"""Continuity cases: transfer, coverage, departure, onboarding and project handover.

The status model and its allowed transitions live in `continuity.lifecycle`.
`plan_version` increments whenever the reviewed scope or plan changes; an approval only
counts for the version it was given against.
"""

import uuid
from datetime import datetime
from typing import Any, Final

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "continuity"
CASE_TYPES: Final = ("transfer", "coverage", "departure", "onboarding", "project_handover")
STATUSES: Final = (
    "draft",
    "investigating",
    "awaiting_input",
    "planning",
    "awaiting_review",
    "ready_for_transfer",
    "executing",
    "verification",
    "blocked",
    "reopened",
    "completed",
    "cancelled",
)
CLOSED: Final = ("completed", "cancelled")
OPEN_STATUSES: Final = tuple(s for s in STATUSES if s not in CLOSED)
PRIORITIES: Final = ("low", "normal", "high", "urgent")
PARTICIPANT_ROLES: Final = ("approver", "verifier", "reviewer", "contributor", "observer")
CRITERION_TYPES: Final = (
    "attestation",
    "task_completed",
    "artefact_linked",
    "supervised_demo",
    "access_confirmed",
    "qa_reviewed",
    "rehearsal",
)
CRITERION_STATUSES: Final = (
    "pending",
    "met",
    "blocked",
    "waived",
    "needs_review",
    "unable_to_assess",
)
# Readiness states that must say why.
EXPLAINED: Final = ("blocked", "needs_review", "unable_to_assess")
TASK_EVENTS: Final = (
    "comment",
    "clarification_requested",
    "clarification_answered",
    "reassigned",
    "due_changed",
    "completed",
    "reopened",
    "cancelled",
)
SYNC_STATUSES: Final = ("not_mirrored", "pending", "synced", "error", "unlinked")
_UUIDV7 = text("uuidv7()")
_USER = "identity.user_account.id"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _tenant_fk(columns: list[str], target: str, name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["tenant_id", *columns], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


class ContinuityCase(Base):
    __tablename__ = "continuity_case"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["affected_person_id"], "directory.person", "fk_case_affected_person"),
        _tenant_fk(["parent_case_id"], "continuity.continuity_case", "fk_case_parent_case"),
        _tenant_fk(["project_asset_id"], "catalog.asset", "fk_case_project_asset"),
        CheckConstraint(_in("case_type", CASE_TYPES), name="case_type"),
        CheckConstraint(_in("status", STATUSES), name="status"),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('completed', 'completed_with_exceptions', 'cancelled')",
            name="outcome",
        ),
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint("(case_type = 'coverage') = (ends_at IS NOT NULL)", name="coverage_end"),
        CheckConstraint("ends_at IS NULL OR ends_at > starts_at", name="range"),
        CheckConstraint(
            "case_type IN ('transfer', 'project_handover') OR affected_person_id IS NOT NULL",
            name="affected_person",
        ),
        CheckConstraint("NOT emergency OR emergency_reason IS NOT NULL", name="emergency_reason"),
        CheckConstraint(_in("priority", PRIORITIES), name="priority"),
        CheckConstraint("(status = 'blocked') = (blocked_from IS NOT NULL)", name="blocked_from"),
        CheckConstraint(
            "case_type = 'project_handover' OR project_asset_id IS NULL", name="project_asset"
        ),
        CheckConstraint("char_length(time_zone) BETWEEN 1 AND 64", name="time_zone_length"),
        CheckConstraint(
            "NOT self_requested OR case_type = 'coverage'", name="self_request_coverage"
        ),
        Index(None, "tenant_id", "status"),
        Index(None, "tenant_id", "affected_person_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    outcome: Mapped[str | None] = mapped_column(Text)
    affected_person_id: Mapped[uuid.UUID | None]
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    plan_version: Mapped[int] = mapped_column(server_default="1")
    emergency: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    emergency_reason: Mapped[str | None] = mapped_column(Text)
    initiator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    coordinator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[str] = mapped_column(Text, server_default="normal")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_zone: Mapped[str] = mapped_column(Text, server_default="UTC")
    accountable_manager_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    delegate_approver_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    approval_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parent_case_id: Mapped[uuid.UUID | None]
    project_asset_id: Mapped[uuid.UUID | None]
    duplicate_override_reason: Mapped[str | None] = mapped_column(Text)
    reopen_count: Mapped[int] = mapped_column(server_default="0")
    blocked_from: Mapped[str | None] = mapped_column(Text)
    # Connected systems left out of this case's evidence ("github", "linear", "notion").
    excluded_sources: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'"))
    privacy_notice_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    privacy_notice_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    # A member's request for cover of their own absence, pending manager activation.
    self_requested: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    activated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CaseScopeItem(Base):
    """One responsibility in a case: who hands what (role) to whom."""

    __tablename__ = "case_scope_item"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id", "case_id", "responsibility_id", name="uq_scope_item_case_responsibility"
        ),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_scope_item_case"),
        _tenant_fk(["responsibility_id"], "catalog.responsibility", "fk_scope_item_responsibility"),
        _tenant_fk(
            ["current_assignment_id"],
            "catalog.ownership_assignment",
            "fk_scope_item_current_assignment",
        ),
        _tenant_fk(
            ["applied_assignment_id"],
            "catalog.ownership_assignment",
            "fk_scope_item_applied_assignment",
        ),
        _tenant_fk(["recipient_person_id"], "directory.person", "fk_scope_item_recipient_person"),
        _tenant_fk(["recipient_team_id"], "directory.team", "fk_scope_item_recipient_team"),
        CheckConstraint("role IN ('primary', 'co_owner', 'backup')", name="role"),
        CheckConstraint("state IN ('planned', 'applied', 'excepted')", name="state"),
        CheckConstraint(
            "num_nonnulls(recipient_person_id, recipient_team_id) <= 1", name="one_recipient"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    responsibility_id: Mapped[uuid.UUID]
    role: Mapped[str] = mapped_column(Text)
    current_assignment_id: Mapped[uuid.UUID | None]
    recipient_person_id: Mapped[uuid.UUID | None]
    recipient_team_id: Mapped[uuid.UUID | None]
    handover_notes: Mapped[str | None] = mapped_column(Text)
    exception_reason: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="planned")
    applied_assignment_id: Mapped[uuid.UUID | None]
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    decline_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseTask(Base):
    __tablename__ = "case_task"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_case_task_case"),
        _tenant_fk(["scope_item_id"], "continuity.case_scope_item", "fk_case_task_scope_item"),
        _tenant_fk(["assignee_team_id"], "directory.team", "fk_case_task_assignee_team"),
        CheckConstraint("status IN ('open', 'done', 'cancelled')", name="status"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint(_in("priority", PRIORITIES), name="priority"),
        CheckConstraint(_in("sync_status", SYNC_STATUSES), name="sync_status"),
        CheckConstraint(
            "external_provider IS NULL OR external_provider IN ('github', 'linear')",
            name="external_provider",
        ),
        CheckConstraint(
            "completion_url IS NULL OR completion_url ~ '^https?://'", name="completion_url_scheme"
        ),
        CheckConstraint(
            "external_url IS NULL OR external_url ~ '^https?://'", name="external_url_scheme"
        ),
        CheckConstraint(
            "num_nonnulls(assignee_user_id, assignee_team_id) <= 1", name="one_assignee"
        ),
        Index(None, "tenant_id", "assignee_user_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    scope_item_id: Mapped[uuid.UUID | None]
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="open")
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    priority: Mapped[str] = mapped_column(Text, server_default="normal")
    assignee_team_id: Mapped[uuid.UUID | None]
    # An open clarification: the member who has been asked and not yet answered.
    needs_input_from_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    completion_note: Mapped[str | None] = mapped_column(Text)
    completion_url: Mapped[str | None] = mapped_column(Text)
    # External mirror (created by an approved M10 workflow; never by Relay on its own).
    external_provider: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(Text)
    sync_status: Mapped[str] = mapped_column(Text, server_default="not_mirrored")


class CaseTaskDependency(Base):
    __tablename__ = "case_task_dependency"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "task_id", "depends_on_task_id"),
        _tenant_fk(["task_id"], "continuity.case_task", "fk_case_task_dependency_task"),
        _tenant_fk(
            ["depends_on_task_id"], "continuity.case_task", "fk_case_task_dependency_depends_on"
        ),
        CheckConstraint("task_id <> depends_on_task_id", name="not_self"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    task_id: Mapped[uuid.UUID]
    depends_on_task_id: Mapped[uuid.UUID]


class CaseTaskEvent(Base):
    """Append-only task activity (no UPDATE or DELETE grant)."""

    __tablename__ = "case_task_event"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["task_id"], "continuity.case_task", "fk_case_task_event_task"),
        CheckConstraint(_in("kind", TASK_EVENTS), name="kind"),
        CheckConstraint("body IS NULL OR char_length(body) BETWEEN 1 AND 5000", name="body_length"),
        Index(None, "tenant_id", "task_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    task_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseReadinessCriterion(Base):
    __tablename__ = "case_readiness_criterion"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_criterion_case"),
        _tenant_fk(["scope_item_id"], "continuity.case_scope_item", "fk_criterion_scope_item"),
        CheckConstraint(_in("criterion_type", CRITERION_TYPES), name="type"),
        CheckConstraint(_in("status", CRITERION_STATUSES), name="status"),
        CheckConstraint("status <> 'waived' OR note IS NOT NULL", name="waiver"),
        CheckConstraint(
            "status NOT IN ('blocked', 'needs_review', 'unable_to_assess') OR note IS NOT NULL",
            name="explained",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    scope_item_id: Mapped[uuid.UUID | None]
    criterion_type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    mandatory: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    note: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Rehearsal: supervised steps, each {"step", "done", "done_by", "done_at"}.
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'"))


class CaseApproval(Base):
    """Immutable decision against one `plan_version` (no UPDATE grant)."""

    __tablename__ = "case_approval"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_case_approval_case"),
        CheckConstraint("decision IN ('approved', 'rejected')", name="decision"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    plan_version: Mapped[int]
    decision: Mapped[str] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    sod_exception_reason: Mapped[str | None] = mapped_column(Text)
    approver_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseComment(Base):
    """A human note on a case. Append-only: no UPDATE or DELETE grant."""

    __tablename__ = "case_comment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_case_comment_case"),
        CheckConstraint("char_length(body) BETWEEN 1 AND 5000", name="body_length"),
        Index(None, "tenant_id", "case_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseMention(Base):
    __tablename__ = "case_mention"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "comment_id", "user_id"),
        _tenant_fk(["comment_id"], "continuity.case_comment", "fk_case_mention_comment"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    comment_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseKnowledge(Base):
    """What knowledge was handed over (or found missing) for a responsibility in a case."""

    __tablename__ = "case_knowledge"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_case_knowledge_case"),
        _tenant_fk(
            ["responsibility_id"], "catalog.responsibility", "fk_case_knowledge_responsibility"
        ),
        _tenant_fk(
            ["knowledge_item_id"], "catalog.knowledge_item", "fk_case_knowledge_knowledge_item"
        ),
        CheckConstraint("outcome IN ('handed_over', 'missing')", name="outcome"),
        CheckConstraint(
            "outcome = 'missing' OR knowledge_item_id IS NOT NULL", name="item_required"
        ),
        CheckConstraint("note IS NULL OR char_length(note) <= 4000", name="note_length"),
        Index(
            "uq_case_knowledge_tenant_id_case_id_knowledge_item_id",
            "tenant_id",
            "case_id",
            "knowledge_item_id",
            unique=True,
            postgresql_where=text("knowledge_item_id IS NOT NULL"),
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    responsibility_id: Mapped[uuid.UUID]
    knowledge_item_id: Mapped[uuid.UUID | None]
    outcome: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CaseStatusChange(Base):
    """Append-only status history. A closure that is later reopened keeps its outcome here."""

    __tablename__ = "case_status_change"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_case_status_change_case"),
        CheckConstraint(_in("to_status", STATUSES), name="to_status"),
        Index(None, "tenant_id", "case_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    from_status: Mapped[str | None] = mapped_column(Text)
    to_status: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseParticipant(Base):
    """Someone involved in a case beyond the roles the case itself records, and why."""

    __tablename__ = "case_participant"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_case_participant_case"),
        _tenant_fk(["person_id"], "directory.person", "fk_case_participant_person"),
        CheckConstraint(_in("role", PARTICIPANT_ROLES), name="role"),
        CheckConstraint("num_nonnulls(user_id, person_id) = 1", name="one_subject"),
        CheckConstraint("char_length(why) BETWEEN 1 AND 500", name="why_length"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    person_id: Mapped[uuid.UUID | None]
    role: Mapped[str] = mapped_column(Text)
    why: Mapped[str] = mapped_column(Text)
    added_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseBlocker(Base):
    __tablename__ = "case_blocker"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_case_blocker_case"),
        CheckConstraint("char_length(description) BETWEEN 1 AND 1000", name="description_length"),
        CheckConstraint("(resolved_at IS NULL) = (resolution IS NULL)", name="resolution"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    description: Mapped[str] = mapped_column(Text)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    escalate_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseReviewItem(Base):
    """Something the case will share, with whom, and the outgoing owner's decision on it.
    A dispute narrows sharing; it never deletes the source or its history."""

    __tablename__ = "case_review_item"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "case_id", "subject_type", "subject_id"),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_case_review_item_case"),
        _tenant_fk(["reviewer_person_id"], "directory.person", "fk_case_review_item_reviewer"),
        CheckConstraint(
            "subject_type IN ('responsibility', 'knowledge', 'source')", name="subject_type"
        ),
        CheckConstraint("audience IN ('case', 'workspace', 'managers')", name="audience"),
        CheckConstraint(
            "decision IN ('pending', 'confirmed', 'corrected', 'disputed')", name="decision"
        ),
        CheckConstraint(
            "decision IN ('pending', 'confirmed') OR note IS NOT NULL", name="explained"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    subject_type: Mapped[str] = mapped_column(Text)
    subject_id: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(Text)
    reviewer_person_id: Mapped[uuid.UUID | None]
    decision: Mapped[str] = mapped_column(Text, server_default="pending")
    note: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExternalAction(Base):
    """A human-approved, create-only write to GitHub or Linear for a task. The approved
    destination and content are what the executor sends, unchanged."""

    __tablename__ = "external_action"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "idempotency_key"),
        _tenant_fk(["task_id"], "continuity.case_task", "fk_external_action_task"),
        CheckConstraint("provider IN ('github', 'linear')", name="provider"),
        CheckConstraint(
            "state IN ('approved', 'executing', 'succeeded', 'uncertain', 'failed')",
            name="state",
        ),
        CheckConstraint("char_length(title) BETWEEN 1 AND 250", name="title_length"),
        CheckConstraint("char_length(body) <= 20000", name="body_length"),
        Index(None, "tenant_id", "task_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    task_id: Mapped[uuid.UUID]
    provider: Mapped[str] = mapped_column(Text)
    target: Mapped[str] = mapped_column(Text)
    target_label: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, server_default="approved")
    attempts: Mapped[int] = mapped_column(server_default="0")
    external_id: Mapped[str | None] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    receipt: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"))
    approved_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
