"""approved external task actions

continuity.external_action: a human-approved, create-only write to GitHub or Linear for a
Relay task. The exact destination and content are stored as approved; the executor
embeds the idempotency key in the created issue so a timed-out request is recovered by
finding it instead of creating a duplicate. States: approved, executing, succeeded,
uncertain (provider may have accepted; reconciling), failed.

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

C = "continuity"
T = "external_action"


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("target_label", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), server_default="approved", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("external_url", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("receipt", JSONB(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("approved_by", sa.Uuid(), nullable=False),
        sa.Column(
            "approved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{T}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{T}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{T}_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name=f"uq_{T}_tenant_id_idempotency_key"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["continuity.case_task.tenant_id", "continuity.case_task.id"],
            name=f"fk_{T}_task",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["identity.user_account.id"], name=f"fk_{T}_approved_by_user_account"
        ),
        sa.CheckConstraint("provider IN ('github', 'linear')", name=op.f(f"ck_{T}_provider")),
        sa.CheckConstraint(
            "state IN ('approved', 'executing', 'succeeded', 'uncertain', 'failed')",
            name=op.f(f"ck_{T}_state"),
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 250", name=op.f(f"ck_{T}_title_length")
        ),
        sa.CheckConstraint("char_length(body) <= 20000", name=op.f(f"ck_{T}_body_length")),
        schema=C,
    )
    op.create_index(f"ix_{T}_tenant_id_task_id", T, ["tenant_id", "task_id"], schema=C)
    enable_tenant_rls(C, T)
    grant_table(C, T, app_role(), ["SELECT", "INSERT", "UPDATE"])


def downgrade() -> None:
    op.drop_table(T, schema=C)
