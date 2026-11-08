"""Workspace endpoints: list mine, create one, read one through verified membership."""

import uuid
from typing import Annotated

import procrastinate
from fastapi import APIRouter, Header, Query, Request, Response, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.audit import service as audit
from relay.identity import models as identity_models
from relay.identity.auth import Identity
from relay.identity.models import ACTIVE, Membership, UserAccount, WorkspaceCreationRequest
from relay.identity.tokens import VerifiedIdentity
from relay.identity.workspace_access import CurrentWorkspace, WorkspaceAccess
from relay.jobs import outbox
from relay.platform.models import Tenant
from relay.policy.permissions import Permission, authorize, authorize_principal
from relay.shared.api_types import StrictInput
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


class WorkspaceView(BaseModel):
    id: uuid.UUID
    name: str
    role: str


class WorkspaceIn(StrictInput):
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
) -> WorkspaceView | None:
    row = (
        await session.execute(
            select(Tenant.id, Tenant.name, Membership.role)
            .join(Membership, Membership.tenant_id == Tenant.id)
            .where(Membership.user_id == user_id, Tenant.id == tenant_id)
        )
    ).one_or_none()
    return WorkspaceView(id=row[0], name=row[1], role=row[2]) if row else None


async def create_workspace(
    factory: async_sessionmaker[AsyncSession],
    jobs: procrastinate.App,
    identity: VerifiedIdentity,
    name: str,
    key: str,
) -> tuple[WorkspaceView, bool]:
    """Create workspace + owner membership atomically; replay returns the original.

    The same transaction writes the audit events and the `workspace.created` outbox event
    (with its job), so either all of it exists or none of it does.

    Returns (workspace, created). The new tenant ID is generated here, so the tenant
    context of this transaction is never client-derived.
    """
    authorize_principal(identity, Permission.WORKSPACE_CREATE)
    workos_user_id = identity.workos_user_id
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
        membership_id = uuid.uuid7()
        session.add(
            Membership(
                id=membership_id,
                tenant_id=tenant_id,
                user_id=user_id,
                role=identity_models.OWNER_ROLE,
                status=ACTIVE,
            )
        )
        await session.flush()
        audit.record(
            session,
            tenant_id=tenant_id,
            action="workspace.created",
            actor_user_id=user_id,
            target_type="workspace",
            target_id=tenant_id,
        )
        audit.record(
            session,
            tenant_id=tenant_id,
            action="membership.created",
            actor_user_id=user_id,
            target_type="membership",
            target_id=membership_id,
            details={"role": identity_models.OWNER_ROLE, "status": ACTIVE},
        )
        await outbox.emit(
            session,
            jobs,
            tenant_id=tenant_id,
            event_type="workspace.created",
            payload={"workspace_id": str(tenant_id), "created_by": str(user_id)},
        )
        return WorkspaceView(id=tenant_id, name=name, role=identity_models.OWNER_ROLE), True


@router.get("")
async def list_my_workspaces(identity: Identity, request: Request) -> list[WorkspaceView]:
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
        return [WorkspaceView(id=r[0], name=r[1], role=r[2]) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_my_workspace(
    body: WorkspaceIn,
    identity: Identity,
    idempotency_key: IdempotencyKey,
    request: Request,
    response: Response,
) -> WorkspaceView:
    summary, created = await create_workspace(
        request.app.state.session_factory,
        request.app.state.jobs,
        identity,
        body.name,
        idempotency_key,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return summary


async def read_workspace(access: WorkspaceAccess) -> WorkspaceView:
    authorize(access, Permission.WORKSPACE_READ)
    tenant = await access.session.get_one(Tenant, access.tenant_id)
    return WorkspaceView(id=tenant.id, name=tenant.name, role=access.role)


@router.get("/{workspace_id}")
async def get_workspace(access: CurrentWorkspace) -> WorkspaceView:
    return await read_workspace(access)


@router.get("/{workspace_id}/audit-events")
async def list_audit_events(
    access: CurrentWorkspace, limit: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[audit.AuditEventView]:
    return await audit.list_events(access, limit=limit)
