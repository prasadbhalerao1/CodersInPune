"""connector contract: pause/resume and sync history

- paused / paused_at on GitHub installations, Linear and Notion connections: a paused
  connector keeps its data and credentials but runs no syncs.
- governance.connector_run: one row per sync run (provider, outcome, error, duration),
  the history behind connector health.

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONNECTIONS = (
    ("integrations", "github_installation"),
    ("integrations", "linear_connection"),
    ("integrations", "notion_connection"),
)


def upgrade() -> None:
    for schema, table in CONNECTIONS:
        op.add_column(
            table,
            sa.Column("paused", sa.Boolean(), server_default=sa.false(), nullable=False),
            schema=schema,
        )
        op.add_column(
            table, sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True), schema=schema
        )
    t = "connector_run"
    op.create_table(
        t,
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("connection_ref", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "finished_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{t}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{t}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{t}_tenant_id_id"),
        sa.CheckConstraint(
            "provider IN ('github', 'linear', 'notion')", name=op.f(f"ck_{t}_provider")
        ),
        sa.CheckConstraint(
            "status IN ('ok', 'partial', 'error', 'skipped')", name=op.f(f"ck_{t}_status")
        ),
        schema="governance",
    )
    op.create_index(
        f"ix_{t}_tenant_id_connection_ref", t, ["tenant_id", "connection_ref"], schema="governance"
    )
    enable_tenant_rls("governance", t)
    grant_table("governance", t, app_role(), ["SELECT", "INSERT"])


def downgrade() -> None:
    op.drop_table("connector_run", schema="governance")
    for schema, table in CONNECTIONS:
        op.drop_column(table, "paused_at", schema=schema)
        op.drop_column(table, "paused", schema=schema)
