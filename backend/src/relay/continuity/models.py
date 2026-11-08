"""Continuity cases: transfer, temporary coverage and light departure.

Lifecycle: draft -> planning -> executing -> completed | cancelled (backend-enforced).
`plan_version` increments whenever the reviewed scope or plan changes; an approval only
counts for the version it was given against.
"""

import uuid
from datetime import datetime
from typing import Final

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
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "continuity"
CASE_TYPES: Final = ("transfer", "coverage", "departure")
STATUSES: Final = ("draft", "planning", "executing", "completed", "cancelled")
CRITERION_TYPES: Final = (
    "attestation",
    "task_completed",
    "artefact_linked",
    "supervised_demo",
    "access_confirmed",
    "qa_reviewed",
)
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
            "case_type = 'transfer' OR affected_person_id IS NOT NULL", name="affected_person"
        ),
        Index(None, "tenant_id", "status"),
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
    initiator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    coordinator_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseTask(Base):
    __tablename__ = "case_task"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_case_task_case"),
        _tenant_fk(["scope_item_id"], "continuity.case_scope_item", "fk_case_task_scope_item"),
        CheckConstraint("status IN ('open', 'done', 'cancelled')", name="status"),
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title_length"),
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


class CaseReadinessCriterion(Base):
    __tablename__ = "case_readiness_criterion"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _tenant_fk(["case_id"], "continuity.continuity_case", "fk_criterion_case"),
        _tenant_fk(["scope_item_id"], "continuity.case_scope_item", "fk_criterion_scope_item"),
        CheckConstraint(_in("criterion_type", CRITERION_TYPES), name="type"),
        CheckConstraint("status IN ('pending', 'met', 'blocked', 'waived')", name="status"),
        CheckConstraint("status <> 'waived' OR note IS NOT NULL", name="waiver"),
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
