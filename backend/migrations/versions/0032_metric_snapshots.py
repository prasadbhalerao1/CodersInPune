"""reproducible insight snapshots

governance.metric_snapshot: the metrics as computed at a moment, with their definitions,
period, numerators, denominators, coverage and limitations, so a trend compares like
with like and nothing historical is invented. Append-only.

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

T = "metric_snapshot"


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False),
        sa.Column("trigger", sa.Text(), server_default="manual", nullable=False),
        sa.Column("taken_by", sa.Uuid(), nullable=True),
        sa.Column(
            "taken_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{T}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{T}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{T}_tenant_id_id"),
        sa.ForeignKeyConstraint(
            ["taken_by"], ["identity.user_account.id"], name=f"fk_{T}_taken_by_user_account"
        ),
        sa.CheckConstraint("trigger IN ('manual', 'scheduled')", name=op.f(f"ck_{T}_trigger")),
        sa.CheckConstraint("period_end > period_start", name=op.f(f"ck_{T}_period")),
        schema="governance",
    )
    op.create_index(f"ix_{T}_tenant_id_taken_at", T, ["tenant_id", "taken_at"], schema="governance")
    enable_tenant_rls("governance", T)
    grant_table("governance", T, app_role(), ["SELECT", "INSERT"])


def downgrade() -> None:
    op.drop_table(T, schema="governance")
