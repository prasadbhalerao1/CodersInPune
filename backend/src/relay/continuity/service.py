"""Continuity case engine: transfer, temporary coverage and light departure.

Lifecycle (backend-enforced, each transition under a row lock on the case):

    draft --submit--> planning --execute--> executing --complete--> completed
      \\__________cancel_________/

- Scope, recipients and dates may change in draft/planning; each change bumps
  `plan_version`, so an approval given against an earlier version no longer counts.
- `execute` needs an approval of the current version (critical cases: the approver must
  not be the initiator unless a separation-of-duties exception is recorded). It applies
  every ownership change in one transaction through the catalog's valid-time operations;
  future effective dates simply create future-dated assignments.
- `complete` needs every mandatory readiness criterion met or waived. Coverage cases
  completed before their end date end the cover early (early return).
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

import procrastinate
from pydantic import AwareDatetime, BaseModel, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.audit.models import AuditEvent
from relay.catalog import service as catalog
from relay.catalog.models import OwnershipAssignment, Responsibility
from relay.continuity.models import (
    CaseApproval,
    CaseReadinessCriterion,
    CaseScopeItem,
    CaseTask,
    ContinuityCase,
)
from relay.directory.models import Person, Team
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.notifications import service as notifications
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.shared.api_types import LongText, Name, StrictInput
from relay.shared.errors import ApiError

CaseType = Literal["transfer", "coverage", "departure"]
CriterionType = Literal[
    "attestation",
    "task_completed",
    "artefact_linked",
    "supervised_demo",
    "access_confirmed",
    "qa_reviewed",
]
EDITABLE = ("draft", "planning")
OPEN = ("draft", "planning", "executing")


# ---------------------------------------------------------------- requests


class CaseIn(StrictInput):
    case_type: CaseType
    title: Name
    reason: LongText | None = None
    affected_person_id: uuid.UUID | None = None
    starts_at: AwareDatetime
    ends_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _shape(self) -> CaseIn:
        if self.case_type != "transfer" and self.affected_person_id is None:
            raise ValueError("coverage and departure cases need the affected person")
        if (self.case_type == "coverage") != (self.ends_at is not None):
            raise ValueError("coverage cases (and only coverage cases) need an end date")
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class CaseUpdate(StrictInput):
    title: Name | None = None
    reason: LongText | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None


class ScopeItemIn(StrictInput):
    responsibility_id: uuid.UUID
    role: Literal["primary", "co_owner", "backup"] = "primary"


class ScopeItemUpdate(StrictInput):
    recipient_person_id: uuid.UUID | None = None
    recipient_team_id: uuid.UUID | None = None
    handover_notes: LongText | None = None
    exception_reason: LongText | None = None


class TaskIn(StrictInput):
    title: Name
    description: LongText | None = None
    assignee_user_id: uuid.UUID | None = None
    due_at: AwareDatetime | None = None
    scope_item_id: uuid.UUID | None = None


class TaskUpdate(StrictInput):
    status: Literal["open", "done", "cancelled"]


class CriterionIn(StrictInput):
    criterion_type: CriterionType
    title: Name
    mandatory: bool = True
    scope_item_id: uuid.UUID | None = None


class CriterionUpdate(StrictInput):
    status: Literal["pending", "met", "blocked", "waived"]
    note: LongText | None = None


class DecisionIn(StrictInput):
    decision: Literal["approved", "rejected"]
    comment: LongText | None = None
    sod_exception_reason: LongText | None = None


class ExtendIn(StrictInput):
    ends_at: AwareDatetime


class EmergencyIn(StrictInput):
    emergency: bool
    reason: LongText | None = None


# ---------------------------------------------------------------- views


class RecipientView(BaseModel):
    type: Literal["person", "team"]
    id: uuid.UUID
    name: str


class ScopeItemView(BaseModel):
    id: uuid.UUID
    responsibility_id: uuid.UUID
    responsibility_name: str
    criticality: str
    role: str
    current_owner_name: str | None
    recipient: RecipientView | None
    handover_notes: str | None
    exception_reason: str | None
    state: str


class TaskView(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    scope_item_id: uuid.UUID | None
    title: str
    description: str | None
    assignee_user_id: uuid.UUID | None
    assignee_name: str | None
    due_at: datetime | None
    status: str
    overdue: bool
    completed_at: datetime | None


class CriterionView(BaseModel):
    id: uuid.UUID
    scope_item_id: uuid.UUID | None
    criterion_type: str
    title: str
    mandatory: bool
    status: str
    note: str | None
    resolved_at: datetime | None


class ApprovalView(BaseModel):
    id: uuid.UUID
    plan_version: int
    decision: str
    comment: str | None
    sod_exception_reason: str | None
    approver_user_id: uuid.UUID
    approver_name: str | None
    decided_at: datetime
    current: bool


class HistoryView(BaseModel):
    occurred_at: datetime
    action: str
    actor_name: str | None
    details: dict[str, str | int | bool | None]


class CaseSummary(BaseModel):
    id: uuid.UUID
    case_type: str
    title: str
    status: str
    outcome: str | None
    affected_person_name: str | None
    starts_at: datetime
    ends_at: datetime | None
    scope_count: int
    open_tasks: int
    overdue_tasks: int
    emergency: bool
    emergency_reason: str | None
    updated_at: datetime


class CaseDetail(CaseSummary):
    reason: str | None
    plan_version: int
    initiator_user_id: uuid.UUID
    coordinator_user_id: uuid.UUID
    coordinator_name: str | None
    critical: bool
    approved: bool
    readiness_met: int
    readiness_total: int
    readiness_blocked: int
    allowed_actions: list[str]
    scope: list[ScopeItemView]
    tasks: list[TaskView]
    criteria: list[CriterionView]
    approvals: list[ApprovalView]


class MyWorkView(BaseModel):
    emergencies: list[CaseSummary]
    tasks: list[TaskView]
    approvals: list[CaseSummary]
    attention: list[CaseSummary]


# ---------------------------------------------------------------- helpers


def _now() -> datetime:
    return datetime.now(UTC)


async def _member_names(access: WorkspaceAccess) -> dict[uuid.UUID, str]:
    rows = await access.session.execute(
        select(Membership.user_id, Membership.display_name, Membership.email).where(
            visible(access, Permission.MEMBER_READ, Membership.tenant_id)
        )
    )
    return {user_id: name or email or "Member" for user_id, name, email in rows}


async def _load(
    access: WorkspaceAccess, case_id: uuid.UUID, *, lock: bool = False
) -> ContinuityCase:
    stmt = select(ContinuityCase).where(
        ContinuityCase.id == case_id,
        visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
    )
    case = await access.session.scalar(stmt.with_for_update() if lock else stmt)
    if case is None:
        raise ApiError(404, "case_not_found", "Case not found.")
    return case


async def _for_change(
    access: WorkspaceAccess, case_id: uuid.UUID, statuses: tuple[str, ...]
) -> ContinuityCase:
    authorize(access, Permission.CASE_MANAGE)
    case = await _load(access, case_id, lock=True)
    if case.status not in statuses:
        raise ApiError(409, "invalid_state", f"Not possible while the case is {case.status}.")
    return case


def _record(
    access: WorkspaceAccess, case: ContinuityCase, action: str, **details: str | int | None
) -> None:
    case.updated_at = func.now()
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=action,
        actor_user_id=access.user_id,
        target_type="continuity_case",
        target_id=case.id,
        details=details,
    )


def _plan_changed(case: ContinuityCase) -> None:
    case.plan_version += 1


async def _notify_case_update(
    access: WorkspaceAccess, jobs: procrastinate.App, case: ContinuityCase, detail: str
) -> None:
    """Tell the people running the case: coordinator, initiator and task assignees."""
    assignees = await access.session.scalars(
        select(CaseTask.assignee_user_id).where(
            CaseTask.case_id == case.id,
            CaseTask.status == "open",
            CaseTask.assignee_user_id.is_not(None),
        )
    )
    recipients = {case.coordinator_user_id, case.initiator_user_id, *(a for a in assignees if a)}
    await notifications.request(
        access.session,
        jobs,
        tenant_id=access.tenant_id,
        kind="case_update",
        case_id=case.id,
        recipients=sorted(recipients),
        actor_user_id=access.user_id,
        detail=detail,
        dedupe=f"case_update:{case.id}:{detail}:{case.plan_version}",
    )


async def _scope(session: AsyncSession, case_id: uuid.UUID) -> list[CaseScopeItem]:
    return list(
        await session.scalars(
            select(CaseScopeItem)
            .where(CaseScopeItem.case_id == case_id)
            .order_by(CaseScopeItem.created_at)
        )
    )


async def _current_assignment(
    access: WorkspaceAccess,
    responsibility_id: uuid.UUID,
    role: str,
    holder: uuid.UUID | None = None,
) -> OwnershipAssignment | None:
    stmt = select(OwnershipAssignment).where(
        OwnershipAssignment.responsibility_id == responsibility_id,
        OwnershipAssignment.role == role,
        catalog.active_at(_now()),
    )
    if holder is not None:
        stmt = stmt.where(OwnershipAssignment.person_id == holder)
    return await access.session.scalar(stmt.limit(1))


async def _require_member(access: WorkspaceAccess, user_id: uuid.UUID) -> None:
    found = await access.session.scalar(
        select(Membership.id).where(Membership.user_id == user_id, Membership.status == "active")
    )
    if found is None:
        raise ApiError(
            422, "assignee_not_member", "Tasks can only be assigned to workspace members."
        )


def _default_criteria(
    case: ContinuityCase, item: CaseScopeItem, name: str
) -> CaseReadinessCriterion:
    if case.case_type == "coverage":
        kind, title = "access_confirmed", f"Cover has the access needed for “{name}”"
    else:
        kind, title = "attestation", f"Recipient confirms the handover of “{name}”"
    return CaseReadinessCriterion(
        tenant_id=case.tenant_id,
        case_id=case.id,
        scope_item_id=item.id,
        criterion_type=kind,
        title=title,
    )


# ---------------------------------------------------------------- commands


async def create_case(access: WorkspaceAccess, data: CaseIn) -> CaseDetail:
    authorize(access, Permission.CASE_MANAGE)
    if data.affected_person_id is not None:
        person = await access.session.scalar(
            select(Person).where(
                Person.id == data.affected_person_id,
                visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
            )
        )
        if person is None:
            raise ApiError(422, "person_not_found", "That person does not exist.")
    case = ContinuityCase(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        case_type=data.case_type,
        title=data.title,
        reason=data.reason or None,
        affected_person_id=data.affected_person_id,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        initiator_user_id=access.user_id,
        coordinator_user_id=access.user_id,
    )
    access.session.add(case)
    await access.session.flush()
    # Departure/coverage: discover the person's current ownership from the catalogue.
    if data.affected_person_id is not None:
        roles = (
            ("primary", "co_owner")
            if data.case_type == "coverage"
            else ("primary", "co_owner", "backup")
        )
        held = await access.session.scalars(
            select(OwnershipAssignment)
            .join(Responsibility, Responsibility.id == OwnershipAssignment.responsibility_id)
            .where(
                OwnershipAssignment.person_id == data.affected_person_id,
                OwnershipAssignment.role.in_(roles),
                Responsibility.status == "active",
                catalog.active_at(_now()),
            )
        )
        access.session.add_all(
            CaseScopeItem(
                tenant_id=access.tenant_id,
                case_id=case.id,
                responsibility_id=a.responsibility_id,
                role=a.role,
                current_assignment_id=a.id,
            )
            for a in held
        )
    _record(access, case, "case.created", case_type=data.case_type)
    return await get_case(access, case.id)


async def update_case(access: WorkspaceAccess, case_id: uuid.UUID, data: CaseUpdate) -> CaseDetail:
    case = await _for_change(access, case_id, EDITABLE)
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(case, field, value)
    if case.case_type == "coverage" and (case.ends_at is None or case.ends_at <= case.starts_at):
        raise ApiError(422, "invalid_range", "Coverage must end after it starts.")
    if case.case_type != "coverage" and case.ends_at is not None:
        raise ApiError(422, "invalid_range", "Only coverage cases have an end date.")
    if {"starts_at", "ends_at"} & changes.keys():
        _plan_changed(case)
    _record(access, case, "case.updated", fields=",".join(sorted(changes)))
    return await get_case(access, case_id)


async def add_scope_item(
    access: WorkspaceAccess, case_id: uuid.UUID, data: ScopeItemIn
) -> CaseDetail:
    case = await _for_change(access, case_id, EDITABLE)
    responsibility = await access.session.scalar(
        select(Responsibility).where(
            Responsibility.id == data.responsibility_id,
            visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
            Responsibility.status == "active",
        )
    )
    if responsibility is None:
        raise ApiError(422, "responsibility_not_found", "That responsibility is not active.")
    exists = await access.session.scalar(
        select(CaseScopeItem.id).where(
            CaseScopeItem.case_id == case_id,
            CaseScopeItem.responsibility_id == data.responsibility_id,
        )
    )
    if exists:
        raise ApiError(409, "already_in_scope", "That responsibility is already in this case.")
    current = await _current_assignment(
        access, data.responsibility_id, data.role, case.affected_person_id
    )
    access.session.add(
        CaseScopeItem(
            tenant_id=access.tenant_id,
            case_id=case_id,
            responsibility_id=data.responsibility_id,
            role=data.role,
            current_assignment_id=current.id if current else None,
        )
    )
    _plan_changed(case)
    _record(access, case, "case.scope_added", responsibility_id=str(data.responsibility_id))
    return await get_case(access, case_id)


async def update_scope_item(
    access: WorkspaceAccess, case_id: uuid.UUID, item_id: uuid.UUID, data: ScopeItemUpdate
) -> CaseDetail:
    case = await _for_change(access, case_id, EDITABLE)
    item = await access.session.get(CaseScopeItem, item_id, with_for_update=True)
    if item is None or item.case_id != case_id:
        raise ApiError(404, "scope_item_not_found", "Scope item not found.")
    changes = data.model_dump(exclude_unset=True)
    if "recipient_person_id" in changes or "recipient_team_id" in changes:
        person_id, team_id = changes.get("recipient_person_id"), changes.get("recipient_team_id")
        if person_id and team_id:
            raise ApiError(422, "one_recipient", "Choose a person or a team, not both.")
        if person_id or team_id:
            await catalog.require_assignee(
                access, catalog.Assignee(person_id=person_id, team_id=team_id)
            )
        item.recipient_person_id, item.recipient_team_id = person_id, team_id
    if "handover_notes" in changes:
        item.handover_notes = changes["handover_notes"] or None
    if "exception_reason" in changes:
        item.exception_reason = changes["exception_reason"] or None
    _plan_changed(case)
    _record(
        access,
        case,
        "case.scope_updated",
        scope_item_id=str(item_id),
        fields=",".join(sorted(changes)),
    )
    return await get_case(access, case_id)


async def remove_scope_item(
    access: WorkspaceAccess, case_id: uuid.UUID, item_id: uuid.UUID
) -> CaseDetail:
    case = await _for_change(access, case_id, EDITABLE)
    item = await access.session.get(CaseScopeItem, item_id)
    if item is None or item.case_id != case_id:
        raise ApiError(404, "scope_item_not_found", "Scope item not found.")
    for criterion in await access.session.scalars(
        select(CaseReadinessCriterion).where(CaseReadinessCriterion.scope_item_id == item_id)
    ):
        await access.session.delete(criterion)
    await access.session.execute(
        update(CaseTask).where(CaseTask.scope_item_id == item_id).values(scope_item_id=None)
    )
    await access.session.delete(item)
    _plan_changed(case)
    _record(access, case, "case.scope_removed", responsibility_id=str(item.responsibility_id))
    return await get_case(access, case_id)


async def submit_case(
    access: WorkspaceAccess, case_id: uuid.UUID, jobs: procrastinate.App
) -> CaseDetail:
    case = await _for_change(access, case_id, ("draft",))
    items = await _scope(access.session, case_id)
    if not items:
        raise ApiError(409, "empty_scope", "Add at least one responsibility first.")
    unresolved = [
        i for i in items if not (i.recipient_person_id or i.recipient_team_id or i.exception_reason)
    ]
    if unresolved:
        raise ApiError(
            409, "recipients_missing", "Every responsibility needs a recipient or an exception."
        )
    names = dict(
        (
            await access.session.execute(
                select(Responsibility.id, Responsibility.name).where(
                    Responsibility.id.in_([i.responsibility_id for i in items])
                )
            )
        ).all()
    )
    access.session.add_all(
        _default_criteria(case, i, names[i.responsibility_id])
        for i in items
        if not i.exception_reason
    )
    case.status = "planning"
    _record(access, case, "case.submitted", plan_version=case.plan_version)
    await notifications.request(
        access.session,
        jobs,
        tenant_id=access.tenant_id,
        kind="approval_requested",
        case_id=case.id,
        audience="approvers",
        actor_user_id=access.user_id,
        dedupe=f"approval_requested:{case.id}:{case.plan_version}",
    )
    return await get_case(access, case_id)


async def decide(
    access: WorkspaceAccess, case_id: uuid.UUID, data: DecisionIn, jobs: procrastinate.App
) -> CaseDetail:
    authorize(access, Permission.CASE_APPROVE)
    case = await _load(access, case_id, lock=True)
    if case.status != "planning":
        raise ApiError(409, "invalid_state", "Only cases in planning can be approved.")
    sod_reason = None
    if (
        data.decision == "approved"
        and access.user_id == case.initiator_user_id
        and await _is_critical(access, case_id)
    ):
        if not data.sod_exception_reason:
            raise ApiError(
                409,
                "separation_of_duties",
                "Critical cases need an approver other than the initiator, "
                "or a recorded separation-of-duties exception.",
            )
        sod_reason = data.sod_exception_reason
    access.session.add(
        CaseApproval(
            tenant_id=access.tenant_id,
            case_id=case_id,
            plan_version=case.plan_version,
            decision=data.decision,
            comment=data.comment or None,
            sod_exception_reason=sod_reason,
            approver_user_id=access.user_id,
        )
    )
    _record(
        access,
        case,
        f"case.{data.decision}",
        plan_version=case.plan_version,
        sod_exception=sod_reason is not None,
    )
    await _notify_case_update(access, jobs, case, data.decision)
    return await get_case(access, case_id)


async def execute_case(
    access: WorkspaceAccess, case_id: uuid.UUID, jobs: procrastinate.App
) -> CaseDetail:
    """Apply every ownership change in one transaction. Retries are safe: the status guard
    (under the case row lock) lets exactly one execution through."""
    case = await _for_change(access, case_id, ("planning",))
    if not await _current_approval(access.session, case):
        raise ApiError(409, "approval_required", "The current plan needs an approval first.")
    at = max(case.starts_at, _now())
    reason = f"Continuity case: {case.title}"
    for item in await _scope(access.session, case_id):
        if item.exception_reason:
            item.state = "excepted"
            continue
        recipient = catalog.Assignee(
            person_id=item.recipient_person_id, team_id=item.recipient_team_id
        )
        if case.case_type == "coverage":
            assert case.ends_at is not None
            applied = await catalog.start_cover(
                access, item.responsibility_id, recipient, at, case.ends_at, reason
            )
        else:
            applied = await catalog.handover(
                access,
                item.responsibility_id,
                item.role,
                recipient,
                at,
                reason,
                from_assignment_id=item.current_assignment_id,
            )
        item.applied_assignment_id = applied.id
        item.state = "applied"
    case.status = "executing"
    _record(access, case, "case.executed", effective_at=at.isoformat())
    await _notify_case_update(access, jobs, case, "executing")
    return await get_case(access, case_id)


async def extend_coverage(
    access: WorkspaceAccess, case_id: uuid.UUID, data: ExtendIn
) -> CaseDetail:
    case = await _for_change(access, case_id, ("executing",))
    if case.case_type != "coverage" or case.ends_at is None or data.ends_at <= case.ends_at:
        raise ApiError(422, "invalid_extension", "Coverage can only be extended to a later date.")
    for item in await _scope(access.session, case_id):
        if item.applied_assignment_id:
            await catalog.extend_cover(
                access, item.applied_assignment_id, data.ends_at, "Coverage extended"
            )
    case.ends_at = data.ends_at
    _record(access, case, "case.extended", ends_at=data.ends_at.isoformat())
    return await get_case(access, case_id)


async def complete_case(
    access: WorkspaceAccess, case_id: uuid.UUID, jobs: procrastinate.App
) -> CaseDetail:
    case = await _for_change(access, case_id, ("executing",))
    criteria = list(
        await access.session.scalars(
            select(CaseReadinessCriterion).where(CaseReadinessCriterion.case_id == case_id)
        )
    )
    if any(c.mandatory and c.status not in ("met", "waived") for c in criteria):
        raise ApiError(
            409, "readiness_incomplete", "Resolve or waive every mandatory readiness check."
        )
    now = _now()
    if case.case_type != "coverage" and case.starts_at > now:
        raise ApiError(
            409, "not_yet_effective", "The transfer takes effect later; complete it then."
        )
    if case.case_type == "coverage" and case.ends_at and case.ends_at > now:
        # Early return: shorten the cover; the original owners were never changed.
        for item in await _scope(access.session, case_id):
            if item.applied_assignment_id:
                await catalog.end_assignment_at(
                    access, item.applied_assignment_id, now, "Early return"
                )
        case.ends_at = now
    items = await _scope(access.session, case_id)
    approvals = await _approvals(access.session, case_id)
    exceptions = (
        any(i.state == "excepted" for i in items)
        or any(c.status == "waived" for c in criteria)
        or any(a.sod_exception_reason for a in approvals if a.plan_version == case.plan_version)
    )
    case.status = "completed"
    case.outcome = "completed_with_exceptions" if exceptions else "completed"
    case.closed_at = func.now()
    _record(access, case, "case.completed", outcome=case.outcome)
    await _notify_case_update(access, jobs, case, "completed")
    return await get_case(access, case_id)


async def cancel_case(
    access: WorkspaceAccess, case_id: uuid.UUID, jobs: procrastinate.App
) -> CaseDetail:
    case = await _for_change(access, case_id, EDITABLE)
    case.status, case.outcome, case.closed_at = "cancelled", "cancelled", func.now()
    _record(access, case, "case.cancelled")
    await _notify_case_update(access, jobs, case, "cancelled")
    return await get_case(access, case_id)


async def add_task(
    access: WorkspaceAccess, case_id: uuid.UUID, data: TaskIn, jobs: procrastinate.App
) -> CaseDetail:
    case = await _for_change(access, case_id, OPEN)
    if data.assignee_user_id:
        await _require_member(access, data.assignee_user_id)
    task = CaseTask(
        tenant_id=access.tenant_id,
        case_id=case_id,
        scope_item_id=data.scope_item_id,
        title=data.title,
        description=data.description or None,
        assignee_user_id=data.assignee_user_id,
        due_at=data.due_at,
        created_by=access.user_id,
    )
    access.session.add(task)
    await access.session.flush()
    _record(access, case, "case.task_added", task_id=str(task.id))
    await notifications.request_task_notifications(access.session, jobs, task, access.user_id)
    return await get_case(access, case_id)


async def update_task(
    access: WorkspaceAccess, case_id: uuid.UUID, task_id: uuid.UUID, data: TaskUpdate
) -> CaseDetail:
    authorize(access, Permission.CASE_READ)
    case = await _load(access, case_id, lock=True)
    task = await access.session.get(CaseTask, task_id, with_for_update=True)
    if task is None or task.case_id != case_id:
        raise ApiError(404, "task_not_found", "Task not found.")
    # Assignees may update their own tasks; otherwise managing the case is required.
    if task.assignee_user_id != access.user_id:
        authorize(access, Permission.CASE_MANAGE)
    if case.status not in OPEN:
        raise ApiError(409, "invalid_state", "The case is closed.")
    task.status = data.status
    task.completed_at = func.now() if data.status == "done" else None
    task.completed_by = access.user_id if data.status == "done" else None
    _record(access, case, "case.task_updated", task_id=str(task_id), status=data.status)
    return await get_case(access, case_id)


async def add_criterion(
    access: WorkspaceAccess, case_id: uuid.UUID, data: CriterionIn
) -> CaseDetail:
    case = await _for_change(access, case_id, OPEN)
    access.session.add(
        CaseReadinessCriterion(
            tenant_id=access.tenant_id,
            case_id=case_id,
            scope_item_id=data.scope_item_id,
            criterion_type=data.criterion_type,
            title=data.title,
            mandatory=data.mandatory,
        )
    )
    _record(access, case, "case.criterion_added", criterion_type=data.criterion_type)
    return await get_case(access, case_id)


async def update_criterion(
    access: WorkspaceAccess, case_id: uuid.UUID, criterion_id: uuid.UUID, data: CriterionUpdate
) -> CaseDetail:
    case = await _for_change(access, case_id, OPEN)
    criterion = await access.session.get(CaseReadinessCriterion, criterion_id, with_for_update=True)
    if criterion is None or criterion.case_id != case_id:
        raise ApiError(404, "criterion_not_found", "Readiness check not found.")
    if data.status == "waived" and not data.note:
        raise ApiError(422, "waiver_reason_required", "Waiving a readiness check needs a reason.")
    criterion.status = data.status
    criterion.note = data.note or None
    criterion.resolved_by = access.user_id if data.status in ("met", "waived") else None
    criterion.resolved_at = func.now() if data.status in ("met", "waived") else None
    _record(
        access, case, "case.criterion_updated", criterion_id=str(criterion_id), status=data.status
    )
    return await get_case(access, case_id)


async def set_emergency(
    access: WorkspaceAccess, case_id: uuid.UUID, data: EmergencyIn, jobs: procrastinate.App
) -> CaseDetail:
    """Raises visibility only: approvals, readiness and ownership rules are unchanged."""
    case = await _for_change(access, case_id, OPEN)
    if data.emergency and not data.reason:
        raise ApiError(422, "reason_required", "Say why this case is an emergency.")
    if case.emergency == data.emergency:
        raise ApiError(409, "unchanged", "The case already has that emergency status.")
    case.emergency = data.emergency
    case.emergency_reason = data.reason if data.emergency else None
    _record(access, case, "case.emergency_raised" if data.emergency else "case.emergency_cleared")
    if data.emergency:
        await notifications.request(
            access.session,
            jobs,
            tenant_id=access.tenant_id,
            kind="case_update",
            case_id=case.id,
            audience="approvers",
            recipients=[case.coordinator_user_id],
            actor_user_id=access.user_id,
            detail="emergency",
            dedupe=f"emergency:{case.id}:{uuid.uuid7()}",
        )
    return await get_case(access, case_id)


# ---------------------------------------------------------------- reads


async def _approvals(session: AsyncSession, case_id: uuid.UUID) -> list[CaseApproval]:
    return list(
        await session.scalars(
            select(CaseApproval)
            .where(CaseApproval.case_id == case_id)
            .order_by(CaseApproval.decided_at.desc())
        )
    )


async def _current_approval(session: AsyncSession, case: ContinuityCase) -> bool:
    """The latest decision on the current plan version is an approval."""
    latest = await session.scalar(
        select(CaseApproval.decision)
        .where(CaseApproval.case_id == case.id, CaseApproval.plan_version == case.plan_version)
        .order_by(CaseApproval.decided_at.desc(), CaseApproval.id.desc())
        .limit(1)
    )
    return latest == "approved"


async def _is_critical(access: WorkspaceAccess, case_id: uuid.UUID) -> bool:
    found = await access.session.scalar(
        select(CaseScopeItem.id)
        .join(Responsibility, Responsibility.id == CaseScopeItem.responsibility_id)
        .where(CaseScopeItem.case_id == case_id, Responsibility.criticality == "critical")
        .limit(1)
    )
    return found is not None


def _task_view(t: CaseTask, names: dict[uuid.UUID, str], now: datetime) -> TaskView:
    return TaskView(
        id=t.id,
        case_id=t.case_id,
        scope_item_id=t.scope_item_id,
        title=t.title,
        description=t.description,
        assignee_user_id=t.assignee_user_id,
        assignee_name=names.get(t.assignee_user_id) if t.assignee_user_id else None,
        due_at=t.due_at,
        status=t.status,
        overdue=t.status == "open" and t.due_at is not None and t.due_at < now,
        completed_at=t.completed_at,
    )


def _allowed_actions(access: WorkspaceAccess, case: ContinuityCase, approved: bool) -> list[str]:
    manage = role_allows(access.role, Permission.CASE_MANAGE)
    approve = role_allows(access.role, Permission.CASE_APPROVE)
    actions: list[str] = []
    if manage and case.status in EDITABLE:
        actions += ["edit", "cancel"]
    if manage and case.status == "draft":
        actions.append("submit")
    if approve and case.status == "planning":
        actions.append("decide")
    if manage and case.status == "planning" and approved:
        actions.append("execute")
    if manage and case.status == "executing":
        actions.append("complete")
        if case.case_type == "coverage":
            actions.append("extend")
    if manage and case.status in OPEN:
        actions += ["add_task", "add_criterion", "set_emergency"]
    if role_allows(access.role, Permission.CASE_COMMENT):
        actions.append("comment")
    return actions


async def _summaries(access: WorkspaceAccess, cases: list[ContinuityCase]) -> list[CaseSummary]:
    ids = [c.id for c in cases]
    now = _now()
    scope_counts = dict(
        (
            await access.session.execute(
                select(CaseScopeItem.case_id, func.count())
                .where(CaseScopeItem.case_id.in_(ids))
                .group_by(CaseScopeItem.case_id)
            )
        ).all()
    )
    tasks = list(
        await access.session.scalars(
            select(CaseTask).where(CaseTask.case_id.in_(ids), CaseTask.status == "open")
        )
    )
    people = dict(
        (
            await access.session.execute(
                select(Person.id, Person.display_name).where(
                    Person.id.in_([c.affected_person_id for c in cases if c.affected_person_id])
                )
            )
        ).all()
    )
    return [
        CaseSummary(
            id=c.id,
            case_type=c.case_type,
            title=c.title,
            status=c.status,
            outcome=c.outcome,
            affected_person_name=people.get(c.affected_person_id) if c.affected_person_id else None,
            starts_at=c.starts_at,
            ends_at=c.ends_at,
            scope_count=scope_counts.get(c.id, 0),
            open_tasks=sum(1 for t in tasks if t.case_id == c.id),
            overdue_tasks=sum(
                1 for t in tasks if t.case_id == c.id and t.due_at and t.due_at < now
            ),
            emergency=c.emergency,
            emergency_reason=c.emergency_reason,
            updated_at=c.updated_at,
        )
        for c in cases
    ]


async def list_cases(access: WorkspaceAccess, *, status: str | None = None) -> list[CaseSummary]:
    authorize(access, Permission.CASE_READ)
    stmt = select(ContinuityCase).where(
        visible(access, Permission.CASE_READ, ContinuityCase.tenant_id)
    )
    if status == "open":
        stmt = stmt.where(ContinuityCase.status.in_(OPEN))
    elif status == "closed":
        stmt = stmt.where(ContinuityCase.status.in_(("completed", "cancelled")))
    cases = list(
        await access.session.scalars(
            stmt.order_by(ContinuityCase.emergency.desc(), ContinuityCase.updated_at.desc()).limit(
                200
            )
        )
    )
    return await _summaries(access, cases)


async def get_case(access: WorkspaceAccess, case_id: uuid.UUID) -> CaseDetail:
    authorize(access, Permission.CASE_READ)
    await access.session.flush()
    case = await _load(access, case_id)
    await access.session.refresh(case)
    summary = (await _summaries(access, [case]))[0]
    items = await _scope(access.session, case_id)
    responsibilities = {
        r.id: r
        for r in await access.session.scalars(
            select(Responsibility).where(
                Responsibility.id.in_([i.responsibility_id for i in items])
            )
        )
    }
    current = {
        a.id: a
        for a in await access.session.scalars(
            select(OwnershipAssignment).where(
                OwnershipAssignment.id.in_(
                    [i.current_assignment_id for i in items if i.current_assignment_id]
                )
            )
        )
    }
    holder_views = await catalog.assignee_views(access.session, list(current.values()))
    person_names = dict(
        (
            await access.session.execute(
                select(Person.id, Person.display_name).where(
                    Person.id.in_([i.recipient_person_id for i in items if i.recipient_person_id])
                )
            )
        ).all()
    )
    team_names = dict(
        (
            await access.session.execute(
                select(Team.id, Team.name).where(
                    Team.id.in_([i.recipient_team_id for i in items if i.recipient_team_id])
                )
            )
        ).all()
    )
    names = await _member_names(access)
    now = _now()
    tasks = list(
        await access.session.scalars(
            select(CaseTask).where(CaseTask.case_id == case_id).order_by(CaseTask.created_at)
        )
    )
    criteria = list(
        await access.session.scalars(
            select(CaseReadinessCriterion)
            .where(CaseReadinessCriterion.case_id == case_id)
            .order_by(CaseReadinessCriterion.created_at)
        )
    )
    approvals = await _approvals(access.session, case_id)
    approved = await _current_approval(access.session, case)

    def recipient(i: CaseScopeItem) -> RecipientView | None:
        if i.recipient_person_id:
            return RecipientView(
                type="person",
                id=i.recipient_person_id,
                name=person_names.get(i.recipient_person_id, "Unknown"),
            )
        if i.recipient_team_id:
            return RecipientView(
                type="team",
                id=i.recipient_team_id,
                name=team_names.get(i.recipient_team_id, "Unknown"),
            )
        return None

    def owner_name(i: CaseScopeItem) -> str | None:
        a = current.get(i.current_assignment_id) if i.current_assignment_id else None
        return holder_views[a.person_id or a.team_id].name if a else None  # type: ignore[index]

    mandatory = [c for c in criteria if c.mandatory]
    return CaseDetail(
        **summary.model_dump(),
        reason=case.reason,
        plan_version=case.plan_version,
        initiator_user_id=case.initiator_user_id,
        coordinator_user_id=case.coordinator_user_id,
        coordinator_name=names.get(case.coordinator_user_id),
        critical=any(r.criticality == "critical" for r in responsibilities.values()),
        approved=approved,
        readiness_met=sum(1 for c in mandatory if c.status in ("met", "waived")),
        readiness_total=len(mandatory),
        readiness_blocked=sum(1 for c in criteria if c.status == "blocked"),
        allowed_actions=_allowed_actions(access, case, approved),
        scope=[
            ScopeItemView(
                id=i.id,
                responsibility_id=i.responsibility_id,
                responsibility_name=responsibilities[i.responsibility_id].name,
                criticality=responsibilities[i.responsibility_id].criticality,
                role=i.role,
                current_owner_name=owner_name(i),
                recipient=recipient(i),
                handover_notes=i.handover_notes,
                exception_reason=i.exception_reason,
                state=i.state,
            )
            for i in items
        ],
        tasks=[_task_view(t, names, now) for t in tasks],
        criteria=[
            CriterionView(
                id=c.id,
                scope_item_id=c.scope_item_id,
                criterion_type=c.criterion_type,
                title=c.title,
                mandatory=c.mandatory,
                status=c.status,
                note=c.note,
                resolved_at=c.resolved_at,
            )
            for c in criteria
        ],
        approvals=[
            ApprovalView(
                id=a.id,
                plan_version=a.plan_version,
                decision=a.decision,
                comment=a.comment,
                sod_exception_reason=a.sod_exception_reason,
                approver_user_id=a.approver_user_id,
                approver_name=names.get(a.approver_user_id),
                decided_at=a.decided_at,
                current=a.plan_version == case.plan_version,
            )
            for a in approvals
        ],
    )


async def case_history(access: WorkspaceAccess, case_id: uuid.UUID) -> list[HistoryView]:
    authorize(access, Permission.CASE_READ)
    await _load(access, case_id)
    names = await _member_names(access)
    events = await access.session.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.target_type == "continuity_case",
            AuditEvent.target_id == case_id,
            visible(access, Permission.CASE_READ, AuditEvent.tenant_id),
        )
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
    )
    return [
        HistoryView(
            occurred_at=e.occurred_at,
            action=e.action,
            actor_name=names.get(e.actor_user_id) if e.actor_user_id else "System",
            details=e.details,
        )
        for e in events
    ]


async def my_work(access: WorkspaceAccess) -> MyWorkView:
    authorize(access, Permission.CASE_READ)
    names = await _member_names(access)
    now = _now()
    tasks = list(
        await access.session.scalars(
            select(CaseTask)
            .join(ContinuityCase, ContinuityCase.id == CaseTask.case_id)
            .where(
                visible(access, Permission.CASE_READ, CaseTask.tenant_id),
                CaseTask.assignee_user_id == access.user_id,
                CaseTask.status == "open",
                ContinuityCase.status.in_(OPEN),
            )
            .order_by(CaseTask.due_at.asc().nulls_last(), CaseTask.created_at)
        )
    )
    open_cases = list(
        await access.session.scalars(
            select(ContinuityCase).where(
                visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
                ContinuityCase.status.in_(OPEN),
            )
        )
    )
    pending: list[ContinuityCase] = []
    if role_allows(access.role, Permission.CASE_APPROVE):
        pending = [
            c
            for c in open_cases
            if c.status == "planning" and not await _current_approval(access.session, c)
        ]
    attention = [
        c for c in open_cases if c.coordinator_user_id == access.user_id and c not in pending
    ]
    emergencies = sorted(
        (c for c in open_cases if c.emergency), key=lambda c: c.updated_at, reverse=True
    )
    return MyWorkView(
        emergencies=await _summaries(access, emergencies),
        tasks=[_task_view(t, names, now) for t in tasks],
        approvals=await _summaries(access, pending),
        attention=await _summaries(access, attention),
    )
