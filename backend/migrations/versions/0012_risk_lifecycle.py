"""risk lifecycle: open -> acknowledged / accepted (until a date) -> resolved

Risks are still computed deterministically from the catalogue; `risk_record` remembers
what people decided about each one (keyed by the risk's stable key) and when the
condition was first seen and last cleared. An accepted risk whose date has passed is open
again; a risk whose condition no longer holds is resolved automatically.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    role = app_role()
    op.execute("CREATE SCHEMA risks")
    op.execute(f"GRANT USAGE ON SCHEMA risks TO {role}")
    op.create_table(
        "risk_record",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("risk_key", sa.Text(), nullable=False),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("accepted_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_risk_record"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_risk_record_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["identity.user_account.id"],
            name="fk_risk_record_decided_by_user_account",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_risk_record_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "risk_key", name="uq_risk_record_tenant_id_risk_key"),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'accepted', 'resolved')",
            name=op.f("ck_risk_record_status"),
        ),
        sa.CheckConstraint(
            "status <> 'accepted' OR (accepted_until IS NOT NULL AND note IS NOT NULL)",
            name=op.f("ck_risk_record_acceptance"),
        ),
        sa.CheckConstraint(
            "severity IN ('high', 'medium', 'low')", name=op.f("ck_risk_record_severity")
        ),
        schema="risks",
    )
    op.create_index(
        "ix_risk_record_tenant_id_status", "risk_record", ["tenant_id", "status"], schema="risks"
    )
    enable_tenant_rls("risks", "risk_record")
    grant_table("risks", "risk_record", role, ["SELECT", "INSERT", "UPDATE"])


def downgrade() -> None:
    op.drop_table("risk_record", schema="risks")
    op.execute("DROP SCHEMA risks")
