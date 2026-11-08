"""Tenant resolution: turn a verified identity + requested workspace into tenant context.

The request names a workspace (path parameter). That choice is never trusted on its own:
inside one transaction we first look up the caller's membership with *no* tenant context
(identity policies only show the caller their own rows), and only if it is active do we
bind the tenant. The handler then runs in that same transaction as `relay_app` under RLS.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.identity.auth import Identity
from relay.identity.models import ACTIVE, Membership, UserAccount
from relay.shared.db.session import establish_tenant_context, unit_of_work
from relay.shared.errors import ApiError


@dataclass(frozen=True, slots=True)
class WorkspaceAccess:
    session: AsyncSession
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    membership_id: uuid.UUID
    role: str


async def get_workspace_access(
    workspace_id: uuid.UUID, identity: Identity, request: Request
) -> AsyncIterator[WorkspaceAccess]:
    factory = request.app.state.session_factory
    async with unit_of_work(factory, None, identity.workos_user_id) as session:
        row = (
            await session.execute(
                select(UserAccount.id, Membership.id, Membership.role, Membership.status)
                .select_from(UserAccount)
                .outerjoin(
                    Membership,
                    and_(
                        Membership.user_id == UserAccount.id, Membership.tenant_id == workspace_id
                    ),
                )
                .where(UserAccount.workos_user_id == identity.workos_user_id)
            )
        ).one_or_none()
        if row is None:
            raise ApiError(403, "user_not_provisioned", "No Relay account exists for this user.")
        user_id, membership_id, role, status = row
        if membership_id is None:
            # Same answer whether the workspace exists or not: no existence oracle.
            raise ApiError(404, "workspace_not_found", "Workspace not found.")
        if status != ACTIVE:
            raise ApiError(403, "membership_inactive", "Your access to this workspace is inactive.")
        await establish_tenant_context(session, workspace_id)
        yield WorkspaceAccess(session, workspace_id, user_id, membership_id, role)


CurrentWorkspace = Annotated[WorkspaceAccess, Depends(get_workspace_access)]
