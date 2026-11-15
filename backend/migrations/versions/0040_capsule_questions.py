"""capsule questions: the handover copilot's question-and-answer thread on a capsule

`intelligence.capsule_question` keeps what the incoming owner asked, the answer, how it
was produced ('ai', 'search' when AI was unavailable, 'not_found' when the evidence
doesn't answer it) and the evidence rows cited. Answers are re-checked against current
evidence whenever they are shown. Append-only for the app role.

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "intelligence"
T = "capsule_question"


def _fk(cols: list[str], target: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", *cols], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("capsule_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("asked_by", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Text(), nullable=True),
        sa.Column("evidence_ids", JSONB(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{T}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{T}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{T}_tenant_id_id"),
        _fk(["capsule_id"], "intelligence.capsule", "fk_capsule_question_capsule"),
        _fk(["run_id"], "intelligence.agent_run", "fk_capsule_question_run"),
        sa.ForeignKeyConstraint(
            ["asked_by"], ["identity.user_account.id"], name=f"fk_{T}_asked_by_user_account"
        ),
        sa.CheckConstraint("mode IN ('ai', 'search', 'not_found')", name=op.f(f"ck_{T}_mode")),
        sa.CheckConstraint(
            "confidence IS NULL OR confidence IN ('high', 'medium', 'low')",
            name=op.f(f"ck_{T}_confidence"),
        ),
        sa.Index(f"ix_{T}_tenant_id_capsule_id", "tenant_id", "capsule_id"),
        schema=S,
    )
    enable_tenant_rls(S, T)
    grant_table(S, T, app_role(), ["SELECT", "INSERT"])


def downgrade() -> None:
    op.drop_table(T, schema=S)
