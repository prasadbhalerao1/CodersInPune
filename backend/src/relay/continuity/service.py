"""Continuity case engine: transfer, coverage, departure, onboarding and project handover.

Lifecycle: see `continuity.lifecycle` (every status change goes through `lifecycle.move`,
under a row lock on the case, and is recorded with actor, time and reason).

- Scope, recipients and dates may change until execution; each change bumps
  `plan_version`, so an approval given against an earlier version no longer counts (and a
  case awaiting review or ready for transfer drops back to planning).
- Approving the current plan moves the case to ready_for_transfer. Approvers are members
  with case.approve, or the case's delegated approver.
- `execute` needs an approval of the current version (critical cases: the approver must
  not be the initiator unless a separation-of-duties exception is recorded). It applies
  every ownership change in one transaction through the catalog's valid-time operations;
  future effective dates simply create future-dated assignments.
- `complete` needs every mandatory readiness criterion met or waived; for critical cases
  the verifier must be neither the initiator nor the approver (or an exception is recorded).
  Coverage cases completed before their end date end the cover early (early return).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import available_timezones

import procrastinate
from pydantic import AwareDatetime, BaseModel, HttpUrl, model_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.audit.models import AuditEvent
from relay.catalog import service as catalog
from relay.catalog.models import Asset, OwnershipAssignment, Responsibility, ResponsibilityAsset
from relay.continuity import lifecycle
from relay.continuity.models import (
    EXPLAINED,
    OPEN_STATUSES,
    CaseApproval,
    CaseBlocker,
    CaseReadinessCriterion,
    CaseScopeItem,
    CaseStatusChange,
    CaseTask,
    CaseTaskDependency,
    CaseTaskEvent,
    ContinuityCase,
)
from relay.directory.models import Person, Team
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.notifications import service as notifications
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.shared import pagination
from relay.shared.api_types import LongText, Name, StrictInput
from relay.shared.errors import ApiError

CaseType = Literal["transfer", "coverage", "departure", "onboarding", "project_handover"]
Priority = Literal["low", "normal", "high", "urgent"]
CriterionType = Literal[
    "attestation",
    "task_completed",
    "artefact_linked",
    "supervised_demo",
    "access_confirmed",
    "qa_reviewed",
    "rehearsal",
]
CriterionStatus = Literal["pending", "met", "blocked", "waived", "needs_review", "unable_to_assess"]
EDITABLE = lifecycle.EDITABLE
OPEN = OPEN_STATUSES
# Cases that need the person affected; transfers and project handovers may not.
NEEDS_PERSON = ("coverage", "departure", "onboarding")


# ---------------------------------------------------------------- requests


def _check_zone(zone: str | None) -> None:
    if zone is not None and zone not in _ZONES:
        raise ValueError("unknown time zone")


_ZONES = frozenset(available_timezones()) | {"UTC"}


class CaseIn(StrictInput):
    case_type: CaseType
    title: Name
    reason: LongText | None = None
    affected_person_id: uuid.UUID | None = None
    starts_at: AwareDatetime
    ends_at: AwareDatetime | None = None
    priority: Priority = "normal"
    due_at: AwareDatetime | None = None
    time_zone: str = "UTC"
    accountable_manager_user_id: uuid.UUID | None = None
    delegate_approver_user_id: uuid.UUID | None = None
    approval_due_at: AwareDatetime | None = None
    project_asset_id: uuid.UUID | None = None
    # Set when the person creating the case saw a similar open case and proceeds anyway.
    duplicate_override_reason: LongText | None = None

    @model_validator(mode="after")
    def _shape(self) -> CaseIn:
        _check_zone(self.time_zone)
        if self.case_type in NEEDS_PERSON and self.affected_person_id is None:
            raise ValueError("coverage, departure and onboarding cases need the person affected")
        if self.project_asset_id is not None and self.case_type != "project_handover":
            raise ValueError("only project handovers link a project asset")
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
    priority: Priority | None = None
    due_at: AwareDatetime | None = None
    time_zone: str | None = None
    accountable_manager_user_id: uuid.UUID | None = None
    delegate_approver_user_id: uuid.UUID | None = None
    approval_due_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _zone(self) -> CaseUpdate:
        _check_zone(self.time_zone)
        return self


class CompleteIn(StrictInput):
    sod_exception_reason: LongText | None = None


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
    assignee_team_id: uuid.UUID | None = None
    due_at: AwareDatetime | None = None
    scope_item_id: uuid.UUID | None = None
    priority: Priority = "normal"
    depends_on: list[uuid.UUID] = []


class TaskUpdate(StrictInput):
    status: Literal["open", "done", "cancelled"]
    # Completion evidence: what was done and, optionally, where to see it.
    completion_note: LongText | None = None
    completion_url: HttpUrl | None = None
    reason: LongText | None = None


class CriterionIn(StrictInput):
    criterion_type: CriterionType
    title: Name
    mandatory: bool = True
    scope_item_id: uuid.UUID | None = None
    # Rehearsal steps, done under supervision; nothing is executed by Relay.
    checklist: list[Name] = []


class CriterionUpdate(StrictInput):
    status: CriterionStatus
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
    decline_reason: str | None = None
    declined_at: datetime | None = None
    # Restricted and not visible to the viewer: no details beyond its existence.
    hidden: bool = False
    # The signed-in user is the incoming person and may decline the assignment.
    can_decline: bool = False


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
    priority: str = "normal"
    assignee_team_id: uuid.UUID | None = None
    assignee_team_name: str | None = None
    depends_on: list[uuid.UUID] = []
    # Titles of open tasks this one waits for: it can't be completed until they are.
    blocked_by: list[str] = []
    needs_input_from_user_id: uuid.UUID | None = None
    needs_input_from_name: str | None = None
    completion_note: str | None = None
    completion_url: str | None = None
    external_provider: str | None = None
    external_url: str | None = None
    sync_status: str = "not_mirrored"
    case_title: str | None = None


class ChecklistStep(BaseModel):
    step: str
    done: bool = False
    done_by: str | None = None
    done_at: datetime | None = None


class CriterionView(BaseModel):
    id: uuid.UUID
    scope_item_id: uuid.UUID | None
    criterion_type: str
    title: str
    mandatory: bool
    status: str
    note: str | None
    resolved_at: datetime | None
    checklist: list[ChecklistStep] = []


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
    priority: str = "normal"
    due_at: datetime | None = None
    overdue: bool = False
    parent_case_id: uuid.UUID | None = None


class BlockerView(BaseModel):
    id: uuid.UUID
    description: str
    owner_user_id: uuid.UUID | None
    owner_name: str | None
    escalate_at: datetime
    escalation_due: bool
    escalated_at: datetime | None
    resolution: str | None
    resolved_by_name: str | None
    resolved_at: datetime | None
    created_by_name: str | None
    created_at: datetime


class StatusChangeView(BaseModel):
    from_status: str | None
    to_status: str
    reason: str | None
    outcome: str | None
    closed_at: datetime | None
    actor_name: str | None
    changed_at: datetime


class CaseLink(BaseModel):
    id: uuid.UUID
    title: str
    case_type: str
    status: str


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
    # Why readiness is blocked or uncertain, in plain words; empty when nothing is in the way.
    readiness_reasons: list[str] = []
    allowed_actions: list[str]
    scope: list[ScopeItemView]
    tasks: list[TaskView]
    criteria: list[CriterionView]
    approvals: list[ApprovalView]
    time_zone: str = "UTC"
    accountable_manager_user_id: uuid.UUID | None = None
    accountable_manager_name: str | None = None
    delegate_approver_user_id: uuid.UUID | None = None
    delegate_approver_name: str | None = None
    approval_due_at: datetime | None = None
    approval_overdue: bool = False
    project_asset_id: uuid.UUID | None = None
    project_asset_name: str | None = None
    reopen_count: int = 0
    blocked_from: str | None = None
    duplicate_override_reason: str | None = None
    self_requested: bool = False
    activated_at: datetime | None = None
    # Overlapping absences: the same person, or a cover who is away at the same time.
    warnings: list[str] = []
    # Moves a manager may make directly from the current status.
    transitions: list[str] = []
    blockers: list[BlockerView] = []
    status_history: list[StatusChangeView] = []
    duplicates: list[CaseLink] = []
    parent: CaseLink | None = None
    children: list[CaseLink] = []


class MentionView(BaseModel):
    notification_id: uuid.UUID
    case_id: uuid.UUID
    case_title: str
    actor_name: str | None
    created_at: datetime


class ReviewView(BaseModel):
    knowledge_id: uuid.UUID
    title: str
    responsibility_id: uuid.UUID
    responsibility_name: str


class HandoverForMe(BaseModel):
    """An approved handover capsule addressed to me, on a case still in progress."""

    capsule_id: uuid.UUID
    case_id: uuid.UUID
    case_title: str
    status: str  # approved (awaiting my acknowledgement) | acknowledged
    version: int
    updated_at: datetime


class MyWorkView(BaseModel):
    emergencies: list[CaseSummary]
    tasks: list[TaskView]
    approvals: list[CaseSummary]
    attention: list[CaseSummary]
    mentions: list[MentionView] = []
    reviews: list[ReviewView] = []
    # Tasks where someone asked me a question, and my recently completed tasks.
    needs_input: list[TaskView] = []
    completed: list[TaskView] = []
    handovers: list[HandoverForMe] = []


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


def _plan_changed(access: WorkspaceAccess, case: ContinuityCase) -> None:
    case.plan_version += 1
    if case.status in ("awaiting_review", "ready_for_transfer"):
        lifecycle.move(access, case, "planning", "The plan changed after review")


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


async def responsibility_names(
    access: WorkspaceAccess, ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    return dict(
        (
            await access.session.execute(
                select(Responsibility.id, Responsibility.name).where(Responsibility.id.in_(ids))
            )
        ).all()
    )


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
    elif case.case_type == "onboarding":
        kind, title = "access_confirmed", f"New owner has the access needed for “{name}”"
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


async def similar_open_cases(
    access: WorkspaceAccess,
    *,
    affected_person_id: uuid.UUID | None,
    project_asset_id: uuid.UUID | None,
    exclude: uuid.UUID | None = None,
) -> list[ContinuityCase]:
    """Open cases about the same person or the same project: likely duplicates."""
    conditions = []
    if affected_person_id is not None:
        conditions.append(ContinuityCase.affected_person_id == affected_person_id)
    if project_asset_id is not None:
        conditions.append(ContinuityCase.project_asset_id == project_asset_id)
    if not conditions:
        return []
    stmt = select(ContinuityCase).where(
        visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
        ContinuityCase.status.in_(OPEN),
        or_(*conditions),
    )
    if exclude is not None:
        stmt = stmt.where(ContinuityCase.id != exclude)
    return list(await access.session.scalars(stmt.order_by(ContinuityCase.created_at).limit(5)))


async def _require_active_member(
    access: WorkspaceAccess, user_id: uuid.UUID | None, what: str
) -> None:
    if user_id is None:
        return
    found = await access.session.scalar(
        select(Membership.id).where(Membership.user_id == user_id, Membership.status == "active")
    )
    if found is None:
        raise ApiError(422, "not_a_member", f"The {what} must be an active workspace member.")


async def create_case(
    access: WorkspaceAccess,
    data: CaseIn,
    jobs: procrastinate.App | None = None,
    *,
    self_request: bool = False,
) -> CaseDetail:
    """Managers create any case. A member may only request cover for their own absence;
    that request does nothing until a manager activates it."""
    if self_request:
        authorize(access, Permission.CASE_READ)
        if data.case_type != "coverage" or data.affected_person_id not in (
            await my_person_ids(access)
        ):
            raise ApiError(403, "forbidden", "You can only request cover for your own absence.")
    else:
        authorize(access, Permission.CASE_MANAGE)
    await _require_active_member(access, data.accountable_manager_user_id, "accountable manager")
    await _require_active_member(access, data.delegate_approver_user_id, "delegated approver")
    if data.project_asset_id is not None:
        asset = await access.session.scalar(
            select(Asset.id).where(
                Asset.id == data.project_asset_id,
                visible(access, Permission.RESPONSIBILITY_READ, Asset.tenant_id),
                Asset.status == "active",
            )
        )
        if asset is None:
            raise ApiError(422, "asset_not_found", "That project does not exist.")
    duplicates = await similar_open_cases(
        access,
        affected_person_id=data.affected_person_id,
        project_asset_id=data.project_asset_id,
    )
    if duplicates and not data.duplicate_override_reason:
        raise ApiError(
            409,
            "duplicate_case",
            f"“{duplicates[0].title}” is already open for the same person or project. "
            "Open it instead, or say why a separate case is needed.",
        )
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
        status="draft",
        title=data.title,
        reason=data.reason or None,
        affected_person_id=data.affected_person_id,
        starts_at=data.starts_at,
        ends_at=data.ends_at,
        priority=data.priority,
        due_at=data.due_at,
        time_zone=data.time_zone,
        accountable_manager_user_id=data.accountable_manager_user_id,
        delegate_approver_user_id=data.delegate_approver_user_id,
        approval_due_at=data.approval_due_at,
        project_asset_id=data.project_asset_id,
        duplicate_override_reason=(data.duplicate_override_reason or None) if duplicates else None,
        initiator_user_id=access.user_id,
        coordinator_user_id=access.user_id,
        self_requested=self_request,
    )
    access.session.add(case)
    await access.session.flush()
    lifecycle.record_created(
        access, case, "Cover requested by the person away" if self_request else "Case created"
    )
    if data.project_asset_id is not None:
        # Project handover: the responsibilities stewarding the project, as currently held.
        stewards = await access.session.scalars(
            select(OwnershipAssignment)
            .join(
                ResponsibilityAsset,
                ResponsibilityAsset.responsibility_id == OwnershipAssignment.responsibility_id,
            )
            .join(Responsibility, Responsibility.id == OwnershipAssignment.responsibility_id)
            .where(
                ResponsibilityAsset.asset_id == data.project_asset_id,
                OwnershipAssignment.role == "primary",
                Responsibility.status == "active",
                catalog.active_at(_now()),
            )
        )
        seen: set[uuid.UUID] = set()
        for a in stewards:
            if a.responsibility_id in seen:
                continue
            seen.add(a.responsibility_id)
            access.session.add(
                CaseScopeItem(
                    tenant_id=access.tenant_id,
                    case_id=case.id,
                    responsibility_id=a.responsibility_id,
                    role="primary",
                    current_assignment_id=a.id,
                )
            )
    # Departure/coverage (and an outgoing project lead): discover what the person holds.
    if data.affected_person_id is not None and data.case_type in (
        "coverage",
        "departure",
        "transfer",
    ):
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
    _record(access, case, "case.created", case_type=data.case_type, priority=data.priority)
    if jobs is not None:
        await notifications.request_case_deadlines(access.session, jobs, case, access.user_id)
    return await get_case(access, case.id)


async def update_case(
    access: WorkspaceAccess,
    case_id: uuid.UUID,
    data: CaseUpdate,
    jobs: procrastinate.App | None = None,
) -> CaseDetail:
    changes = data.model_dump(exclude_unset=True)
    # Dates, ownership dates aside, and who is accountable can change until the case closes.
    plan_fields = {"starts_at", "ends_at"}
    case = await _for_change(access, case_id, EDITABLE if plan_fields & changes.keys() else OPEN)
    await _require_active_member(
        access, changes.get("accountable_manager_user_id"), "accountable manager"
    )
    await _require_active_member(
        access, changes.get("delegate_approver_user_id"), "delegated approver"
    )
    for field, value in changes.items():
        setattr(case, field, value)
    if case.case_type == "coverage" and (case.ends_at is None or case.ends_at <= case.starts_at):
        raise ApiError(422, "invalid_range", "Coverage must end after it starts.")
    if case.case_type != "coverage" and case.ends_at is not None:
        raise ApiError(422, "invalid_range", "Only coverage cases have an end date.")
    if plan_fields & changes.keys():
        _plan_changed(access, case)
    _record(access, case, "case.updated", fields=",".join(sorted(changes)))
    if jobs is not None and {"due_at", "approval_due_at", "ends_at"} & changes.keys():
        # Reminders are keyed by the deadline; ones for an old deadline become no-ops.
        await notifications.request_case_deadlines(access.session, jobs, case, access.user_id)
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
    onboarding = case.case_type == "onboarding"
    # Onboarding: the new person receives; whoever holds it now is the outgoing owner.
    current = await _current_assignment(
        access, data.responsibility_id, data.role, None if onboarding else case.affected_person_id
    )
    access.session.add(
        CaseScopeItem(
            tenant_id=access.tenant_id,
            case_id=case_id,
            responsibility_id=data.responsibility_id,
            role=data.role,
            current_assignment_id=current.id if current else None,
            recipient_person_id=case.affected_person_id if onboarding else None,
        )
    )
    _plan_changed(access, case)
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
        if person_id or team_id:
            item.decline_reason = item.declined_at = item.declined_by = None
    if "handover_notes" in changes:
        item.handover_notes = changes["handover_notes"] or None
    if "exception_reason" in changes:
        item.exception_reason = changes["exception_reason"] or None
    _plan_changed(access, case)
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
    _plan_changed(access, case)
    _record(access, case, "case.scope_removed", responsibility_id=str(item.responsibility_id))
    return await get_case(access, case_id)


async def submit_case(
    access: WorkspaceAccess, case_id: uuid.UUID, jobs: procrastinate.App
) -> CaseDetail:
    case = await _for_change(access, case_id, lifecycle.INTAKE)
    if case.self_requested and case.activated_at is None:
        raise ApiError(409, "not_activated", "Activate the cover request first.")
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
    names = await responsibility_names(access, [i.responsibility_id for i in items])
    covered = set(
        await access.session.scalars(
            select(CaseReadinessCriterion.scope_item_id).where(
                CaseReadinessCriterion.case_id == case_id
            )
        )
    )
    access.session.add_all(
        _default_criteria(case, i, names[i.responsibility_id])
        for i in items
        if not i.exception_reason and i.id not in covered and i.state == "planned"
    )
    lifecycle.move(access, case, "planning", "Plan submitted for approval")
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
    case = await _load(access, case_id, lock=True)
    if case.delegate_approver_user_id != access.user_id:
        authorize(access, Permission.CASE_APPROVE)
    if case.status not in lifecycle.APPROVABLE:
        raise ApiError(409, "invalid_state", "Only plans in planning or review can be decided.")
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
    if data.decision == "approved":
        lifecycle.move(access, case, "ready_for_transfer", "Plan approved")
    elif case.status == "awaiting_review":
        lifecycle.move(access, case, "planning", "Plan rejected")
    await _notify_case_update(access, jobs, case, data.decision)
    return await get_case(access, case_id)


async def execute_case(
    access: WorkspaceAccess, case_id: uuid.UUID, jobs: procrastinate.App
) -> CaseDetail:
    """Apply every ownership change in one transaction. Retries are safe: the status guard
    (under the case row lock) lets exactly one execution through."""
    case = await _for_change(access, case_id, lifecycle.EXECUTABLE)
    if not await _current_approval(access.session, case):
        raise ApiError(409, "approval_required", "The current plan needs an approval first.")
    at = max(case.starts_at, _now())
    reason = f"Continuity case: {case.title}"
    for item in await _scope(access.session, case_id):
        if item.state == "applied":  # already handed over before a reopen
            continue
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
    lifecycle.move(access, case, "executing", "Ownership changes applied")
    _record(access, case, "case.executed", effective_at=at.isoformat())
    await _notify_case_update(access, jobs, case, "executing")
    return await get_case(access, case_id)


async def extend_coverage(
    access: WorkspaceAccess,
    case_id: uuid.UUID,
    data: ExtendIn,
    jobs: procrastinate.App | None = None,
) -> CaseDetail:
    case = await _for_change(access, case_id, lifecycle.RUNNING)
    if case.case_type != "coverage" or case.ends_at is None or data.ends_at <= case.ends_at:
        raise ApiError(422, "invalid_extension", "Coverage can only be extended to a later date.")
    for item in await _scope(access.session, case_id):
        if item.applied_assignment_id:
            await catalog.extend_cover(
                access, item.applied_assignment_id, data.ends_at, "Coverage extended"
            )
    case.ends_at = data.ends_at
    _record(access, case, "case.extended", ends_at=data.ends_at.isoformat())
    if jobs is not None:
        # The coverage-ending reminder follows the new end; the old one becomes a no-op.
        await notifications.request_case_deadlines(access.session, jobs, case, access.user_id)
    return await get_case(access, case_id)


async def complete_case(
    access: WorkspaceAccess,
    case_id: uuid.UUID,
    jobs: procrastinate.App,
    data: CompleteIn | None = None,
) -> CaseDetail:
    case = await _for_change(access, case_id, lifecycle.RUNNING)
    sod_reason = data.sod_exception_reason if data else None
    if await _is_critical(access, case_id):
        approvers = set(
            await access.session.scalars(
                select(CaseApproval.approver_user_id).where(
                    CaseApproval.case_id == case_id,
                    CaseApproval.plan_version == case.plan_version,
                    CaseApproval.decision == "approved",
                )
            )
        )
        if (access.user_id == case.initiator_user_id or access.user_id in approvers) and (
            not sod_reason
        ):
            raise ApiError(
                409,
                "separation_of_duties",
                "Critical cases need a verifier who neither started nor approved the case, "
                "or a recorded separation-of-duties exception.",
            )
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
        or bool(sod_reason)
    )
    lifecycle.move(access, case, "completed", sod_reason)
    case.outcome = "completed_with_exceptions" if exceptions else "completed"
    case.closed_at = func.now()
    _record(access, case, "case.completed", outcome=case.outcome, sod_exception=bool(sod_reason))
    await _notify_case_update(access, jobs, case, "completed")
    return await get_case(access, case_id)


async def cancel_case(
    access: WorkspaceAccess, case_id: uuid.UUID, jobs: procrastinate.App
) -> CaseDetail:
    case = await _for_change(access, case_id, (*EDITABLE, "blocked"))
    lifecycle.move(access, case, "cancelled")
    case.outcome, case.closed_at = "cancelled", func.now()
    _record(access, case, "case.cancelled")
    await _notify_case_update(access, jobs, case, "cancelled")
    return await get_case(access, case_id)


async def add_task(
    access: WorkspaceAccess, case_id: uuid.UUID, data: TaskIn, jobs: procrastinate.App
) -> CaseDetail:
    case = await _for_change(access, case_id, OPEN)
    if data.assignee_user_id and data.assignee_team_id:
        raise ApiError(422, "one_assignee", "Assign a member or a team, not both.")
    if data.assignee_user_id:
        await _require_member(access, data.assignee_user_id)
    if data.assignee_team_id:
        await catalog.require_assignee(access, catalog.Assignee(team_id=data.assignee_team_id))
    if data.depends_on:
        found = set(
            await access.session.scalars(
                select(CaseTask.id).where(
                    CaseTask.id.in_(data.depends_on), CaseTask.case_id == case_id
                )
            )
        )
        if found != set(data.depends_on):
            raise ApiError(422, "dependency_not_found", "Dependencies must be tasks in this case.")
    task = CaseTask(
        tenant_id=access.tenant_id,
        case_id=case_id,
        scope_item_id=data.scope_item_id,
        title=data.title,
        description=data.description or None,
        assignee_user_id=data.assignee_user_id,
        assignee_team_id=data.assignee_team_id,
        due_at=data.due_at,
        priority=data.priority,
        created_by=access.user_id,
    )
    access.session.add(task)
    await access.session.flush()
    access.session.add_all(
        CaseTaskDependency(tenant_id=access.tenant_id, task_id=task.id, depends_on_task_id=d)
        for d in set(data.depends_on)
    )
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
    if data.status == task.status:
        raise ApiError(409, "unchanged", f"The task is already {task.status}.")
    if data.status == "done":
        waiting = await open_dependencies(access.session, [task.id])
        if waiting.get(task.id):
            raise ApiError(
                409,
                "dependencies_open",
                "Finish what this task depends on first: " + ", ".join(waiting[task.id]) + ".",
            )
    if data.status != "done" and task.status == "done" and not data.reason:
        raise ApiError(422, "reason_required", "Say why a completed task is reopened or cancelled.")
    task.status = data.status
    task.completed_at = func.now() if data.status == "done" else None
    task.completed_by = access.user_id if data.status == "done" else None
    if data.status == "done":
        task.completion_note = data.completion_note or None
        task.completion_url = str(data.completion_url) if data.completion_url else None
        task.needs_input_from_user_id = None
    kind = {"done": "completed", "open": "reopened", "cancelled": "cancelled"}[data.status]
    access.session.add(
        CaseTaskEvent(
            tenant_id=access.tenant_id,
            task_id=task.id,
            kind=kind,
            body=data.reason or data.completion_note or None,
            detail={"url": str(data.completion_url)} if data.completion_url else {},
            actor_user_id=access.user_id,
        )
    )
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
            checklist=[{"step": step, "done": False} for step in data.checklist],
        )
    )
    if data.criterion_type == "rehearsal" and not data.checklist:
        raise ApiError(422, "checklist_required", "A rehearsal needs at least one step.")
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
    if data.status in EXPLAINED and not data.note:
        raise ApiError(
            422, "explanation_required", "Say why this check is blocked or can't be assessed."
        )
    if (
        data.status == "met"
        and criterion.criterion_type == "rehearsal"
        and not all(step.get("done") for step in criterion.checklist)
    ):
        raise ApiError(409, "rehearsal_incomplete", "Finish every rehearsal step first.")
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


async def my_person_ids(access: WorkspaceAccess) -> set[uuid.UUID]:
    """Directory people that are the signed-in member (matched by email)."""
    return set(
        await access.session.scalars(
            select(Person.id)
            .join(Membership, func.lower(Membership.email) == func.lower(Person.email))
            .where(
                Membership.user_id == access.user_id,
                Membership.status == "active",
                visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
            )
        )
    )


async def is_scope_recipient(access: WorkspaceAccess, scope_item_id: uuid.UUID | None) -> bool:
    if scope_item_id is None:
        return False
    person = await access.session.scalar(
        select(CaseScopeItem.recipient_person_id).where(CaseScopeItem.id == scope_item_id)
    )
    return person is not None and person in await my_person_ids(access)


async def coverage_warnings(
    access: WorkspaceAccess, case: ContinuityCase, items: list[CaseScopeItem]
) -> list[str]:
    """Overlapping absences, from open coverage cases whose [start, end) overlaps this one."""
    if case.status not in OPEN:
        return []
    end = case.ends_at or case.starts_at
    overlapping = select(ContinuityCase).where(
        visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
        ContinuityCase.id != case.id,
        ContinuityCase.case_type == "coverage",
        ContinuityCase.status.in_(OPEN),
        ContinuityCase.starts_at < (end if case.ends_at else case.starts_at + timedelta(days=1)),
        or_(ContinuityCase.ends_at.is_(None), ContinuityCase.ends_at > case.starts_at),
    )
    warnings = []
    if case.case_type == "coverage" and case.affected_person_id:
        for other in await access.session.scalars(
            overlapping.where(ContinuityCase.affected_person_id == case.affected_person_id)
        ):
            warnings.append(f"“{other.title}” already covers an overlapping absence.")
    covers = {i.recipient_person_id for i in items if i.recipient_person_id}
    if covers:
        names = dict(
            (
                await access.session.execute(
                    select(Person.id, Person.display_name).where(Person.id.in_(covers))
                )
            ).all()
        )
        for other in await access.session.scalars(
            overlapping.where(ContinuityCase.affected_person_id.in_(covers))
        ):
            name = names.get(other.affected_person_id, "A recipient")  # type: ignore[arg-type]
            warnings.append(f"{name} is away during this period (“{other.title}”).")
    return warnings


def _link(c: ContinuityCase) -> CaseLink:
    return CaseLink(id=c.id, title=c.title, case_type=c.case_type, status=c.status)


async def open_dependencies(
    session: AsyncSession, task_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    """For each task, the titles of open tasks it still waits for."""
    rows = await session.execute(
        select(CaseTaskDependency.task_id, CaseTask.title)
        .join(CaseTask, CaseTask.id == CaseTaskDependency.depends_on_task_id)
        .where(CaseTaskDependency.task_id.in_(task_ids), CaseTask.status == "open")
        .order_by(CaseTask.title)
    )
    waiting: dict[uuid.UUID, list[str]] = {}
    for task_id, title in rows:
        waiting.setdefault(task_id, []).append(title)
    return waiting


async def task_views(
    access: WorkspaceAccess,
    tasks: list[CaseTask],
    names: dict[uuid.UUID, str],
    *,
    case_titles: dict[uuid.UUID, str] | None = None,
) -> list[TaskView]:
    ids = [t.id for t in tasks]
    deps: dict[uuid.UUID, list[uuid.UUID]] = {}
    for task_id, dep in await access.session.execute(
        select(CaseTaskDependency.task_id, CaseTaskDependency.depends_on_task_id).where(
            CaseTaskDependency.task_id.in_(ids)
        )
    ):
        deps.setdefault(task_id, []).append(dep)
    waiting = await open_dependencies(access.session, ids)
    teams = dict(
        (
            await access.session.execute(
                select(Team.id, Team.name).where(
                    Team.id.in_([t.assignee_team_id for t in tasks if t.assignee_team_id])
                )
            )
        ).all()
    )
    now = _now()
    views = []
    for t in tasks:
        view = _task_view(t, names, now)
        view.priority = t.priority
        view.assignee_team_id = t.assignee_team_id
        view.assignee_team_name = teams.get(t.assignee_team_id) if t.assignee_team_id else None
        view.depends_on = deps.get(t.id, [])
        view.blocked_by = waiting.get(t.id, []) if t.status == "open" else []
        view.needs_input_from_user_id = t.needs_input_from_user_id
        view.needs_input_from_name = (
            names.get(t.needs_input_from_user_id) if t.needs_input_from_user_id else None
        )
        view.completion_note = t.completion_note
        view.completion_url = t.completion_url
        view.external_provider = t.external_provider
        view.external_url = t.external_url
        view.sync_status = t.sync_status
        view.case_title = case_titles.get(t.case_id) if case_titles else None
        views.append(view)
    return views


def readiness_reasons(criteria: list[CaseReadinessCriterion], tasks: list[TaskView]) -> list[str]:
    """Plain-language reasons readiness is blocked or uncertain."""
    reasons = []
    for c in criteria:
        if c.status == "blocked":
            reasons.append(f"“{c.title}” is blocked: {c.note}")
        elif c.status == "needs_review":
            reasons.append(f"“{c.title}” needs a person to review it: {c.note}")
        elif c.status == "unable_to_assess":
            reasons.append(f"“{c.title}” can't be assessed: {c.note}")
        elif c.mandatory and c.status == "pending":
            if c.criterion_type == "rehearsal" and c.checklist:
                done = sum(1 for s in c.checklist if s.get("done"))
                reasons.append(f"“{c.title}”: rehearsal {done}/{len(c.checklist)} steps done")
            else:
                reasons.append(f"“{c.title}” is still pending")
    waiting = [t for t in tasks if t.status == "open" and t.blocked_by]
    if waiting:
        reasons.append(f"{len(waiting)} task(s) are waiting on other tasks")
    asked = [t for t in tasks if t.status == "open" and t.needs_input_from_name]
    for t in asked:
        reasons.append(f"“{t.title}” is waiting for input from {t.needs_input_from_name}")
    return reasons


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
    approve = approve or case.delegate_approver_user_id == access.user_id
    if manage and case.status in EDITABLE:
        actions.append("edit")
    if manage and lifecycle.allowed(case, "cancelled"):
        actions.append("cancel")
    if manage and case.self_requested and case.activated_at is None:
        actions.append("activate")
    elif manage and case.status in lifecycle.INTAKE:
        actions.append("submit")
    if manage and case.emergency and case.status in EDITABLE:
        actions.append("fill_backups")
    if approve and case.status in lifecycle.APPROVABLE:
        actions.append("decide")
    if manage and case.status in lifecycle.EXECUTABLE and approved:
        actions.append("execute")
    if manage and case.status in lifecycle.RUNNING:
        actions.append("complete")
        if case.case_type == "coverage":
            actions.append("extend")
    if manage and case.status in OPEN:
        actions += ["add_task", "add_criterion", "set_emergency", "add_blocker", "update"]
        if case.status != "blocked":
            actions.append("transition")
    if manage and case.status in ("completed", "cancelled"):
        actions.append("reopen")
    if manage and case.case_type == "departure" and case.status in EDITABLE:
        actions.append("split")
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
            priority=c.priority,
            due_at=c.due_at,
            overdue=c.status in OPEN
            and (
                (c.due_at is not None and c.due_at < now)
                or any(t.case_id == c.id and t.due_at and t.due_at < now for t in tasks)
            ),
            parent_case_id=c.parent_case_id,
        )
        for c in cases
    ]


class CaseFilter(BaseModel):
    status: str | None = None  # "open", "closed" or a single status
    priority: Priority | None = None
    case_type: CaseType | None = None
    affected_person_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    due_before: AwareDatetime | None = None
    overdue: bool = False


async def list_cases(
    access: WorkspaceAccess,
    *,
    status: str | None = None,
    filters: CaseFilter | None = None,
    after: str | None = None,
    limit: int = 200,
) -> tuple[list[CaseSummary], str | None]:
    authorize(access, Permission.CASE_READ)
    f = filters or CaseFilter(status=status)
    status = f.status
    stmt = select(ContinuityCase).where(
        visible(access, Permission.CASE_READ, ContinuityCase.tenant_id)
    )
    if status == "open":
        stmt = stmt.where(ContinuityCase.status.in_(OPEN))
    elif status == "closed":
        stmt = stmt.where(ContinuityCase.status.in_(("completed", "cancelled")))
    elif status:
        stmt = stmt.where(ContinuityCase.status == status)
    if f.priority:
        stmt = stmt.where(ContinuityCase.priority == f.priority)
    if f.case_type:
        stmt = stmt.where(ContinuityCase.case_type == f.case_type)
    if f.affected_person_id:
        stmt = stmt.where(ContinuityCase.affected_person_id == f.affected_person_id)
    if f.team_id:
        from relay.directory.models import TeamMember

        stmt = stmt.where(
            ContinuityCase.affected_person_id.in_(
                select(TeamMember.person_id).where(TeamMember.team_id == f.team_id)
            )
        )
    if f.due_before:
        stmt = stmt.where(ContinuityCase.due_at < f.due_before)
    order = (ContinuityCase.emergency, ContinuityCase.updated_at, ContinuityCase.id)
    keyset = pagination.after_key(
        order, after, (bool, datetime.fromisoformat, uuid.UUID), descending=True
    )
    if keyset is not None:
        stmt = stmt.where(keyset)
    cases, next_cursor = pagination.split(
        list(
            await access.session.scalars(
                stmt.order_by(*(column.desc() for column in order)).limit(limit + 1)
            )
        ),
        limit,
        lambda c: (c.emergency, c.updated_at.isoformat(), c.id),
    )
    summaries = await _summaries(access, cases)
    return ([c for c in summaries if c.overdue] if f.overdue else summaries), next_cursor


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

    blockers = list(
        await access.session.scalars(
            select(CaseBlocker)
            .where(CaseBlocker.case_id == case_id)
            .order_by(CaseBlocker.resolved_at.desc().nulls_first(), CaseBlocker.created_at)
        )
    )
    changes = list(
        await access.session.scalars(
            select(CaseStatusChange)
            .where(CaseStatusChange.case_id == case_id)
            .order_by(CaseStatusChange.changed_at.desc(), CaseStatusChange.id.desc())
        )
    )
    related = {
        c.id: c
        for c in await access.session.scalars(
            select(ContinuityCase).where(
                (ContinuityCase.parent_case_id == case_id)
                | (ContinuityCase.id == case.parent_case_id)
            )
        )
    }
    duplicates = (
        await similar_open_cases(
            access,
            affected_person_id=case.affected_person_id,
            project_asset_id=case.project_asset_id,
            exclude=case.id,
        )
        if case.status in OPEN
        else []
    )
    project_name = (
        await access.session.scalar(select(Asset.name).where(Asset.id == case.project_asset_id))
        if case.project_asset_id
        else None
    )
    mine = await my_person_ids(access)
    task_list = await task_views(access, tasks, names)
    manual = sorted(lifecycle.MANUAL.get(case.status, frozenset()))
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
        readiness_blocked=sum(1 for c in criteria if c.status in EXPLAINED),
        readiness_reasons=readiness_reasons(criteria, task_list),
        allowed_actions=_allowed_actions(access, case, approved),
        scope=[
            ScopeItemView(
                id=i.id,
                responsibility_id=i.responsibility_id,
                # Restricted responsibilities the viewer can't see stay unnamed.
                responsibility_name=responsibilities[i.responsibility_id].name
                if i.responsibility_id in responsibilities
                else "Restricted responsibility",
                criticality=responsibilities[i.responsibility_id].criticality
                if i.responsibility_id in responsibilities
                else "standard",
                hidden=i.responsibility_id not in responsibilities,
                role=i.role,
                current_owner_name=None
                if i.responsibility_id not in responsibilities
                else owner_name(i),
                recipient=recipient(i),
                handover_notes=i.handover_notes,
                exception_reason=i.exception_reason,
                state=i.state,
                decline_reason=i.decline_reason,
                declined_at=i.declined_at,
                can_decline=i.recipient_person_id in mine
                and i.state == "planned"
                and case.status in EDITABLE,
            )
            for i in items
        ],
        tasks=task_list,
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
                checklist=[ChecklistStep.model_validate(step) for step in c.checklist],
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
        time_zone=case.time_zone,
        accountable_manager_user_id=case.accountable_manager_user_id,
        accountable_manager_name=names.get(case.accountable_manager_user_id)
        if case.accountable_manager_user_id
        else None,
        delegate_approver_user_id=case.delegate_approver_user_id,
        delegate_approver_name=names.get(case.delegate_approver_user_id)
        if case.delegate_approver_user_id
        else None,
        approval_due_at=case.approval_due_at,
        approval_overdue=case.approval_due_at is not None
        and case.approval_due_at < now
        and case.status in lifecycle.APPROVABLE
        and not approved,
        project_asset_id=case.project_asset_id,
        project_asset_name=project_name,
        reopen_count=case.reopen_count,
        blocked_from=case.blocked_from,
        duplicate_override_reason=case.duplicate_override_reason,
        transitions=manual if "transition" in _allowed_actions(access, case, approved) else [],
        blockers=[
            BlockerView(
                id=b.id,
                description=b.description,
                owner_user_id=b.owner_user_id,
                owner_name=names.get(b.owner_user_id) if b.owner_user_id else None,
                escalate_at=b.escalate_at,
                escalation_due=b.resolved_at is None and b.escalate_at <= now,
                escalated_at=b.escalated_at,
                resolution=b.resolution,
                resolved_by_name=names.get(b.resolved_by) if b.resolved_by else None,
                resolved_at=b.resolved_at,
                created_by_name=names.get(b.created_by),
                created_at=b.created_at,
            )
            for b in blockers
        ],
        status_history=[
            StatusChangeView(
                from_status=c.from_status,
                to_status=c.to_status,
                reason=c.reason,
                outcome=c.outcome,
                closed_at=c.closed_at,
                actor_name=names.get(c.actor_user_id),
                changed_at=c.changed_at,
            )
            for c in changes
        ],
        duplicates=[_link(c) for c in duplicates],
        self_requested=case.self_requested,
        activated_at=case.activated_at,
        warnings=await coverage_warnings(access, case, items),
        parent=_link(related[case.parent_case_id]) if case.parent_case_id in related else None,
        children=[_link(c) for c in related.values() if c.parent_case_id == case.id],
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
    from relay.directory.models import TeamMember

    my_teams = select(TeamMember.team_id).where(
        TeamMember.person_id.in_(await my_person_ids(access))
    )
    mine = (CaseTask.assignee_user_id == access.user_id) | CaseTask.assignee_team_id.in_(my_teams)
    in_open_case = (
        select(CaseTask, ContinuityCase.title)
        .join(ContinuityCase, ContinuityCase.id == CaseTask.case_id)
        .where(
            visible(access, Permission.CASE_READ, CaseTask.tenant_id),
            ContinuityCase.status.in_(OPEN),
            CaseTask.status == "open",
        )
    )
    rows = (
        await access.session.execute(
            in_open_case.where(mine).order_by(
                CaseTask.due_at.asc().nulls_last(), CaseTask.created_at
            )
        )
    ).all()
    asked = (
        await access.session.execute(
            in_open_case.where(CaseTask.needs_input_from_user_id == access.user_id)
        )
    ).all()
    done = (
        await access.session.execute(
            select(CaseTask, ContinuityCase.title)
            .join(ContinuityCase, ContinuityCase.id == CaseTask.case_id)
            .where(
                visible(access, Permission.CASE_READ, CaseTask.tenant_id),
                CaseTask.completed_by == access.user_id,
                CaseTask.status == "done",
            )
            .order_by(CaseTask.completed_at.desc())
            .limit(25)
        )
    ).all()
    titles = {t.case_id: title for t, title in [*rows, *asked, *done]}
    tasks = [t for t, _ in rows]
    open_cases = list(
        await access.session.scalars(
            select(ContinuityCase).where(
                visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
                ContinuityCase.status.in_(OPEN),
            )
        )
    )
    approver = role_allows(access.role, Permission.CASE_APPROVE)
    pending = [
        c
        for c in open_cases
        if c.status in lifecycle.APPROVABLE
        and (approver or c.delegate_approver_user_id == access.user_id)
        and not await _current_approval(access.session, c)
    ]
    attention = [
        c for c in open_cases if c.coordinator_user_id == access.user_id and c not in pending
    ]
    emergencies = sorted(
        (c for c in open_cases if c.emergency), key=lambda c: c.updated_at, reverse=True
    )
    # Unread mentions of me, and knowledge I wrote that is due for review.
    from relay.catalog import knowledge  # local: knowledge imports continuity models
    from relay.notifications.models import Notification

    mentions = await access.session.execute(
        select(Notification, ContinuityCase.title)
        .join(ContinuityCase, ContinuityCase.id == Notification.case_id)
        .where(
            visible(access, Permission.CASE_READ, Notification.tenant_id),
            Notification.recipient_user_id == access.user_id,
            Notification.kind == "mentioned",
            Notification.read_at.is_(None),
        )
        .order_by(Notification.created_at.desc())
        .limit(20)
    )
    stale = [
        k
        for k in await knowledge.responsibility_knowledge_by_author(access, access.user_id)
        if k.freshness == "stale"
    ]
    # Plus drafts and disputes waiting for me as steward.
    seen = {k.id for k in stale}
    stale += [k for k in await knowledge.stewarded_for_review(access) if k.id not in seen]
    return MyWorkView(
        handovers=await _handovers_for_me(access),
        emergencies=await _summaries(access, emergencies),
        tasks=await task_views(access, tasks, names, case_titles=titles),
        needs_input=await task_views(access, [t for t, _ in asked], names, case_titles=titles),
        completed=await task_views(access, [t for t, _ in done], names, case_titles=titles),
        approvals=await _summaries(access, pending),
        attention=await _summaries(access, attention),
        mentions=[
            MentionView(
                notification_id=n.id,
                case_id=n.case_id,
                case_title=title,
                actor_name=names.get(n.actor_user_id) if n.actor_user_id else None,
                created_at=n.created_at,
            )
            for n, title in mentions
            if n.case_id is not None
        ],
        reviews=[
            ReviewView(
                knowledge_id=k.id,
                title=k.title,
                responsibility_id=k.responsibility_id,
                responsibility_name=k.responsibility_name,
            )
            for k in stale[:20]
        ],
    )


async def _handovers_for_me(access: WorkspaceAccess) -> list[HandoverForMe]:
    """Handovers addressed to me that are approved: the first thing a recipient needs."""
    from relay.intelligence.models import Capsule  # local: intelligence imports this module

    if not role_allows(access.role, Permission.AI_READ):
        return []
    rows = await access.session.execute(
        select(Capsule, ContinuityCase.title)
        .join(ContinuityCase, ContinuityCase.id == Capsule.case_id)
        .where(
            visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
            Capsule.recipient_user_id == access.user_id,
            Capsule.status.in_(("approved", "acknowledged")),
            ContinuityCase.status.in_(OPEN_STATUSES),
        )
        .order_by(Capsule.status, Capsule.updated_at.desc())
        .limit(10)
    )
    return [
        HandoverForMe(
            capsule_id=c.id,
            case_id=c.case_id,
            case_title=title,
            status=c.status,
            version=c.current_version,
            updated_at=c.updated_at,
        )
        for c, title in rows
    ]
