"""Workspace endpoints: list mine, create one, read one through verified membership."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.identity import models as identity_models
from relay.identity.auth import Identity
from relay.identity.models import ACTIVE, Membership, UserAccount, WorkspaceCreationRequest
from relay.identity.workspace_access import CurrentWorkspace
from relay.platform.models import Tenant
from relay.shared.db.session import unit_of_work
from relay.shared.errors import ApiError

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

WorkspaceName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"),
]


class WorkspaceSummary(BaseModel):
    id: uuid.UUID
    name: str
    role: str


class CreateWorkspace(BaseModel):
    name: WorkspaceName


async def _resolve_user_id(session: AsyncSession, workos_user_id: str) -> uuid.UUID:
    """Create-or-get the caller's Relay user. Concurrency-safe via the unique key."""
    stmt = (
        insert(UserAccount)
        .values(workos_user_id=workos_user_id)
        .on_conflict_do_update(
            index_elements=[UserAccount.workos_user_id],
            # No-op update so RETURNING yields the existing row's id.
            set_={"workos_user_id": workos_user_id},
        )
        .returning(UserAccount.id)
    )
    return (await session.execute(stmt)).scalar_one()


async def _workspace_for_user(
    session: AsyncSession, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> WorkspaceSummary | None:
    row = (
        await session.execute(
            select(Tenant.id, Tenant.name, Membership.role)
            .join(Membership, Membership.tenant_id == Tenant.id)
            .where(Membership.user_id == user_id, Tenant.id == tenant_id)
        )
    ).one_or_none()
    return WorkspaceSummary(id=row[0], name=row[1], role=row[2]) if row else None


async def create_workspace(
    factory: async_sessionmaker[AsyncSession], workos_user_id: str, name: str, key: str
) -> tuple[WorkspaceSummary, bool]:
    """Create workspace + owner membership atomically; replay returns the original.

    Returns (workspace, created). The new tenant ID is generated here, so the tenant
    context of this transaction is never client-derived.
    """
    tenant_id = uuid.uuid7()
    async with unit_of_work(factory, tenant_id, workos_user_id) as session:
        user_id = await _resolve_user_id(session, workos_user_id)
        claimed = await session.scalar(
            insert(WorkspaceCreationRequest)
            .values(user_id=user_id, idempotency_key=key, created_tenant_id=tenant_id)
            .on_conflict_do_nothing()
            .returning(WorkspaceCreationRequest.created_tenant_id)
        )
        if claimed is None:
            existing = await session.scalar(
                select(WorkspaceCreationRequest.created_tenant_id).where(
                    WorkspaceCreationRequest.user_id == user_id,
                    WorkspaceCreationRequest.idempotency_key == key,
                )
            )
            summary = await _workspace_for_user(session, user_id, existing) if existing else None
            if summary is None:
                raise ApiError(409, "idempotency_conflict", "This request was already used.")
            return summary, False

        session.add(Tenant(id=tenant_id, name=name))
        await session.flush()
        session.add(
            Membership(
                tenant_id=tenant_id,
                user_id=user_id,
                role=identity_models.OWNER_ROLE,
                status=ACTIVE,
            )
        )
        await session.flush()
        return WorkspaceSummary(id=tenant_id, name=name, role=identity_models.OWNER_ROLE), True


@router.get("")
async def list_my_workspaces(identity: Identity, request: Request) -> list[WorkspaceSummary]:
    """Workspaces where the caller has an active membership. No tenant context needed."""
    async with unit_of_work(request.app.state.session_factory, None, identity.workos_user_id) as s:
        rows = await s.execute(
            select(Tenant.id, Tenant.name, Membership.role)
            .join(Membership, Membership.tenant_id == Tenant.id)
            .join(UserAccount, UserAccount.id == Membership.user_id)
            .where(
                UserAccount.workos_user_id == identity.workos_user_id,
                Membership.status == ACTIVE,
            )
            .order_by(Tenant.name, Tenant.id)
        )
        return [WorkspaceSummary(id=r[0], name=r[1], role=r[2]) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_my_workspace(
    body: CreateWorkspace,
    identity: Identity,
    idempotency_key: IdempotencyKey,
    request: Request,
    response: Response,
) -> WorkspaceSummary:
    summary, created = await create_workspace(
        request.app.state.session_factory, identity.workos_user_id, body.name, idempotency_key
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return summary


@router.get("/{workspace_id}")
async def get_workspace(access: CurrentWorkspace) -> WorkspaceSummary:
    tenant = await access.session.get_one(Tenant, access.tenant_id)
    return WorkspaceSummary(id=tenant.id, name=tenant.name, role=access.role)
