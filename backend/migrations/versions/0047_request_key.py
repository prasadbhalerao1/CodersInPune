"""request key: idempotent creates (one resource per workspace and Idempotency-Key)

Revision ID: 0047
Revises: 0046
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "platform"
T = "request_key"


def upgrade() -> None:
    op.create_table(
        T,
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{T}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{T}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{T}_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "key", name=f"uq_{T}_tenant_id_key"),
        schema=S,
    )
    enable_tenant_rls(S, T)
    grant_table(S, T, app_role(), ["SELECT", "INSERT", "UPDATE", "DELETE"])


def downgrade() -> None:
    op.drop_table(T, schema=S)
