"""Automation Center records. See migration 0020."""

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
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "automation"
_UUIDV7 = text("uuidv7()")
_USER = "identity.user_account.id"
TEMPLATES: Final = (
    "critical_without_backup",
    "no_primary_owner",
    "stale_knowledge",
    "archived_owner",
    "coverage_ending",
    "case_overdue",
    "task_overdue",
    "risk_acceptance_expiring",
)


def _fk(columns: list[str], target: str, name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["tenant_id", *columns], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class AutomationRule(Base):
    __tablename__ = "automation_rule"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "template"),
        CheckConstraint(_in("template", TEMPLATES), name="template"),
        CheckConstraint("action IN ('notify', 'create_follow_up')", name="action"),
        CheckConstraint("last_status IN ('never', 'ok', 'failed')", name="last_status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    template: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    action: Mapped[str] = mapped_column(Text, server_default="notify")
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str] = mapped_column(Text, server_default="never")
    last_error: Mapped[str | None] = mapped_column(Text)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AutomationRun(Base):
    __tablename__ = "automation_run"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _fk(["rule_id"], "automation.automation_rule", "fk_automation_run_rule"),
        CheckConstraint("trigger IN ('schedule', 'manual', 'retry')", name="trigger"),
        CheckConstraint("status IN ('ok', 'failed')", name="status"),
        Index(None, "tenant_id", "rule_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    rule_id: Mapped[uuid.UUID]
    trigger: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    matched: Mapped[int] = mapped_column(Integer, server_default="0")
    actions: Mapped[int] = mapped_column(Integer, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FollowUp(Base):
    __tablename__ = "follow_up"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _fk(["rule_id"], "automation.automation_rule", "fk_follow_up_rule"),
        _fk(["responsibility_id"], "catalog.responsibility", "fk_follow_up_responsibility"),
        _fk(["case_id"], "continuity.continuity_case", "fk_follow_up_case"),
        CheckConstraint("status IN ('open', 'done')", name="status"),
        CheckConstraint("num_nonnulls(responsibility_id, case_id) = 1", name="subject"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    rule_id: Mapped[uuid.UUID]
    title: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
    responsibility_id: Mapped[uuid.UUID | None]
    case_id: Mapped[uuid.UUID | None]
    assignee_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    status: Mapped[str] = mapped_column(Text, server_default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutomationAction(Base):
    """Idempotency ledger: one row per (rule, dedupe key), whatever the run."""

    __tablename__ = "automation_action"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "rule_id", "dedupe_key"),
        _fk(["rule_id"], "automation.automation_rule", "fk_automation_action_rule"),
        _fk(["run_id"], "automation.automation_run", "fk_automation_action_run"),
        _fk(["follow_up_id"], "automation.follow_up", "fk_automation_action_follow_up"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    rule_id: Mapped[uuid.UUID]
    run_id: Mapped[uuid.UUID]
    dedupe_key: Mapped[str] = mapped_column(Text)
    follow_up_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
