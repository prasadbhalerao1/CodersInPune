"""in-app notifications for case workflows

Created asynchronously by outbox handlers (never in the request). `dedupe_key` is unique
per workspace, so redelivered events and repeated reminders cannot notify twice. Rows hold
identifiers and an enum-like `detail` only; titles are read from the case at display time.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "task_assigned",
    "task_due_soon",
    "task_overdue",
    "approval_requested",
    "mentioned",
    "case_update",
)


def upgrade() -> None:
    role = app_role()
    op.execute("CREATE SCHEMA notifications")
    op.execute(f"GRANT USAGE ON SCHEMA notifications TO {role}")
    kinds = ", ".join(f"'{k}'" for k in KINDS)
    op.create_table(
        "notification",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("dedupe_key", sa.Text(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notification"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_notification_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["identity.user_account.id"],
            name="fk_notification_recipient_user_id_user_account",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["identity.user_account.id"],
            name="fk_notification_actor_user_id_user_account",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["continuity.continuity_case.tenant_id", "continuity.continuity_case.id"],
            name="fk_notification_case",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["continuity.case_task.tenant_id", "continuity.case_task.id"],
            name="fk_notification_task",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_notification_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_notification_tenant_id_dedupe_key"),
        sa.CheckConstraint(f"kind IN ({kinds})", name=op.f("ck_notification_kind")),
        schema="notifications",
    )
    op.create_index(
        "ix_notification_tenant_id_recipient_user_id_read_at",
        "notification",
        ["tenant_id", "recipient_user_id", "read_at"],
        schema="notifications",
    )
    enable_tenant_rls("notifications", "notification")
    grant_table("notifications", "notification", role, ["SELECT", "INSERT", "UPDATE"])


def downgrade() -> None:
    op.drop_table("notification", schema="notifications")
    op.execute("DROP SCHEMA notifications")
