"""assets: the things responsibilities steward (repositories, services, vendors, ...)

Ownership stays on responsibilities; an asset has no owner of its own. A responsibility
may steward or use many assets, and an asset may be linked from many responsibilities.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ASSET_TYPES = (
    "repository",
    "service",
    "project",
    "process",
    "vendor",
    "document_collection",
    "other",
)


def upgrade() -> None:
    role = app_role()
    types = ", ".join(f"'{t}'" for t in ASSET_TYPES)
    op.create_table(
        "asset",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("asset_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_asset"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_asset_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["identity.user_account.id"], name="fk_asset_created_by_user_account"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_asset_tenant_id_id"),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_asset_name_length")
        ),
        sa.CheckConstraint(f"asset_type IN ({types})", name=op.f("ck_asset_asset_type")),
        sa.CheckConstraint("status IN ('active', 'archived')", name=op.f("ck_asset_status")),
        sa.CheckConstraint("url IS NULL OR url ~ '^https?://'", name=op.f("ck_asset_url_scheme")),
        schema="catalog",
    )
    op.create_index("ix_asset_tenant_id_status", "asset", ["tenant_id", "status"], schema="catalog")
    enable_tenant_rls("catalog", "asset")
    grant_table("catalog", "asset", role, ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "responsibility_asset",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("responsibility_id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("relationship", sa.Text(), server_default="stewards", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_responsibility_asset"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_responsibility_asset_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_responsibility_asset_responsibility",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "asset_id"],
            ["catalog.asset.tenant_id", "catalog.asset.id"],
            name="fk_responsibility_asset_asset",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["identity.user_account.id"],
            name="fk_responsibility_asset_created_by_user_account",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_responsibility_asset_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "responsibility_id",
            "asset_id",
            name="uq_responsibility_asset_tenant_id_responsibility_id_asset_id",
        ),
        sa.CheckConstraint(
            "relationship IN ('stewards', 'uses')",
            name=op.f("ck_responsibility_asset_relationship"),
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_responsibility_asset_tenant_id_asset_id",
        "responsibility_asset",
        ["tenant_id", "asset_id"],
        schema="catalog",
    )
    enable_tenant_rls("catalog", "responsibility_asset")
    grant_table("catalog", "responsibility_asset", role, ["SELECT", "INSERT", "DELETE"])


def downgrade() -> None:
    op.drop_table("responsibility_asset", schema="catalog")
    op.drop_table("asset", schema="catalog")
