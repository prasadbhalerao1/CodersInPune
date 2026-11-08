"""directory (people, teams) and catalog (responsibilities, ownership history)

Ownership ranges are half-open: tstzrange(valid_from, valid_to, '[)'), NULL valid_to =
open-ended. Exclusion constraints (btree_gist) enforce at most one primary owner at any
instant and at most one role per assignee per responsibility at any instant. The change
table is append-only (no UPDATE/DELETE grant + trigger).

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERIOD = "tstzrange(valid_from, valid_to, '[)')"


def _ts(name: str, nullable: bool = False, default: bool = True) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.func.now() if default else None,
        nullable=nullable,
    )


def _tenant_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id"], ["platform.tenant.id"], name=f"fk_{table}_tenant_id_tenant"
    )


def _user_fk(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.user_account.id"], name=f"fk_{table}_{column}_user_account"
    )


def upgrade() -> None:
    role = app_role()
    # Trusted extension: the database owner may create it.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.execute("CREATE SCHEMA directory")
    op.execute(f"GRANT USAGE ON SCHEMA directory TO {role}")
    for table, label_column in (("person", "display_name"), ("team", "name")):
        extra = (
            [
                sa.Column("email", sa.Text(), nullable=True),
                sa.Column("title", sa.Text(), nullable=True),
            ]
            if table == "person"
            else [sa.Column("description", sa.Text(), nullable=True)]
        )
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
            sa.Column("tenant_id", sa.Uuid(), nullable=False),
            sa.Column(label_column, sa.Text(), nullable=False),
            *extra,
            sa.Column("status", sa.Text(), server_default="active", nullable=False),
            _ts("created_at"),
            _ts("updated_at"),
            sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
            _tenant_fk(table),
            sa.UniqueConstraint("tenant_id", "id", name=f"uq_{table}_tenant_id_id"),
            sa.CheckConstraint(
                f"char_length({label_column}) BETWEEN 1 AND 200",
                name=f"ck_{table}_{label_column}_length",
            ),
            sa.CheckConstraint("status IN ('active', 'archived')", name=f"ck_{table}_status"),
            schema="directory",
        )
        enable_tenant_rls("directory", table)
        grant_table("directory", table, role, ["SELECT", "INSERT", "UPDATE"])

    op.execute("CREATE SCHEMA catalog")
    op.execute(f"GRANT USAGE ON SCHEMA catalog TO {role}")
    op.create_table(
        "responsibility",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("criticality", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("archived_at", nullable=True, default=False),
        sa.PrimaryKeyConstraint("id", name="pk_responsibility"),
        _tenant_fk("responsibility"),
        _user_fk("responsibility", "created_by"),
        sa.UniqueConstraint("tenant_id", "id", name="uq_responsibility_tenant_id_id"),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 200", name="ck_responsibility_name_length"
        ),
        sa.CheckConstraint(
            "criticality IN ('critical', 'high', 'standard', 'low')",
            name="ck_responsibility_criticality",
        ),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_responsibility_status"),
        schema="catalog",
    )
    op.create_index(
        "ix_responsibility_tenant_id_status",
        "responsibility",
        ["tenant_id", "status"],
        schema="catalog",
    )
    enable_tenant_rls("catalog", "responsibility")
    grant_table("catalog", "responsibility", role, ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "ownership_assignment",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("responsibility_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=True),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        _ts("created_at"),
        sa.PrimaryKeyConstraint("id", name="pk_ownership_assignment"),
        _tenant_fk("ownership_assignment"),
        _user_fk("ownership_assignment", "created_by"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_ownership_assignment_responsibility",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "person_id"],
            ["directory.person.tenant_id", "directory.person.id"],
            name="fk_ownership_assignment_person",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "team_id"],
            ["directory.team.tenant_id", "directory.team.id"],
            name="fk_ownership_assignment_team",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ownership_assignment_tenant_id_id"),
        sa.CheckConstraint(
            "role IN ('primary', 'co_owner', 'backup')", name="ck_ownership_assignment_role"
        ),
        sa.CheckConstraint(
            "num_nonnulls(person_id, team_id) = 1", name="ck_ownership_assignment_one_assignee"
        ),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from", name="ck_ownership_assignment_valid_range"
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_ownership_assignment_tenant_id_responsibility_id",
        "ownership_assignment",
        ["tenant_id", "responsibility_id"],
        schema="catalog",
    )
    op.execute(
        "ALTER TABLE catalog.ownership_assignment "
        "ADD CONSTRAINT ex_ownership_assignment_one_primary "
        f"EXCLUDE USING gist (tenant_id WITH =, responsibility_id WITH =, {PERIOD} WITH &&) "
        "WHERE (role = 'primary')"
    )
    op.execute(
        "ALTER TABLE catalog.ownership_assignment ADD CONSTRAINT ex_ownership_assignment_one_role "
        "EXCLUDE USING gist (tenant_id WITH =, responsibility_id WITH =, "
        f"(COALESCE(person_id, team_id)) WITH =, {PERIOD} WITH &&)"
    )
    enable_tenant_rls("catalog", "ownership_assignment")
    grant_table("catalog", "ownership_assignment", role, ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "ownership_assignment_change",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("assignment_id", sa.Uuid(), nullable=False),
        sa.Column("responsibility_id", sa.Uuid(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        _ts("changed_at"),
        sa.PrimaryKeyConstraint("id", name="pk_ownership_assignment_change"),
        _tenant_fk("ownership_assignment_change"),
        _user_fk("ownership_assignment_change", "changed_by"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["catalog.ownership_assignment.tenant_id", "catalog.ownership_assignment.id"],
            name="fk_assignment_change_assignment",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_assignment_change_responsibility",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_ownership_assignment_change_tenant_id_id"),
        sa.CheckConstraint(
            "change_type IN ('assigned', 'ended')",
            name="ck_ownership_assignment_change_change_type",
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_assignment_change_responsibility_changed_at",
        "ownership_assignment_change",
        ["tenant_id", "responsibility_id", "changed_at"],
        schema="catalog",
    )
    enable_tenant_rls("catalog", "ownership_assignment_change")
    grant_table("catalog", "ownership_assignment_change", role, ["SELECT", "INSERT"])
    op.execute(
        """
        CREATE FUNCTION catalog.reject_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'ownership change history is append-only'
                USING ERRCODE = 'insufficient_privilege';
        END $$
        """
    )
    op.execute(
        "CREATE TRIGGER ownership_assignment_change_append_only "
        "BEFORE UPDATE OR DELETE ON catalog.ownership_assignment_change "
        "FOR EACH ROW EXECUTE FUNCTION catalog.reject_change()"
    )


def downgrade() -> None:
    op.drop_table("ownership_assignment_change", schema="catalog")
    op.execute("DROP FUNCTION catalog.reject_change()")
    op.drop_table("ownership_assignment", schema="catalog")
    op.drop_table("responsibility", schema="catalog")
    op.execute("DROP SCHEMA catalog")
    op.drop_table("team", schema="directory")
    op.drop_table("person", schema="directory")
    op.execute("DROP SCHEMA directory")
    # btree_gist is left installed: other objects may come to rely on it.
