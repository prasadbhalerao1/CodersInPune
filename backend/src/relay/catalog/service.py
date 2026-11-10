"""Responsibility catalogue and ownership assignments.

Time semantics: an assignment is active at instant t when
`valid_from <= t AND (valid_to IS NULL OR valid_to > t)` — the half-open range
`[valid_from, valid_to)`. Ending an assignment sets `valid_to`; nothing is deleted, and
every change also writes an append-only `ownership_assignment_change` row and an audit
event in the same transaction.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, Field, model_validator
from sqlalchemy import ColumnElement, and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.catalog import stewardship
from relay.catalog.models import (
    Asset,
    OwnershipAssignment,
    OwnershipAssignmentChange,
    Responsibility,
    ResponsibilityAsset,
)
from relay.directory.models import Department, Person, Team
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import LongText, Name, ShortText, StrictInput, blank_to_none
from relay.shared.errors import ApiError

Criticality = Literal["critical", "high", "standard", "low"]
Role = Literal["primary", "co_owner", "backup"]
ResponsibilityStatus = Literal["active", "archived"]

_CONSTRAINT_ERRORS = {
    "ex_ownership_assignment_one_primary": (
        "primary_owner_conflict",
        "Another primary owner is assigned for this period. Replace the primary owner instead.",
    ),
    "ex_ownership_assignment_one_temporary": (
        "coverage_conflict",
        "Someone already covers this responsibility for part of that period.",
    ),
    "ex_ownership_assignment_one_role": (
        "assignment_overlap",
        "This person or team already holds a role on this responsibility for this period.",
    ),
}


# ---------------------------------------------------------------- schemas


class Stewardship(StrictInput):
    """Governance fields shared by create and update."""

    restricted: bool | None = None
    type_id: uuid.UUID | None = None
    escalation_path: LongText | None = None
    escalation_contact: ShortText | None = None
    review_cadence_days: Annotated[int, Field(ge=7, le=730)] | None = None
    needs_verification: bool | None = None
    procedures: Annotated[list[Name], Field(max_length=30)] | None = None
    access_prerequisites: Annotated[list[Name], Field(max_length=30)] | None = None
    accountable_person_id: uuid.UUID | None = None


class ResponsibilityIn(Stewardship):
    name: Name
    description: LongText | None = None
    category: ShortText | None = None
    criticality: Criticality = "standard"


class ResponsibilityUpdate(Stewardship):
    version: int
    name: Name | None = None
    description: LongText | None = None
    category: ShortText | None = None
    criticality: Criticality | None = None


class Assignee(StrictInput):
    person_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Assignee:
        if (self.person_id is None) == (self.team_id is None):
            raise ValueError("provide exactly one of person_id or team_id")
        return self


class AssignmentIn(Assignee):
    role: Role
    starts_at: AwareDatetime | None = None
    reason: LongText | None = None


class EndAssignmentIn(StrictInput):
    ends_at: AwareDatetime | None = None
    reason: LongText | None = None


class CorrectionIn(StrictInput):
    """Fix a recorded period (e.g. backdate a start). The previous period stays in the
    change history; a reason is mandatory."""

    valid_from: AwareDatetime
    valid_to: AwareDatetime | None = None
    reason: LongText


class ReplacePrimaryIn(Assignee):
    effective_at: AwareDatetime | None = None
    reason: LongText | None = None


class AssigneeView(BaseModel):
    type: Literal["person", "team"]
    id: uuid.UUID
    name: str
    status: str
    department_name: str | None = None


class AssignmentView(BaseModel):
    id: uuid.UUID
    role: str
    assignee: AssigneeView
    valid_from: datetime
    valid_to: datetime | None
    state: Literal["current", "scheduled", "ended"]
    reason: str | None


class ResponsibilitySummary(BaseModel):
    id: uuid.UUID
    name: str
    category: str | None
    criticality: str
    status: str
    primary_owner: AssigneeView | None
    backup_count: int
    updated_at: datetime
    restricted: bool = False
    type_id: uuid.UUID | None = None
    type_name: str | None = None
    needs_verification: bool = False
    review_due: bool = False
    last_reviewed_at: datetime | None = None


class ResponsibilityDetail(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    category: str | None
    criticality: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None
    as_of: datetime
    owners_as_of: list[AssignmentView]
    assignments: list[AssignmentView]
    assets: list[LinkedAssetView]
    restricted: bool = False
    type_id: uuid.UUID | None = None
    type_name: str | None = None
    escalation_path: str | None = None
    escalation_contact: str | None = None
    review_cadence_days: int | None = None
    effective_review_days: int = 365
    last_reviewed_at: datetime | None = None
    last_reviewed_by_name: str | None = None
    review_due: bool = False
    needs_verification: bool = False
    procedures: list[str] = []
    access_prerequisites: list[str] = []
    accountable_person_id: uuid.UUID | None = None
    accountable_person_name: str | None = None


class LinkedAssetView(BaseModel):
    id: uuid.UUID
    name: str
    asset_type: str
    url: str | None
    status: str
    relationship: str


class ChangeView(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    change_type: str
    role: str
    assignee: AssigneeView
    valid_from: datetime
    valid_to: datetime | None
    reason: str | None
    changed_by: uuid.UUID
    changed_at: datetime


# ---------------------------------------------------------------- helpers


def utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return utcnow()
    if value.tzinfo is None:
        raise ApiError(422, "naive_datetime", "Timestamps must include a timezone offset.")
    return value


def active_at(at: datetime) -> ColumnElement[bool]:
    return and_(
        OwnershipAssignment.valid_from <= at,
        or_(OwnershipAssignment.valid_to.is_(None), OwnershipAssignment.valid_to > at),
    )


def _state(a: OwnershipAssignment, now: datetime) -> Literal["current", "scheduled", "ended"]:
    if a.valid_from > now:
        return "scheduled"
    if a.valid_to is not None and a.valid_to <= now:
        return "ended"
    return "current"


def _pattern(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def assignee_views(
    session: AsyncSession, assignments: Sequence[OwnershipAssignment]
) -> dict[uuid.UUID, AssigneeView]:
    person_ids = {a.person_id for a in assignments if a.person_id}
    team_ids = {a.team_id for a in assignments if a.team_id}
    views: dict[uuid.UUID, AssigneeView] = {}
    if person_ids:
        for p, department in await session.execute(
            select(Person, Department.name)
            .outerjoin(Department, Department.id == Person.department_id)
            .where(Person.id.in_(person_ids))
        ):
            views[p.id] = AssigneeView(
                type="person",
                id=p.id,
                name=p.display_name,
                status=p.status,
                department_name=department,
            )
    if team_ids:
        for t, department in await session.execute(
            select(Team, Department.name)
            .outerjoin(Department, Department.id == Team.department_id)
            .where(Team.id.in_(team_ids))
        ):
            views[t.id] = AssigneeView(
                type="team", id=t.id, name=t.name, status=t.status, department_name=department
            )
    return views


def _assignment_view(
    a: OwnershipAssignment, assignees: dict[uuid.UUID, AssigneeView], now: datetime
) -> AssignmentView:
    return AssignmentView(
        id=a.id,
        role=a.role,
        assignee=assignees[a.person_id or a.team_id],  # type: ignore[index]
        valid_from=a.valid_from,
        valid_to=a.valid_to,
        state=_state(a, now),
        reason=a.reason,
    )


async def _get_responsibility(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, *, lock: bool = False
) -> Responsibility:
    stmt = select(Responsibility).where(
        Responsibility.id == responsibility_id,
        visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
    )
    if lock:
        stmt = stmt.with_for_update()
    responsibility = await access.session.scalar(stmt)
    if responsibility is None:
        raise ApiError(404, "responsibility_not_found", "Responsibility not found.")
    return responsibility


async def require_active_responsibility(
    access: WorkspaceAccess, responsibility_id: uuid.UUID
) -> Responsibility:
    # Row lock serialises concurrent ownership changes on the same responsibility.
    responsibility = await _get_responsibility(access, responsibility_id, lock=True)
    if responsibility.status != "active":
        raise ApiError(409, "responsibility_archived", "Restore the responsibility to change it.")
    return responsibility


async def require_assignee(access: WorkspaceAccess, assignee: Assignee) -> None:
    model = Person if assignee.person_id else Team
    target_id = assignee.person_id or assignee.team_id
    found = await access.session.scalar(
        select(model.status).where(
            model.id == target_id, visible(access, Permission.DIRECTORY_READ, model.tenant_id)
        )
    )
    if found is None:
        raise ApiError(422, "assignee_not_found", "That person or team does not exist.")
    if found != "active":
        raise ApiError(422, "assignee_archived", "Archived people and teams cannot be assigned.")


def _record_change(
    access: WorkspaceAccess,
    assignment: OwnershipAssignment,
    change_type: str,
    reason: str | None,
) -> None:
    access.session.add(
        OwnershipAssignmentChange(
            tenant_id=access.tenant_id,
            assignment_id=assignment.id,
            responsibility_id=assignment.responsibility_id,
            change_type=change_type,
            valid_from=assignment.valid_from,
            valid_to=assignment.valid_to,
            reason=reason,
            changed_by=access.user_id,
        )
    )


def record_audit(
    access: WorkspaceAccess,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    **details: str | int | bool | None,
) -> None:
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=action,
        actor_user_id=access.user_id,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )


async def _flush_assignments(access: WorkspaceAccess) -> None:
    try:
        await access.session.flush()
    except IntegrityError as exc:
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        code, message = _CONSTRAINT_ERRORS.get(
            constraint or "", ("assignment_conflict", "The ownership change conflicts.")
        )
        raise ApiError(409, code, message) from exc


async def _insert_assignment(
    access: WorkspaceAccess,
    responsibility_id: uuid.UUID,
    role: str,
    assignee: Assignee,
    starts_at: datetime,
    reason: str | None,
) -> OwnershipAssignment:
    assignment = OwnershipAssignment(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        responsibility_id=responsibility_id,
        role=role,
        person_id=assignee.person_id,
        team_id=assignee.team_id,
        valid_from=starts_at,
        reason=reason,
        created_by=access.user_id,
    )
    access.session.add(assignment)
    await _flush_assignments(access)
    _record_change(access, assignment, "assigned", reason)
    return assignment


async def _end(
    access: WorkspaceAccess, assignment: OwnershipAssignment, ends_at: datetime, reason: str | None
) -> None:
    if ends_at <= assignment.valid_from:
        raise ApiError(
            422, "invalid_end", "An assignment must end after it starts; it cannot be erased."
        )
    if assignment.valid_to is not None and ends_at >= assignment.valid_to:
        raise ApiError(409, "already_ended", "This assignment already ends by that time.")
    assignment.valid_to = ends_at
    await _flush_assignments(access)
    _record_change(access, assignment, "ended", reason)


# ---------------------------------------------------------------- responsibilities


async def list_responsibilities(
    access: WorkspaceAccess,
    *,
    q: str | None = None,
    criticality: Criticality | None = None,
    status: ResponsibilityStatus | None = "active",
    category: str | None = None,
    department_id: uuid.UUID | None = None,
    type_id: uuid.UUID | None = None,
    has_backup: bool | None = None,
    review: Literal["due", "ok"] | None = None,
    needs_verification: bool | None = None,
) -> list[ResponsibilitySummary]:
    now = utcnow()
    stmt = select(Responsibility).where(
        visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id)
    )
    if department_id:
        # A responsibility belongs to a department through its current owners.
        owned_in_department = (
            select(OwnershipAssignment.responsibility_id)
            .outerjoin(Person, Person.id == OwnershipAssignment.person_id)
            .outerjoin(Team, Team.id == OwnershipAssignment.team_id)
            .where(
                active_at(now),
                or_(Person.department_id == department_id, Team.department_id == department_id),
            )
        )
        stmt = stmt.where(Responsibility.id.in_(owned_in_department))
    if status:
        stmt = stmt.where(Responsibility.status == status)
    if criticality:
        stmt = stmt.where(Responsibility.criticality == criticality)
    if category:
        stmt = stmt.where(Responsibility.category == category)
    if type_id:
        stmt = stmt.where(Responsibility.type_id == type_id)
    if needs_verification is not None:
        stmt = stmt.where(Responsibility.needs_verification.is_(needs_verification))
    if has_backup is not None:
        backed = select(OwnershipAssignment.responsibility_id).where(
            OwnershipAssignment.role == "backup", active_at(now)
        )
        stmt = stmt.where(
            Responsibility.id.in_(backed) if has_backup else Responsibility.id.not_in(backed)
        )
    if q:
        stmt = stmt.where(
            or_(
                Responsibility.name.ilike(_pattern(q)),
                Responsibility.description.ilike(_pattern(q)),
                Responsibility.category.ilike(_pattern(q)),
            )
        )
    responsibilities = list(
        await access.session.scalars(
            stmt.order_by(Responsibility.name, Responsibility.id).limit(500)
        )
    )
    current = list(
        await access.session.scalars(
            select(OwnershipAssignment).where(
                OwnershipAssignment.responsibility_id.in_([r.id for r in responsibilities]),
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
                active_at(now),
            )
        )
    )
    assignees = await assignee_views(access.session, current)
    cadence = await stewardship.review_days(access, responsibilities)
    types = await stewardship.type_names(access)
    summaries = []
    for r in responsibilities:
        mine = [a for a in current if a.responsibility_id == r.id]
        primary = next((a for a in mine if a.role == "primary"), None)
        due = stewardship.is_review_due(r, cadence[r.id], now)
        if review is not None and due != (review == "due"):
            continue
        summaries.append(
            ResponsibilitySummary(
                id=r.id,
                name=r.name,
                category=r.category,
                criticality=r.criticality,
                status=r.status,
                primary_owner=assignees[primary.person_id or primary.team_id]  # type: ignore[index]
                if primary
                else None,
                backup_count=sum(1 for a in mine if a.role == "backup"),
                updated_at=r.updated_at,
                restricted=r.restricted,
                type_id=r.type_id,
                type_name=types.get(r.type_id) if r.type_id else None,
                needs_verification=r.needs_verification,
                review_due=due,
                last_reviewed_at=r.last_reviewed_at,
            )
        )
    return summaries


async def get_responsibility(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, *, as_of: datetime | None = None
) -> ResponsibilityDetail:
    at = _aware(as_of)
    r = await _get_responsibility(access, responsibility_id)
    assignments = list(
        await access.session.scalars(
            select(OwnershipAssignment)
            .where(
                OwnershipAssignment.responsibility_id == r.id,
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
            )
            .order_by(OwnershipAssignment.valid_from.desc(), OwnershipAssignment.id.desc())
        )
    )
    assignees = await assignee_views(access.session, assignments)
    now = utcnow()

    def is_active(a: OwnershipAssignment) -> bool:
        return a.valid_from <= at and (a.valid_to is None or a.valid_to > at)

    role_order = {"temporary": 0, "primary": 1, "co_owner": 2, "backup": 3}
    owners = sorted((a for a in assignments if is_active(a)), key=lambda a: role_order[a.role])
    linked = await access.session.execute(
        select(Asset, ResponsibilityAsset.relationship)
        .join(ResponsibilityAsset, ResponsibilityAsset.asset_id == Asset.id)
        .where(
            ResponsibilityAsset.responsibility_id == r.id,
            visible(access, Permission.RESPONSIBILITY_READ, Asset.tenant_id),
        )
        .order_by(Asset.name)
    )
    days = (await stewardship.review_days(access, [r]))[r.id]
    names = await stewardship.governance_names(access, r)
    return ResponsibilityDetail(
        restricted=r.restricted,
        type_id=r.type_id,
        type_name=names.type_name,
        escalation_path=r.escalation_path,
        escalation_contact=r.escalation_contact,
        review_cadence_days=r.review_cadence_days,
        effective_review_days=days,
        last_reviewed_at=r.last_reviewed_at,
        last_reviewed_by_name=names.reviewer_name,
        review_due=stewardship.is_review_due(r, days, now),
        needs_verification=r.needs_verification,
        procedures=r.procedures,
        access_prerequisites=r.access_prerequisites,
        accountable_person_id=r.accountable_person_id,
        accountable_person_name=names.accountable_name,
        id=r.id,
        name=r.name,
        description=r.description,
        category=r.category,
        criticality=r.criticality,
        status=r.status,
        version=r.version,
        created_at=r.created_at,
        updated_at=r.updated_at,
        archived_at=r.archived_at,
        as_of=at,
        owners_as_of=[_assignment_view(a, assignees, now) for a in owners],
        assignments=[_assignment_view(a, assignees, now) for a in assignments],
        assets=[
            LinkedAssetView(
                id=a.id,
                name=a.name,
                asset_type=a.asset_type,
                url=a.url,
                status=a.status,
                relationship=relationship,
            )
            for a, relationship in linked
        ],
    )


async def create_responsibility(
    access: WorkspaceAccess, data: ResponsibilityIn
) -> ResponsibilityDetail:
    responsibility = await add_responsibility(access, data)
    return await get_responsibility(access, responsibility.id)


async def add_responsibility(access: WorkspaceAccess, data: ResponsibilityIn) -> Responsibility:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    fields = await stewardship.clean(access, data.model_dump(exclude_unset=True))
    responsibility = Responsibility(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        name=data.name,
        description=blank_to_none(data.description),
        category=blank_to_none(data.category),
        criticality=data.criticality,
        created_by=access.user_id,
        **{k: v for k, v in fields.items() if k in stewardship.FIELDS},
    )
    access.session.add(responsibility)
    await access.session.flush()
    record_audit(
        access,
        "responsibility.created",
        "responsibility",
        responsibility.id,
        criticality=data.criticality,
    )
    return responsibility


async def update_responsibility(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, data: ResponsibilityUpdate
) -> ResponsibilityDetail:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await _get_responsibility(access, responsibility_id)
    changes = await stewardship.clean(
        access, data.model_dump(exclude_unset=True, exclude={"version"})
    )
    for field in ("description", "category"):
        if field in changes:
            changes[field] = blank_to_none(changes[field])
    result = await access.session.execute(
        update(Responsibility)
        .where(Responsibility.id == responsibility_id, Responsibility.version == data.version)
        .values(**changes, version=Responsibility.version + 1, updated_at=func.now())
        .returning(Responsibility.id)
    )
    if result.scalar_one_or_none() is None:
        raise ApiError(
            409, "version_conflict", "This responsibility was changed by someone else. Reload."
        )
    record_audit(
        access,
        "responsibility.updated",
        "responsibility",
        responsibility_id,
        fields=",".join(sorted(changes)),
    )
    access.session.expire_all()
    return await get_responsibility(access, responsibility_id)


async def correct_assignment(
    access: WorkspaceAccess,
    responsibility_id: uuid.UUID,
    assignment_id: uuid.UUID,
    data: CorrectionIn,
) -> ResponsibilityDetail:
    """Correct when an assignment really started or ended, including in the past. Overlap
    rules still apply (one primary at a time); history keeps the original and the reason."""
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await _get_responsibility(access, responsibility_id, lock=True)
    assignment = await access.session.get(OwnershipAssignment, assignment_id, with_for_update=True)
    if assignment is None or assignment.responsibility_id != responsibility_id:
        raise ApiError(404, "assignment_not_found", "Assignment not found.")
    if not data.reason.strip():
        raise ApiError(422, "reason_required", "Say why the record is corrected.")
    if data.valid_to is not None and data.valid_to <= data.valid_from:
        raise ApiError(422, "invalid_range", "The end must be after the start.")
    if assignment.role == "temporary" and data.valid_to is None:
        raise ApiError(422, "invalid_range", "Temporary cover needs an end.")
    before = (assignment.valid_from, assignment.valid_to)
    assignment.valid_from, assignment.valid_to = data.valid_from, data.valid_to
    await _flush_assignments(access)
    _record_change(access, assignment, "corrected", data.reason)
    record_audit(
        access,
        "assignment.corrected",
        "responsibility",
        responsibility_id,
        assignment_id=str(assignment_id),
        from_start=before[0].isoformat(),
        from_end=before[1].isoformat() if before[1] else None,
    )
    access.session.expire_all()
    return await get_responsibility(access, responsibility_id)


async def set_responsibility_status(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, status: ResponsibilityStatus
) -> ResponsibilityDetail:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    r = await _get_responsibility(access, responsibility_id, lock=True)
    if r.status == status:
        raise ApiError(409, f"already_{status}", f"The responsibility is already {status}.")
    r.status = status
    r.archived_at = func.now() if status == "archived" else None
    r.updated_at = func.now()
    r.version += 1
    await access.session.flush()
    record_audit(
        access,
        "responsibility.archived" if status == "archived" else "responsibility.restored",
        "responsibility",
        r.id,
    )
    access.session.expire_all()
    return await get_responsibility(access, responsibility_id)


# ---------------------------------------------------------------- ownership


async def add_assignment(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, data: AssignmentIn
) -> OwnershipAssignment:
    """Assign without replacing anyone: the EXCLUDE constraints reject a second primary."""
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await require_active_responsibility(access, responsibility_id)
    await require_assignee(access, data)
    assignment = await _insert_assignment(
        access, responsibility_id, data.role, data, _aware(data.starts_at), data.reason
    )
    record_audit(
        access,
        "ownership.assigned",
        "ownership_assignment",
        assignment.id,
        role=data.role,
        responsibility_id=str(responsibility_id),
    )
    return assignment


async def assign_owner(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, data: AssignmentIn
) -> ResponsibilityDetail:
    await add_assignment(access, responsibility_id, data)
    return await get_responsibility(access, responsibility_id)


async def end_assignment(
    access: WorkspaceAccess,
    responsibility_id: uuid.UUID,
    assignment_id: uuid.UUID,
    data: EndAssignmentIn,
) -> ResponsibilityDetail:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await require_active_responsibility(access, responsibility_id)
    assignment = await access.session.scalar(
        select(OwnershipAssignment)
        .where(
            OwnershipAssignment.id == assignment_id,
            OwnershipAssignment.responsibility_id == responsibility_id,
        )
        .with_for_update()
    )
    if assignment is None:
        raise ApiError(404, "assignment_not_found", "Assignment not found.")
    await _end(access, assignment, _aware(data.ends_at), data.reason)
    record_audit(
        access,
        "ownership.ended",
        "ownership_assignment",
        assignment.id,
        role=assignment.role,
        responsibility_id=str(responsibility_id),
    )
    return await get_responsibility(access, responsibility_id)


async def handover(
    access: WorkspaceAccess,
    responsibility_id: uuid.UUID,
    role: str,
    recipient: Assignee,
    at: datetime,
    reason: str | None,
    *,
    from_assignment_id: uuid.UUID | None = None,
) -> OwnershipAssignment:
    """Contiguous handover of `role` to `recipient` at `at` (possibly in the future).

    Ends, at `at`: the current primary (for role=primary) or `from_assignment_id`, plus any
    other normal role the recipient holds on this responsibility. Then starts the recipient's
    assignment `[at, open)`. History is only appended; nothing is deleted or rewritten.
    """
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await require_active_responsibility(access, responsibility_id)
    await require_assignee(access, recipient)
    new_holder = recipient.person_id or recipient.team_id
    active = list(
        await access.session.scalars(
            select(OwnershipAssignment)
            .where(
                OwnershipAssignment.responsibility_id == responsibility_id,
                OwnershipAssignment.role != "temporary",
                active_at(at),
            )
            .with_for_update()
        )
    )
    if any(a.role == role and (a.person_id or a.team_id) == new_holder for a in active):
        raise ApiError(409, "already_assigned", "That owner already holds this role.")
    to_end = [
        a
        for a in active
        if (role == "primary" and a.role == "primary")
        or a.id == from_assignment_id
        or (a.person_id or a.team_id) == new_holder
    ]
    for assignment in to_end:
        if assignment.valid_from >= at:
            raise ApiError(
                409, "scheduled_conflict", "End the scheduled assignment before replacing it."
            )
        await _end(access, assignment, at, reason)
    return await _insert_assignment(access, responsibility_id, role, recipient, at, reason)


async def replace_primary(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, data: ReplacePrimaryIn
) -> ResponsibilityDetail:
    """End the current primary (and any other role the new owner holds) at
    `effective_at`, then start the new primary there: one atomic, contiguous handover."""
    at = _aware(data.effective_at)
    previous = await access.session.scalar(
        select(OwnershipAssignment.id).where(
            OwnershipAssignment.responsibility_id == responsibility_id,
            OwnershipAssignment.role == "primary",
            active_at(at),
        )
    )
    new_primary = await handover(access, responsibility_id, "primary", data, at, data.reason)
    record_audit(
        access,
        "ownership.primary_replaced",
        "ownership_assignment",
        new_primary.id,
        responsibility_id=str(responsibility_id),
        previous_assignment_id=str(previous) if previous else None,
    )
    return await get_responsibility(access, responsibility_id)


async def start_cover(
    access: WorkspaceAccess,
    responsibility_id: uuid.UUID,
    recipient: Assignee,
    starts_at: datetime,
    ends_at: datetime,
    reason: str | None,
) -> OwnershipAssignment:
    """Temporary coverage `[starts_at, ends_at)`. Original owners stay untouched, so normal
    ownership resumes automatically when the range ends — no job or manual restore needed."""
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await require_active_responsibility(access, responsibility_id)
    await require_assignee(access, recipient)
    assignment = OwnershipAssignment(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        responsibility_id=responsibility_id,
        role="temporary",
        person_id=recipient.person_id,
        team_id=recipient.team_id,
        valid_from=starts_at,
        valid_to=ends_at,
        reason=reason,
        created_by=access.user_id,
    )
    access.session.add(assignment)
    await _flush_assignments(access)
    _record_change(access, assignment, "assigned", reason)
    return assignment


async def _locked_assignment(
    access: WorkspaceAccess, assignment_id: uuid.UUID
) -> OwnershipAssignment:
    assignment = await access.session.scalar(
        select(OwnershipAssignment).where(OwnershipAssignment.id == assignment_id).with_for_update()
    )
    if assignment is None:
        raise ApiError(404, "assignment_not_found", "Assignment not found.")
    return assignment


async def end_assignment_at(
    access: WorkspaceAccess, assignment_id: uuid.UUID, at: datetime, reason: str | None
) -> None:
    """End (or shorten) an assignment at `at`; e.g. an early return from coverage."""
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await _end(access, await _locked_assignment(access, assignment_id), at, reason)


async def extend_cover(
    access: WorkspaceAccess, assignment_id: uuid.UUID, ends_at: datetime, reason: str | None
) -> None:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    assignment = await _locked_assignment(access, assignment_id)
    if assignment.role != "temporary" or assignment.valid_to is None:
        raise ApiError(409, "not_temporary", "Only temporary coverage can be extended.")
    if ends_at <= assignment.valid_to:
        raise ApiError(422, "invalid_extension", "The new end must be later than the current end.")
    assignment.valid_to = ends_at
    await _flush_assignments(access)
    _record_change(access, assignment, "extended", reason)


async def ownership_history(
    access: WorkspaceAccess, responsibility_id: uuid.UUID
) -> list[ChangeView]:
    await _get_responsibility(access, responsibility_id)
    rows = (
        await access.session.execute(
            select(OwnershipAssignmentChange, OwnershipAssignment)
            .join(
                OwnershipAssignment,
                OwnershipAssignment.id == OwnershipAssignmentChange.assignment_id,
            )
            .where(
                OwnershipAssignmentChange.responsibility_id == responsibility_id,
                visible(
                    access, Permission.RESPONSIBILITY_READ, OwnershipAssignmentChange.tenant_id
                ),
            )
            .order_by(
                OwnershipAssignmentChange.changed_at.desc(), OwnershipAssignmentChange.id.desc()
            )
        )
    ).all()
    assignees = await assignee_views(access.session, [a for _, a in rows])
    return [
        ChangeView(
            id=c.id,
            assignment_id=c.assignment_id,
            change_type=c.change_type,
            role=a.role,
            assignee=assignees[a.person_id or a.team_id],  # type: ignore[index]
            valid_from=c.valid_from,
            valid_to=c.valid_to,
            reason=c.reason,
            changed_by=c.changed_by,
            changed_at=c.changed_at,
        )
        for c, a in rows
    ]
