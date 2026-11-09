"""Workspace continuity policies: read by everyone, changed by admins, always audited.

- critical_requires_backup: a critical responsibility without a backup is a high risk
  (and single-holder critical coverage is flagged). Off: it is a medium risk like any
  other missing backup.
- knowledge_review_days: how long knowledge stays "fresh" after a review.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.governance.models import WorkspacePolicy
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import StrictInput


@dataclass(frozen=True, slots=True)
class Policy:
    critical_requires_backup: bool = True
    knowledge_review_days: int = 90


DEFAULT = Policy()


class PolicyView(BaseModel):
    critical_requires_backup: bool
    knowledge_review_days: int
    updated_by_name: str | None
    updated_at: datetime | None


class PolicyUpdate(StrictInput):
    critical_requires_backup: bool | None = None
    knowledge_review_days: Annotated[int, Field(ge=7, le=730)] | None = None


async def current(session: AsyncSession) -> Policy:
    """The policy for the session's tenant (RLS scopes the row); defaults when unset."""
    row = await session.scalar(select(WorkspacePolicy))
    if row is None:
        return DEFAULT
    return Policy(row.critical_requires_backup, row.knowledge_review_days)


async def _view(access: WorkspaceAccess, row: WorkspacePolicy | None) -> PolicyView:
    if row is None:
        return PolicyView(
            critical_requires_backup=DEFAULT.critical_requires_backup,
            knowledge_review_days=DEFAULT.knowledge_review_days,
            updated_by_name=None,
            updated_at=None,
        )
    name = await access.session.scalar(
        select(func.coalesce(Membership.display_name, Membership.email)).where(
            Membership.user_id == row.updated_by
        )
    )
    return PolicyView(
        critical_requires_backup=row.critical_requires_backup,
        knowledge_review_days=row.knowledge_review_days,
        updated_by_name=name or "Former member",
        updated_at=row.updated_at,
    )


async def get_policy(access: WorkspaceAccess) -> PolicyView:
    authorize(access, Permission.WORKSPACE_READ)
    row = await access.session.scalar(
        select(WorkspacePolicy).where(
            visible(access, Permission.WORKSPACE_READ, WorkspacePolicy.tenant_id)
        )
    )
    return await _view(access, row)


async def update_policy(access: WorkspaceAccess, data: PolicyUpdate) -> PolicyView:
    authorize(access, Permission.POLICY_MANAGE)
    changes = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    row = await access.session.scalar(
        select(WorkspacePolicy)
        .where(visible(access, Permission.POLICY_MANAGE, WorkspacePolicy.tenant_id))
        .with_for_update()
    )
    if row is None:
        row = WorkspacePolicy(
            id=uuid.uuid7(),
            tenant_id=access.tenant_id,
            critical_requires_backup=DEFAULT.critical_requires_backup,
            knowledge_review_days=DEFAULT.knowledge_review_days,
            updated_by=access.user_id,
        )
        access.session.add(row)
    before = {k: getattr(row, k) for k in changes}
    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_by, row.updated_at = access.user_id, func.now()
    await access.session.flush()
    await access.session.refresh(row)
    if changes:
        audit.record(
            access.session,
            tenant_id=access.tenant_id,
            action="policy.updated",
            actor_user_id=access.user_id,
            target_type="workspace_policy",
            target_id=row.id,
            details={
                **{f"{k}_from": str(v) for k, v in before.items()},
                **{f"{k}_to": str(v) for k, v in changes.items()},
            },
        )
    return await _view(access, row)
