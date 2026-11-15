"""email delivery for notifications and invitations

- notifications.email_preference: per user and category opt-outs (absence = default on).
- notifications.email_delivery: one row per email Relay intends to send. The unique
  idempotency key (e.g. "notification:<id>") means a notification can be emailed at most
  once, whatever the retries; the same key is sent to the provider as its
  Idempotency-Key. Rows store the recipient address (needed to send) and short error
  codes only, never message bodies or provider secrets.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "notifications"
CATEGORIES = "'tasks', 'reminders', 'approvals', 'mentions', 'case_updates'"


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


def upgrade() -> None:
    role = app_role()
    op.create_table(
        "email_preference",
        *_base("email_preference"),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["identity.user_account.id"],
            name="fk_email_preference_user_id_user_account",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            "category",
            name="uq_email_preference_tenant_id_user_id_category",
        ),
        sa.CheckConstraint(
            f"category IN ({CATEGORIES})", name=op.f("ck_email_preference_category")
        ),
        schema=S,
    )
    enable_tenant_rls(S, "email_preference")
    grant_table(S, "email_preference", role, ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "email_delivery",
        *_base("email_delivery"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=True),
        sa.Column("invitation_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_user_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_email", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_message_id", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("sent_at", nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "notification_id"],
            ["notifications.notification.tenant_id", "notifications.notification.id"],
            name="fk_email_delivery_notification",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "invitation_id"],
            ["identity.invitation.tenant_id", "identity.invitation.id"],
            name="fk_email_delivery_invitation",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["identity.user_account.id"],
            name="fk_email_delivery_recipient_user_id_user_account",
        ),
        sa.UniqueConstraint(
            "tenant_id", "idempotency_key", name="uq_email_delivery_tenant_id_idempotency_key"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed', 'skipped')",
            name=op.f("ck_email_delivery_status"),
        ),
        sa.CheckConstraint(
            "num_nonnulls(notification_id, invitation_id) = 1",
            name=op.f("ck_email_delivery_subject"),
        ),
        schema=S,
    )
    op.create_index(
        "ix_email_delivery_tenant_id_status", "email_delivery", ["tenant_id", "status"], schema=S
    )
    enable_tenant_rls(S, "email_delivery")
    grant_table(S, "email_delivery", role, ["SELECT", "INSERT", "UPDATE"])


def downgrade() -> None:
    op.drop_table("email_delivery", schema=S)
    op.drop_table("email_preference", schema=S)
