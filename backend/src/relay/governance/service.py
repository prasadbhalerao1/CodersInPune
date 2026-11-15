"""Workspace continuity policies: read by everyone, changed by admins, always audited.

- critical_requires_backup: a critical responsibility without a backup is a high risk
  (and single-holder critical coverage is flagged). Off: it is a medium risk like any
  other missing backup.
- knowledge_review_days: how long knowledge stays "fresh" after a review.
- retention_days: how long operational records are kept (governance.administration).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.governance.models import CriticalityPolicy, WorkspacePolicy
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import StrictInput


@dataclass(frozen=True, slots=True)
class Policy:
    critical_requires_backup: bool = True
    knowledge_review_days: int = 90
    retention_days: int = 365


DEFAULT = Policy()


class PolicyView(BaseModel):
    critical_requires_backup: bool
    knowledge_review_days: int
    retention_days: int
    updated_by_name: str | None
    updated_at: datetime | None


class PolicyUpdate(StrictInput):
    critical_requires_backup: bool | None = None
    knowledge_review_days: Annotated[int, Field(ge=7, le=730)] | None = None
    retention_days: Annotated[int, Field(ge=30, le=3650)] | None = None


async def current(session: AsyncSession) -> Policy:
    """The policy for the session's tenant (RLS scopes the row); defaults when unset."""
    row = await session.scalar(select(WorkspacePolicy))
    if row is None:
        return DEFAULT
    return Policy(row.critical_requires_backup, row.knowledge_review_days, row.retention_days)


async def _view(access: WorkspaceAccess, row: WorkspacePolicy | None) -> PolicyView:
    if row is None:
        return PolicyView(
            critical_requires_backup=DEFAULT.critical_requires_backup,
            knowledge_review_days=DEFAULT.knowledge_review_days,
            retention_days=DEFAULT.retention_days,
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
        retention_days=row.retention_days,
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
            retention_days=DEFAULT.retention_days,
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


# ---------------------------------------------------------------- criticality tiers


@dataclass(frozen=True, slots=True)
class Tier:
    requires_backup: bool
    review_days: int
    requires_accountable_contact: bool


Criticality = Literal["critical", "high", "standard", "low"]
DEFAULT_TIERS: dict[str, Tier] = {
    "critical": Tier(requires_backup=True, review_days=90, requires_accountable_contact=True),
    "high": Tier(requires_backup=True, review_days=180, requires_accountable_contact=False),
    "standard": Tier(requires_backup=False, review_days=365, requires_accountable_contact=False),
    "low": Tier(requires_backup=False, review_days=365, requires_accountable_contact=False),
}


class TierView(BaseModel):
    criticality: Criticality
    requires_backup: bool
    review_days: int
    requires_accountable_contact: bool
    customised: bool


class TierUpdate(StrictInput):
    requires_backup: bool
    review_days: Annotated[int, Field(ge=7, le=730)]
    requires_accountable_contact: bool


async def criticality_tiers(session: AsyncSession) -> dict[str, Tier]:
    """Coverage policy per criticality (RLS scopes rows to the tenant); defaults otherwise."""
    tiers = dict(DEFAULT_TIERS)
    for row in await session.scalars(select(CriticalityPolicy)):
        tiers[row.criticality] = Tier(
            row.requires_backup, row.review_days, row.requires_accountable_contact
        )
    return tiers


async def list_tiers(access: WorkspaceAccess) -> list[TierView]:
    authorize(access, Permission.WORKSPACE_READ)
    custom = set(await access.session.scalars(select(CriticalityPolicy.criticality)))
    tiers = await criticality_tiers(access.session)
    return [
        TierView(
            criticality=c,
            requires_backup=t.requires_backup,
            review_days=t.review_days,
            requires_accountable_contact=t.requires_accountable_contact,
            customised=c in custom,
        )
        for c, t in tiers.items()
    ]


async def update_tier(
    access: WorkspaceAccess, criticality: Criticality, data: TierUpdate
) -> list[TierView]:
    authorize(access, Permission.POLICY_MANAGE)
    row = await access.session.scalar(
        select(CriticalityPolicy)
        .where(CriticalityPolicy.criticality == criticality)
        .with_for_update()
    )
    if row is None:
        row = CriticalityPolicy(
            tenant_id=access.tenant_id, criticality=criticality, updated_by=access.user_id
        )
        access.session.add(row)
    row.requires_backup = data.requires_backup
    row.review_days = data.review_days
    row.requires_accountable_contact = data.requires_accountable_contact
    row.updated_by, row.updated_at = access.user_id, func.now()
    await access.session.flush()
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="policy.tier_updated",
        actor_user_id=access.user_id,
        target_type="criticality_policy",
        target_id=row.id,
        details={"criticality": criticality, **{k: str(v) for k, v in data.model_dump().items()}},
    )
    return await list_tiers(access)
