"""Responsibility governance: managed types, restricted access grants, dependencies,
review cadence and verification.

Restricted responsibilities are fail-closed twice: the `restricted_visibility` row policy
(migration 0025) hides them from every query, and services only act on rows they can
read. Granting access is a manager action and audited; it never reveals other
restricted responsibilities.

Review cadence: the responsibility's own cadence, else its type's, else the criticality
tier's (governance.criticality_policy, with built-in defaults).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import delete, func, or_, select

from relay.audit import service as audit
from relay.catalog.models import (
    Asset,
    Responsibility,
    ResponsibilityAccess,
    ResponsibilityDependency,
    ResponsibilityType,
)
from relay.directory.models import Person
from relay.governance import service as governance
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.shared.api_types import LongText, Name, StrictInput
from relay.shared.errors import ApiError

# Responsibility columns a create/update may set directly.
FIELDS = frozenset(
    {
        "restricted",
        "type_id",
        "escalation_path",
        "escalation_contact",
        "review_cadence_days",
        "needs_verification",
        "procedures",
        "access_prerequisites",
        "accountable_person_id",
    }
)
Relationship = Literal["depends_on", "feeds", "escalates_to", "shares_access"]


class TypeIn(StrictInput):
    name: Name
    description: LongText | None = None
    review_cadence_days: int | None = None


class TypeView(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    review_cadence_days: int | None
    responsibilities: int


class DependencyIn(StrictInput):
    depends_on_responsibility_id: uuid.UUID | None = None
    depends_on_asset_id: uuid.UUID | None = None
    relationship: Relationship = "depends_on"
    note: LongText | None = None


class DependencyView(BaseModel):
    id: uuid.UUID
    direction: Literal["outgoing", "incoming"]
    relationship: str
    provenance: str
    note: str | None
    target_type: Literal["responsibility", "asset"]
    target_id: uuid.UUID
    target_name: str
    created_at: datetime


class AccessGrantIn(StrictInput):
    user_id: uuid.UUID


class AccessGrantView(BaseModel):
    user_id: uuid.UUID
    name: str
    granted_at: datetime


class StewardshipView(BaseModel):
    dependencies: list[DependencyView]
    access: list[AccessGrantView]


@dataclass(frozen=True, slots=True)
class Names:
    type_name: str | None
    reviewer_name: str | None
    accountable_name: str | None


# ---------------------------------------------------------------- helpers used by the catalog


async def clean(access: WorkspaceAccess, changes: dict[str, Any]) -> dict[str, Any]:
    """Validate governance fields: same-workspace type and person; trimmed text."""
    if changes.get("type_id") is not None:
        found = await access.session.scalar(
            select(ResponsibilityType.id).where(ResponsibilityType.id == changes["type_id"])
        )
        if found is None:
            raise ApiError(422, "type_not_found", "That responsibility type does not exist.")
    if changes.get("accountable_person_id") is not None:
        found = await access.session.scalar(
            select(Person.id).where(
                Person.id == changes["accountable_person_id"], Person.status == "active"
            )
        )
        if found is None:
            raise ApiError(422, "person_not_found", "Choose an active person as the contact.")
    for key in ("escalation_path", "escalation_contact"):
        if key in changes:
            changes[key] = (changes[key] or "").strip() or None
    for key in ("procedures", "access_prerequisites"):
        if changes.get(key) is not None:
            changes[key] = [item.strip() for item in changes[key] if item.strip()]
        elif key in changes:
            changes[key] = []
    for key in ("restricted", "needs_verification"):
        if key in changes and changes[key] is None:
            del changes[key]
    return changes


async def review_days(
    access: WorkspaceAccess, responsibilities: list[Responsibility]
) -> dict[uuid.UUID, int]:
    tiers = await governance.criticality_tiers(access.session)
    type_days = dict(
        (
            await access.session.execute(
                select(ResponsibilityType.id, ResponsibilityType.review_cadence_days).where(
                    ResponsibilityType.id.in_({r.type_id for r in responsibilities if r.type_id})
                )
            )
        ).all()
    )
    return {
        r.id: r.review_cadence_days
        or (type_days.get(r.type_id) if r.type_id else None)
        or tiers[r.criticality].review_days
        for r in responsibilities
    }


def is_review_due(r: Responsibility, days: int, now: datetime) -> bool:
    reviewed = r.last_reviewed_at or r.created_at
    return reviewed + timedelta(days=days) <= now


async def type_names(access: WorkspaceAccess) -> dict[uuid.UUID, str]:
    return dict(
        (await access.session.execute(select(ResponsibilityType.id, ResponsibilityType.name))).all()
    )


async def governance_names(access: WorkspaceAccess, r: Responsibility) -> Names:
    type_name = (
        await access.session.scalar(
            select(ResponsibilityType.name).where(ResponsibilityType.id == r.type_id)
        )
        if r.type_id
        else None
    )
    reviewer = (
        await access.session.scalar(
            select(func.coalesce(Membership.display_name, Membership.email)).where(
                Membership.user_id == r.last_reviewed_by
            )
        )
        if r.last_reviewed_by
        else None
    )
    accountable = (
        await access.session.scalar(
            select(Person.display_name).where(Person.id == r.accountable_person_id)
        )
        if r.accountable_person_id
        else None
    )
    return Names(type_name, reviewer, accountable)


def _audit(
    access: WorkspaceAccess, action: str, rid: uuid.UUID, **details: str | int | bool | None
) -> None:
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=action,
        actor_user_id=access.user_id,
        target_type="responsibility",
        target_id=rid,
        details=details,
    )


async def _responsibility(access: WorkspaceAccess, rid: uuid.UUID) -> Responsibility:
    # The row policy already hides restricted responsibilities from people without access.
    r = await access.session.scalar(
        select(Responsibility).where(
            Responsibility.id == rid,
            visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
        )
    )
    if r is None:
        raise ApiError(404, "responsibility_not_found", "Responsibility not found.")
    return r


# ---------------------------------------------------------------- types


async def list_types(access: WorkspaceAccess) -> list[TypeView]:
    authorize(access, Permission.RESPONSIBILITY_READ)
    counts = dict(
        (
            await access.session.execute(
                select(Responsibility.type_id, func.count())
                .where(Responsibility.status == "active", Responsibility.type_id.is_not(None))
                .group_by(Responsibility.type_id)
            )
        ).all()
    )
    rows = await access.session.scalars(
        select(ResponsibilityType)
        .where(visible(access, Permission.RESPONSIBILITY_READ, ResponsibilityType.tenant_id))
        .order_by(ResponsibilityType.name)
    )
    return [
        TypeView(
            id=t.id,
            name=t.name,
            description=t.description,
            review_cadence_days=t.review_cadence_days,
            responsibilities=counts.get(t.id, 0),
        )
        for t in rows
    ]


async def create_type(access: WorkspaceAccess, data: TypeIn) -> list[TypeView]:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    if data.review_cadence_days is not None and not 7 <= data.review_cadence_days <= 730:
        raise ApiError(422, "invalid_cadence", "Review every 7 to 730 days.")
    exists = await access.session.scalar(
        select(ResponsibilityType.id).where(
            func.lower(ResponsibilityType.name) == data.name.strip().lower()
        )
    )
    if exists:
        raise ApiError(409, "type_exists", "A type with that name already exists.")
    t = ResponsibilityType(
        tenant_id=access.tenant_id,
        name=data.name.strip(),
        description=data.description or None,
        review_cadence_days=data.review_cadence_days,
        created_by=access.user_id,
    )
    access.session.add(t)
    await access.session.flush()
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="responsibility_type.created",
        actor_user_id=access.user_id,
        target_type="responsibility_type",
        target_id=t.id,
        details={},
    )
    return await list_types(access)


# ---------------------------------------------------------------- review & verification


async def mark_reviewed(access: WorkspaceAccess, rid: uuid.UUID, *, verified: bool) -> None:
    """A person confirms the responsibility is current; `verified` also clears the
    needs-human-verification flag (e.g. after an import or an AI suggestion)."""
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    r = await _responsibility(access, rid)
    r.last_reviewed_at, r.last_reviewed_by = func.now(), access.user_id
    if verified:
        r.needs_verification = False
    _audit(access, "responsibility.reviewed", rid, verified=str(verified).lower())


# ---------------------------------------------------------------- dependencies


async def stewardship(access: WorkspaceAccess, rid: uuid.UUID) -> StewardshipView:
    await _responsibility(access, rid)
    rows = list(
        await access.session.scalars(
            select(ResponsibilityDependency)
            .where(
                or_(
                    ResponsibilityDependency.responsibility_id == rid,
                    ResponsibilityDependency.depends_on_responsibility_id == rid,
                )
            )
            .order_by(ResponsibilityDependency.created_at)
        )
    )
    # Only responsibilities the caller can see are named; hidden ones are left out.
    ids = {d.responsibility_id for d in rows} | {
        d.depends_on_responsibility_id for d in rows if d.depends_on_responsibility_id
    }
    names = dict(
        (
            await access.session.execute(
                select(Responsibility.id, Responsibility.name).where(Responsibility.id.in_(ids))
            )
        ).all()
    )
    assets = dict(
        (
            await access.session.execute(
                select(Asset.id, Asset.name).where(
                    Asset.id.in_({d.depends_on_asset_id for d in rows if d.depends_on_asset_id})
                )
            )
        ).all()
    )
    deps = []
    for d in rows:
        outgoing = d.responsibility_id == rid
        if outgoing and d.depends_on_asset_id:
            target_type, target_id = "asset", d.depends_on_asset_id
            target_name = assets.get(target_id)
        else:
            target_type = "responsibility"
            target_id = d.depends_on_responsibility_id if outgoing else d.responsibility_id  # type: ignore[assignment]
            target_name = names.get(target_id)
        if target_name is None:
            continue
        deps.append(
            DependencyView(
                id=d.id,
                direction="outgoing" if outgoing else "incoming",
                relationship=d.relationship,
                provenance=d.provenance,
                note=d.note,
                target_type=target_type,
                target_id=target_id,
                target_name=target_name,
                created_at=d.created_at,
            )
        )
    grants: list[AccessGrantView] = []
    if role_allows(access.role, Permission.RESPONSIBILITY_MANAGE):
        grants = [
            AccessGrantView(user_id=user_id, name=name or email or "Member", granted_at=at)
            for user_id, name, email, at in await access.session.execute(
                select(
                    ResponsibilityAccess.user_id,
                    Membership.display_name,
                    Membership.email,
                    ResponsibilityAccess.granted_at,
                )
                .join(Membership, Membership.user_id == ResponsibilityAccess.user_id)
                .where(ResponsibilityAccess.responsibility_id == rid)
                .order_by(ResponsibilityAccess.granted_at)
            )
        ]
    return StewardshipView(dependencies=deps, access=grants)


async def add_dependency(
    access: WorkspaceAccess, rid: uuid.UUID, data: DependencyIn
) -> StewardshipView:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await _responsibility(access, rid)
    if (data.depends_on_responsibility_id is None) == (data.depends_on_asset_id is None):
        raise ApiError(422, "one_target", "Choose a responsibility or an asset.")
    if data.depends_on_responsibility_id is not None:
        if data.depends_on_responsibility_id == rid:
            raise ApiError(422, "not_self", "A responsibility can't depend on itself.")
        await _responsibility(access, data.depends_on_responsibility_id)
    else:
        found = await access.session.scalar(
            select(Asset.id).where(Asset.id == data.depends_on_asset_id)
        )
        if found is None:
            raise ApiError(422, "asset_not_found", "That asset does not exist.")
    access.session.add(
        ResponsibilityDependency(
            tenant_id=access.tenant_id,
            responsibility_id=rid,
            depends_on_responsibility_id=data.depends_on_responsibility_id,
            depends_on_asset_id=data.depends_on_asset_id,
            relationship=data.relationship,
            provenance="manual",
            note=data.note or None,
            created_by=access.user_id,
        )
    )
    _audit(access, "responsibility.dependency_added", rid, relationship=data.relationship)
    await access.session.flush()
    return await stewardship(access, rid)


async def remove_dependency(
    access: WorkspaceAccess, rid: uuid.UUID, dependency_id: uuid.UUID
) -> StewardshipView:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await _responsibility(access, rid)
    removed = await access.session.execute(
        delete(ResponsibilityDependency).where(
            ResponsibilityDependency.id == dependency_id,
            ResponsibilityDependency.responsibility_id == rid,
        )
    )
    if not removed.rowcount:  # type: ignore[attr-defined]
        raise ApiError(404, "dependency_not_found", "Dependency not found.")
    _audit(access, "responsibility.dependency_removed", rid)
    return await stewardship(access, rid)


# ---------------------------------------------------------------- restricted access


async def grant_access(
    access: WorkspaceAccess, rid: uuid.UUID, data: AccessGrantIn
) -> StewardshipView:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    r = await _responsibility(access, rid)
    if not r.restricted:
        raise ApiError(409, "not_restricted", "Everyone can already see this responsibility.")
    member = await access.session.scalar(
        select(Membership.id).where(
            Membership.user_id == data.user_id, Membership.status == "active"
        )
    )
    if member is None:
        raise ApiError(422, "not_a_member", "Grant access to an active member.")
    exists = await access.session.scalar(
        select(ResponsibilityAccess.id).where(
            ResponsibilityAccess.responsibility_id == rid,
            ResponsibilityAccess.user_id == data.user_id,
        )
    )
    if exists is None:
        access.session.add(
            ResponsibilityAccess(
                tenant_id=access.tenant_id,
                responsibility_id=rid,
                user_id=data.user_id,
                granted_by=access.user_id,
            )
        )
        _audit(access, "responsibility.access_granted", rid, user_id=str(data.user_id))
        await access.session.flush()
    return await stewardship(access, rid)


async def revoke_access(
    access: WorkspaceAccess, rid: uuid.UUID, user_id: uuid.UUID
) -> StewardshipView:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await _responsibility(access, rid)
    await access.session.execute(
        delete(ResponsibilityAccess).where(
            ResponsibilityAccess.responsibility_id == rid, ResponsibilityAccess.user_id == user_id
        )
    )
    _audit(access, "responsibility.access_revoked", rid, user_id=str(user_id))
    return await stewardship(access, rid)
