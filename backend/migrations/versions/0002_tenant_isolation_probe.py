"""tenant isolation probe tables

Minimal parent/child tenant-scoped tables that prove RLS, composite tenant foreign
keys and tenant-prefixed uniqueness. Kept as the reference implementation of the
tenant-table conventions.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CRUD = ["SELECT", "INSERT", "UPDATE", "DELETE"]


def upgrade() -> None:
    role = app_role()
    op.create_table(
        "tenant_probe",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tenant_probe"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_tenant_probe_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_tenant_probe_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_tenant_probe_tenant_id_name"),
        schema="platform",
    )
    enable_tenant_rls("platform", "tenant_probe")
    grant_table("platform", "tenant_probe", role, _CRUD)

    op.create_table(
        "tenant_probe_item",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("probe_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_tenant_probe_item"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_tenant_probe_item_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "probe_id"],
            ["platform.tenant_probe.tenant_id", "platform.tenant_probe.id"],
            name="fk_tenant_probe_item_tenant_id_probe_id_tenant_probe",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_tenant_probe_item_tenant_id_id"),
        schema="platform",
    )
    op.create_index(
        "ix_tenant_probe_item_tenant_id_probe_id",
        "tenant_probe_item",
        ["tenant_id", "probe_id"],
        schema="platform",
    )
    enable_tenant_rls("platform", "tenant_probe_item")
    grant_table("platform", "tenant_probe_item", role, _CRUD)


def downgrade() -> None:
    op.drop_table("tenant_probe_item", schema="platform")
    op.drop_table("tenant_probe", schema="platform")
