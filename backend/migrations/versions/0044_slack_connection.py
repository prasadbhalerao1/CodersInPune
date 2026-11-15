"""slack connection: a workspace's Slack incoming webhook (encrypted) and channel label

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "integrations"
T = "slack_connection"


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("webhook_encrypted", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("connected_by", sa.Uuid(), nullable=True),
        sa.Column(
            "connected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=f"pk_{T}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{T}_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["connected_by"], ["identity.user_account.id"], name=f"fk_{T}_connected_by_user_account"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{T}_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", name=f"uq_{T}_tenant_id"),
        sa.CheckConstraint(
            "char_length(channel) BETWEEN 1 AND 80", name=op.f(f"ck_{T}_channel_length")
        ),
        schema=S,
    )
    enable_tenant_rls(S, T)
    grant_table(S, T, app_role(), ["SELECT", "INSERT", "UPDATE", "DELETE"])


def downgrade() -> None:
    op.drop_table(T, schema=S)
