"""departments: lightweight grouping of people and teams

- directory.department: name unique per workspace, archivable (never deleted).
- person.department_id / team.department_id: optional, composite same-tenant FKs.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    role = app_role()
    op.create_table(
        "department",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_department"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_department_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_department_tenant_id_id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_department_tenant_id_name"),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name=op.f("ck_department_name_length")
        ),
        sa.CheckConstraint("status IN ('active', 'archived')", name=op.f("ck_department_status")),
        schema="directory",
    )
    enable_tenant_rls("directory", "department")
    grant_table("directory", "department", role, ["SELECT", "INSERT", "UPDATE"])

    for table in ("person", "team"):
        op.add_column(
            table, sa.Column("department_id", sa.Uuid(), nullable=True), schema="directory"
        )
        op.create_foreign_key(
            f"fk_{table}_department",
            table,
            "department",
            ["tenant_id", "department_id"],
            ["tenant_id", "id"],
            source_schema="directory",
            referent_schema="directory",
        )
        op.create_index(
            f"ix_{table}_tenant_id_department_id",
            table,
            ["tenant_id", "department_id"],
            schema="directory",
        )


def downgrade() -> None:
    for table in ("person", "team"):
        op.drop_index(f"ix_{table}_tenant_id_department_id", table, schema="directory")
        op.drop_constraint(f"fk_{table}_department", table, schema="directory", type_="foreignkey")
        op.drop_column(table, "department_id", schema="directory")
    op.drop_table("department", schema="directory")
