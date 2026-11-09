"""intelligence: AI runtime, evidence, claims, proposals, interviews, capsules

- ai_settings / ai_capability_setting: per-workspace kill switch, token budget and
  capability toggles (absent row = defaults).
- agent_run / agent_run_event: run state machine, checkpoint, provider/model/key index,
  usage; events hold identifiers and codes only.
- evidence: the audience-scoped pool a run was allowed to see (D2); excerpts are bounded.
- claim / claim_evidence: validated findings with their citations.
- proposal: reviewable changes; fingerprint suppresses re-proposing rejected items.
- interview_question: knowledge interview questions and answers.
- capsule / capsule_version / capsule_ack: versioned, approved, acknowledged handovers.
- catalog.knowledge_item.origin gains 'ai' (expand only).

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "intelligence"
CASE = "continuity.continuity_case"
RUN = "intelligence.agent_run"
RUN_STATES = (
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
AUDIENCES = ("workspace", "managers")
PROPOSAL_TYPES = (
    "knowledge_draft",
    "case_finding",
    "task",
    "readiness_criterion",
    "exception",
    "handover_content",
    "coordination_message",
)
TABLES = (
    "capsule_ack",
    "capsule_version",
    "capsule",
    "interview_question",
    "proposal",
    "claim_evidence",
    "claim",
    "evidence",
    "agent_run_event",
    "agent_run",
    "ai_capability_setting",
    "ai_settings",
)


def _base(table: str) -> list[sa.SchemaItem]:
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{table}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{table}_tenant_id_id"),
    ]


def _ts(name: str, nullable: bool = False) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=None if nullable else sa.func.now(),
        nullable=nullable,
    )


def _text(name: str, nullable: bool = False, default: str | None = None) -> sa.Column[sa.Text]:
    return sa.Column(name, sa.Text(), server_default=default, nullable=nullable)


def _int(name: str, nullable: bool = False, default: str | None = None) -> sa.Column[sa.Integer]:
    return sa.Column(name, sa.Integer(), server_default=default, nullable=nullable)


def _json(name: str, default: str | None = None) -> sa.Column[JSONB]:
    return sa.Column(
        name, JSONB(), server_default=sa.text(default) if default else None, nullable=False
    )


def _flag(name: str, default: bool) -> sa.Column[sa.Boolean]:
    return sa.Column(
        name, sa.Boolean(), server_default=sa.true() if default else sa.false(), nullable=False
    )


def _fk(cols: list[str], target: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", *cols], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


def _user(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.user_account.id"], name=f"fk_{table}_{column}_user_account"
    )


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _check(table: str, name: str, condition: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(condition, name=op.f(f"ck_{table}_{name}"))


def _index(table: str, *columns: str) -> None:
    op.create_index(f"ix_{table}_{'_'.join(columns)}", table, list(columns), schema=S)


def _knowledge_origin(condition: str) -> None:
    op.drop_constraint("ck_knowledge_item_origin", "knowledge_item", schema="catalog")
    op.create_check_constraint(
        op.f("ck_knowledge_item_origin"), "knowledge_item", condition, schema="catalog"
    )


def upgrade() -> None:
    role = app_role()
    op.execute(f"CREATE SCHEMA {S}")
    op.execute(f"GRANT USAGE ON SCHEMA {S} TO {role}")
    _knowledge_origin("origin IN ('person', 'notion', 'ai')")

    t = "ai_settings"
    op.create_table(
        t,
        *_base(t),
        _flag("enabled", True),
        _int("monthly_token_budget", nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        _ts("updated_at"),
        _user(t, "updated_by"),
        sa.UniqueConstraint("tenant_id", name="uq_ai_settings_tenant_id"),
        _check(t, "monthly_token_budget", "monthly_token_budget >= 0"),
        schema=S,
    )

    t = "ai_capability_setting"
    op.create_table(
        t,
        *_base(t),
        _text("capability"),
        _flag("enabled", True),
        sa.Column("updated_by", sa.Uuid(), nullable=False),
        _ts("updated_at"),
        _user(t, "updated_by"),
        sa.UniqueConstraint(
            "tenant_id", "capability", name="uq_ai_capability_setting_tenant_id_capability"
        ),
        schema=S,
    )

    t = "agent_run"
    op.create_table(
        t,
        *_base(t),
        _text("capability"),
        _int("capability_version"),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        _text("trigger", default="manual"),
        sa.Column("requested_by", sa.Uuid(), nullable=True),
        _text("state", default="queued"),
        _text("input_hash"),
        _int("step", default="0"),
        _json("checkpoint", "'{}'"),
        _text("provider", nullable=True),
        _text("model", nullable=True),
        _int("key_index", nullable=True),
        _int("input_tokens", default="0"),
        _int("output_tokens", default="0"),
        sa.Column("cost_usd", sa.Numeric(12, 6), server_default="0", nullable=False),
        _int("duration_ms", default="0"),
        _text("error_code", nullable=True),
        _flag("cancel_requested", False),
        _ts("created_at"),
        _ts("started_at", nullable=True),
        _ts("finished_at", nullable=True),
        _fk(["case_id"], CASE, "fk_agent_run_case"),
        _user(t, "requested_by"),
        _check(t, "state", _in("state", RUN_STATES)),
        _check(t, "trigger", "trigger IN ('manual', 'automation', 'retry')"),
        schema=S,
    )
    _index(t, "tenant_id", "case_id")

    t = "agent_run_event"
    op.create_table(
        t,
        *_base(t),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        _text("step"),
        _text("level", default="info"),
        _text("code"),
        _json("detail", "'{}'"),
        _ts("created_at"),
        _fk(["run_id"], RUN, "fk_agent_run_event_run"),
        _check(t, "level", "level IN ('info', 'warning', 'error')"),
        schema=S,
    )
    _index(t, "tenant_id", "run_id")

    t = "evidence"
    op.create_table(
        t,
        *_base(t),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        _text("ref"),
        _text("source_system"),
        _text("source_type"),
        _text("source_id"),
        _text("title"),
        _text("url", nullable=True),
        _text("revision", nullable=True),
        _ts("source_ts", nullable=True),
        _text("excerpt"),
        _text("audience", default="workspace"),
        _text("status", default="active"),
        _ts("created_at"),
        _fk(["run_id"], RUN, "fk_evidence_run"),
        _fk(["case_id"], CASE, "fk_evidence_case"),
        _check(t, "source_system", _in("source_system", ("relay", "github", "linear", "notion"))),
        _check(t, "audience", _in("audience", AUDIENCES)),
        _check(t, "status", "status IN ('active', 'stale', 'withdrawn')"),
        _check(t, "excerpt_length", "char_length(excerpt) <= 4000"),
        schema=S,
    )
    _index(t, "tenant_id", "case_id")
    _index(t, "tenant_id", "source_system", "source_id")

    t = "claim"
    op.create_table(
        t,
        *_base(t),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        _text("capability"),
        _text("kind"),
        _text("claim_type"),
        _text("text"),
        _text("confidence"),
        _text("audience", default="workspace"),
        _text("review_status", default="unreviewed"),
        _flag("supported", True),
        _ts("timeline_at", nullable=True),
        _ts("created_at"),
        _fk(["run_id"], RUN, "fk_claim_run"),
        _fk(["case_id"], CASE, "fk_claim_case"),
        _check(
            t,
            "kind",
            _in(
                "kind",
                ("finding", "decision", "question", "dependency", "conflict", "missing", "work"),
            ),
        ),
        _check(
            t,
            "claim_type",
            _in("claim_type", ("direct_fact", "rule", "ai_inference", "human_decision")),
        ),
        _check(t, "confidence", _in("confidence", ("high", "medium", "low", "insufficient"))),
        _check(t, "audience", _in("audience", AUDIENCES)),
        _check(t, "review_status", "review_status IN ('unreviewed', 'accepted', 'rejected')"),
        _check(t, "text_length", "char_length(text) <= 2000"),
        schema=S,
    )
    _index(t, "tenant_id", "case_id")

    t = "claim_evidence"
    op.create_table(
        t,
        *_base(t),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        _fk(["claim_id"], "intelligence.claim", "fk_claim_evidence_claim"),
        _fk(["evidence_id"], "intelligence.evidence", "fk_claim_evidence_evidence"),
        sa.UniqueConstraint(
            "tenant_id",
            "claim_id",
            "evidence_id",
            name="uq_claim_evidence_tenant_id_claim_id_evidence_id",
        ),
        schema=S,
    )
    _index(t, "tenant_id", "evidence_id")

    t = "proposal"
    op.create_table(
        t,
        *_base(t),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        _text("capability"),
        _text("type"),
        _text("title"),
        _json("payload"),
        _json("claim_ids", "'[]'"),
        _json("evidence_ids", "'[]'"),
        _text("confidence", default="medium"),
        _text("audience", default="workspace"),
        _text("fingerprint"),
        _text("evidence_revision"),
        _text("status", default="pending"),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        _ts("reviewed_at", nullable=True),
        _text("reason", nullable=True),
        _text("result_ref", nullable=True),
        _ts("created_at"),
        _fk(["case_id"], CASE, "fk_proposal_case"),
        _fk(["run_id"], RUN, "fk_proposal_run"),
        _user(t, "reviewed_by"),
        _check(t, "type", _in("type", PROPOSAL_TYPES)),
        _check(t, "status", "status IN ('pending', 'accepted', 'edited', 'rejected')"),
        _check(t, "audience", _in("audience", AUDIENCES)),
        _check(t, "reason_length", "reason IS NULL OR char_length(reason) <= 1000"),
        schema=S,
    )
    _index(t, "tenant_id", "case_id")
    _index(t, "tenant_id", "fingerprint")

    t = "interview_question"
    op.create_table(
        t,
        *_base(t),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("responsibility_id", sa.Uuid(), nullable=True),
        _text("question"),
        _text("why"),
        _json("evidence_ids", "'[]'"),
        sa.Column("asked_user_id", sa.Uuid(), nullable=True),
        _text("status", default="open"),
        _text("answer", nullable=True),
        sa.Column("answered_by", sa.Uuid(), nullable=True),
        _ts("answered_at", nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        _ts("reviewed_at", nullable=True),
        _ts("created_at"),
        _fk(["case_id"], CASE, "fk_interview_question_case"),
        _fk(["run_id"], RUN, "fk_interview_question_run"),
        _fk(
            ["responsibility_id"], "catalog.responsibility", "fk_interview_question_responsibility"
        ),
        _user(t, "asked_user_id"),
        _user(t, "answered_by"),
        _user(t, "reviewed_by"),
        _check(
            t,
            "status",
            _in("status", ("open", "answered", "unknown", "not_applicable", "cannot_share")),
        ),
        _check(t, "answer_length", "answer IS NULL OR char_length(answer) <= 8000"),
        schema=S,
    )
    _index(t, "tenant_id", "case_id")

    t = "capsule"
    op.create_table(
        t,
        *_base(t),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        _text("status", default="draft"),
        _int("current_version", default="0"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        _fk(["case_id"], CASE, "fk_capsule_case"),
        _user(t, "recipient_user_id"),
        _user(t, "created_by"),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "recipient_user_id",
            name="uq_capsule_tenant_id_case_id_recipient_user_id",
        ),
        _check(t, "status", "status IN ('draft', 'approved', 'acknowledged')"),
        schema=S,
    )

    t = "capsule_version"
    op.create_table(
        t,
        *_base(t),
        sa.Column("capsule_id", sa.Uuid(), nullable=False),
        _int("version"),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        _json("sections"),
        _json("omissions", "'[]'"),
        _json("redactions", "'[]'"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        _ts("created_at"),
        sa.Column("approved_by", sa.Uuid(), nullable=True),
        _ts("approved_at", nullable=True),
        _fk(["capsule_id"], "intelligence.capsule", "fk_capsule_version_capsule"),
        _fk(["run_id"], RUN, "fk_capsule_version_run"),
        _user(t, "created_by"),
        _user(t, "approved_by"),
        sa.UniqueConstraint(
            "tenant_id",
            "capsule_id",
            "version",
            name="uq_capsule_version_tenant_id_capsule_id_version",
        ),
        schema=S,
    )

    t = "capsule_ack"
    op.create_table(
        t,
        *_base(t),
        sa.Column("capsule_id", sa.Uuid(), nullable=False),
        _int("version"),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        _ts("acknowledged_at"),
        _fk(["capsule_id"], "intelligence.capsule", "fk_capsule_ack_capsule"),
        _user(t, "user_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "capsule_id",
            "version",
            "user_id",
            name="uq_capsule_ack_tenant_id_capsule_id_version_user_id",
        ),
        schema=S,
    )

    for table in TABLES:
        enable_tenant_rls(S, table)
        # Evidence/claim history is kept; nothing here is deleted by the application.
        grant_table(S, table, role, ["SELECT", "INSERT", "UPDATE"])


def downgrade() -> None:
    for table in TABLES:
        op.drop_table(table, schema=S)
    op.execute(f"DROP SCHEMA {S}")
    op.execute("UPDATE catalog.knowledge_item SET origin = 'person' WHERE origin = 'ai'")
    _knowledge_origin("origin IN ('person', 'notion')")
