"""Continuity case DTOs: request bodies (`*In`, `*Update`) and response views.

Kept apart from the case engine (`continuity.service`), which re-exports them, so callers
can keep importing `service.CaseDetail` and friends.
"""

import uuid
from datetime import datetime
from typing import Literal
from zoneinfo import available_timezones

from pydantic import AwareDatetime, BaseModel, HttpUrl, model_validator

from relay.continuity import lifecycle
from relay.continuity.models import OPEN_STATUSES
from relay.shared.api_types import LongText, Name, StrictInput

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
    # The incoming person's explicit acceptance; a case cannot complete without it.
    accepted_at: datetime | None = None
    # Restricted and not visible to the viewer: no details beyond its existence.
    hidden: bool = False
    # The signed-in user is the incoming person and may decline the assignment.
    can_decline: bool = False
    # The signed-in user is the incoming person and has not accepted yet.
    can_accept: bool = False


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
