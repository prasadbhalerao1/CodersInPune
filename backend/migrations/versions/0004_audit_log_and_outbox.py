"""append-only audit log and transactional outbox

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME_FORMAT = r"'^[a-z_]+(\.[a-z_]+)+$'"


def upgrade() -> None:
    role = app_role()
    op.execute("CREATE SCHEMA audit")
    op.execute(f"GRANT USAGE ON SCHEMA audit TO {role}")
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_audit_event"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_audit_event_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["identity.user_account.id"],
            name="fk_audit_event_actor_user_id_user_account",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_audit_event_tenant_id_id"),
        sa.CheckConstraint("actor_type IN ('user', 'system')", name="ck_audit_event_actor_type"),
        sa.CheckConstraint(f"action ~ {NAME_FORMAT}", name="ck_audit_event_action_format"),
        sa.CheckConstraint(
            "(actor_type = 'user') = (actor_user_id IS NOT NULL)",
            name="ck_audit_event_actor_consistency",
        ),
        schema="audit",
    )
    op.create_index(
        "ix_audit_event_tenant_id_occurred_at",
        "audit_event",
        ["tenant_id", "occurred_at"],
        schema="audit",
    )
    enable_tenant_rls("audit", "audit_event")
    # Append-only: no UPDATE/DELETE grant, and a trigger that refuses them for every role.
    grant_table("audit", "audit_event", role, ["SELECT", "INSERT"])
    op.execute(
        """
        CREATE FUNCTION audit.reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit events are append-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER audit_event_append_only BEFORE UPDATE OR DELETE ON audit.audit_event "
        "FOR EACH ROW EXECUTE FUNCTION audit.reject_change()"
    )

    op.create_table(
        "outbox_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error_type", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_event"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_outbox_event_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_outbox_event_tenant_id_id"),
        sa.CheckConstraint(f"event_type ~ {NAME_FORMAT}", name="ck_outbox_event_event_type_format"),
        schema="platform",
    )
    op.create_index(
        "ix_outbox_event_tenant_id_processed_at",
        "outbox_event",
        ["tenant_id", "processed_at"],
        schema="platform",
    )
    enable_tenant_rls("platform", "outbox_event")
    grant_table("platform", "outbox_event", role, ["SELECT", "INSERT", "UPDATE"])


def downgrade() -> None:
    op.drop_table("outbox_event", schema="platform")
    op.drop_table("audit_event", schema="audit")
    op.execute("DROP FUNCTION audit.reject_change()")
    op.execute("DROP SCHEMA audit")
