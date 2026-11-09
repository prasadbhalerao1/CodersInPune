"""AI runtime, evidence, claims, proposals, interviews and capsules. See migration 0022.

Every AI output is a claim or a proposal that cites evidence rows built from what the
requesting person could see. Nothing here is ever written by a model directly: the run
engine validates model output and persists it; people review it.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Final

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "intelligence"
_UUIDV7 = sql("uuidv7()")
_USER = "identity.user_account.id"
_CASE = "continuity.continuity_case"

RUN_STATES: Final = (
    "queued",
    "running",
    "waiting_for_approval",
    "completed",
    "partial",
    "failed",
    "cancelled",
    "timed_out",
    "needs_human_review",
)
SOURCE_SYSTEMS: Final = ("relay", "github", "linear", "notion")
AUDIENCES: Final = ("workspace", "managers")
CLAIM_KINDS: Final = (
    "finding",
    "decision",
    "question",
    "dependency",
    "conflict",
    "missing",
    "work",
)
CLAIM_TYPES: Final = ("direct_fact", "rule", "ai_inference", "human_decision")
CONFIDENCE: Final = ("high", "medium", "low", "insufficient")
PROPOSAL_TYPES: Final = (
    "knowledge_draft",
    "case_finding",
    "task",
    "readiness_criterion",
    "exception",
    "handover_content",
    "coordination_message",
)
QUESTION_STATUSES: Final = ("open", "answered", "unknown", "not_applicable", "cannot_share")


def _fk(columns: list[str], target: str, name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["tenant_id", *columns], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class AiSettings(Base):
    __tablename__ = "ai_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id"),
        CheckConstraint("monthly_token_budget >= 0", name="monthly_token_budget"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=sql("true"))
    monthly_token_budget: Mapped[int | None] = mapped_column(Integer)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    updated_at: Mapped[datetime] = _now()


class AiCapabilitySetting(Base):
    __tablename__ = "ai_capability_setting"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "capability"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    capability: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=sql("true"))
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    updated_at: Mapped[datetime] = _now()


class AgentRun(Base):
    __tablename__ = "agent_run"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _fk(["case_id"], _CASE, "fk_agent_run_case"),
        CheckConstraint(_in("state", RUN_STATES), name="state"),
        CheckConstraint("trigger IN ('manual', 'automation', 'retry')", name="trigger"),
        Index(None, "tenant_id", "case_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    capability: Mapped[str] = mapped_column(Text)
    capability_version: Mapped[int] = mapped_column(Integer)
    case_id: Mapped[uuid.UUID | None]
    trigger: Mapped[str] = mapped_column(Text, server_default="manual")
    requested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    state: Mapped[str] = mapped_column(Text, server_default="queued")
    input_hash: Mapped[str] = mapped_column(Text)
    step: Mapped[int] = mapped_column(Integer, server_default="0")
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql("'{}'"))
    provider: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    key_index: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, server_default="0")
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), server_default="0")
    duration_ms: Mapped[int] = mapped_column(Integer, server_default="0")
    error_code: Mapped[str | None] = mapped_column(Text)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, server_default=sql("false"))
    created_at: Mapped[datetime] = _now()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRunEvent(Base):
    __tablename__ = "agent_run_event"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _fk(["run_id"], "intelligence.agent_run", "fk_agent_run_event_run"),
        CheckConstraint("level IN ('info', 'warning', 'error')", name="level"),
        Index(None, "tenant_id", "run_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    run_id: Mapped[uuid.UUID]
    step: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(Text, server_default="info")
    code: Mapped[str] = mapped_column(Text)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sql("'{}'"))
    created_at: Mapped[datetime] = _now()


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _fk(["run_id"], "intelligence.agent_run", "fk_evidence_run"),
        _fk(["case_id"], _CASE, "fk_evidence_case"),
        CheckConstraint(_in("source_system", SOURCE_SYSTEMS), name="source_system"),
        CheckConstraint(_in("audience", AUDIENCES), name="audience"),
        CheckConstraint("status IN ('active', 'stale', 'withdrawn')", name="status"),
        CheckConstraint("char_length(excerpt) <= 4000", name="excerpt_length"),
        Index(None, "tenant_id", "case_id"),
        Index(None, "tenant_id", "source_system", "source_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    run_id: Mapped[uuid.UUID]
    case_id: Mapped[uuid.UUID]
    ref: Mapped[str] = mapped_column(Text)
    source_system: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    revision: Mapped[str | None] = mapped_column(Text)
    source_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    excerpt: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(Text, server_default="workspace")
    status: Mapped[str] = mapped_column(Text, server_default="active")
    created_at: Mapped[datetime] = _now()


class Claim(Base):
    __tablename__ = "claim"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _fk(["run_id"], "intelligence.agent_run", "fk_claim_run"),
        _fk(["case_id"], _CASE, "fk_claim_case"),
        CheckConstraint(_in("kind", CLAIM_KINDS), name="kind"),
        CheckConstraint(_in("claim_type", CLAIM_TYPES), name="claim_type"),
        CheckConstraint(_in("confidence", CONFIDENCE), name="confidence"),
        CheckConstraint(_in("audience", AUDIENCES), name="audience"),
        CheckConstraint(
            "review_status IN ('unreviewed', 'accepted', 'rejected')", name="review_status"
        ),
        CheckConstraint("char_length(text) <= 2000", name="text_length"),
        Index(None, "tenant_id", "case_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    run_id: Mapped[uuid.UUID]
    capability: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[str] = mapped_column(Text)
    audience: Mapped[str] = mapped_column(Text, server_default="workspace")
    review_status: Mapped[str] = mapped_column(Text, server_default="unreviewed")
    supported: Mapped[bool] = mapped_column(Boolean, server_default=sql("true"))
    timeline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()


class ClaimEvidence(Base):
    __tablename__ = "claim_evidence"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "claim_id", "evidence_id"),
        _fk(["claim_id"], "intelligence.claim", "fk_claim_evidence_claim"),
        _fk(["evidence_id"], "intelligence.evidence", "fk_claim_evidence_evidence"),
        Index(None, "tenant_id", "evidence_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    claim_id: Mapped[uuid.UUID]
    evidence_id: Mapped[uuid.UUID]


class Proposal(Base):
    __tablename__ = "proposal"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _fk(["case_id"], _CASE, "fk_proposal_case"),
        _fk(["run_id"], "intelligence.agent_run", "fk_proposal_run"),
        CheckConstraint(_in("type", PROPOSAL_TYPES), name="type"),
        CheckConstraint("status IN ('pending', 'accepted', 'edited', 'rejected')", name="status"),
        CheckConstraint(_in("audience", AUDIENCES), name="audience"),
        CheckConstraint("reason IS NULL OR char_length(reason) <= 1000", name="reason_length"),
        Index(None, "tenant_id", "case_id"),
        Index(None, "tenant_id", "fingerprint"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    run_id: Mapped[uuid.UUID | None]
    capability: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    claim_ids: Mapped[list[str]] = mapped_column(JSONB, server_default=sql("'[]'"))
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, server_default=sql("'[]'"))
    confidence: Mapped[str] = mapped_column(Text, server_default="medium")
    audience: Mapped[str] = mapped_column(Text, server_default="workspace")
    fingerprint: Mapped[str] = mapped_column(Text)
    evidence_revision: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
    result_ref: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()


class InterviewQuestion(Base):
    __tablename__ = "interview_question"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        _fk(["case_id"], _CASE, "fk_interview_question_case"),
        _fk(["run_id"], "intelligence.agent_run", "fk_interview_question_run"),
        _fk(
            ["responsibility_id"],
            "catalog.responsibility",
            "fk_interview_question_responsibility",
        ),
        CheckConstraint(_in("status", QUESTION_STATUSES), name="status"),
        CheckConstraint("answer IS NULL OR char_length(answer) <= 8000", name="answer_length"),
        Index(None, "tenant_id", "case_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    run_id: Mapped[uuid.UUID | None]
    responsibility_id: Mapped[uuid.UUID | None]
    question: Mapped[str] = mapped_column(Text)
    why: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, server_default=sql("'[]'"))
    asked_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    status: Mapped[str] = mapped_column(Text, server_default="open")
    answer: Mapped[str | None] = mapped_column(Text)
    answered_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _now()


class Capsule(Base):
    __tablename__ = "capsule"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "case_id", "recipient_user_id"),
        _fk(["case_id"], _CASE, "fk_capsule_case"),
        CheckConstraint("status IN ('draft', 'approved', 'acknowledged')", name="status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    case_id: Mapped[uuid.UUID]
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    current_version: Mapped[int] = mapped_column(Integer, server_default="0")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()


class CapsuleVersion(Base):
    __tablename__ = "capsule_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "capsule_id", "version"),
        _fk(["capsule_id"], "intelligence.capsule", "fk_capsule_version_capsule"),
        _fk(["run_id"], "intelligence.agent_run", "fk_capsule_version_run"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    capsule_id: Mapped[uuid.UUID]
    version: Mapped[int] = mapped_column(Integer)
    run_id: Mapped[uuid.UUID | None]
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    omissions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=sql("'[]'"))
    redactions: Mapped[list[str]] = mapped_column(JSONB, server_default=sql("'[]'"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = _now()
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CapsuleAck(Base):
    __tablename__ = "capsule_ack"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "capsule_id", "version", "user_id"),
        _fk(["capsule_id"], "intelligence.capsule", "fk_capsule_ack_capsule"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    capsule_id: Mapped[uuid.UUID]
    version: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    acknowledged_at: Mapped[datetime] = _now()
