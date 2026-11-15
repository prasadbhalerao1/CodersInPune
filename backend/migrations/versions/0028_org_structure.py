"""organisational structure: scoped roles, member types, reporting lines, history

- membership / invitation roles: continuity_manager (runs cases and ownership changes),
  knowledge_steward (verifies knowledge) and team_manager (manages responsibilities held
  by the teams in their scope only).
- membership.member_type: employee, contractor or external collaborator.
- identity.membership_team_scope: the teams a team manager manages.
- directory.person.manager_person_id: reporting line.
- directory.directory_history: append-only team and department membership history.

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ROLES = "('owner', 'admin', 'member', 'guest', 'auditor')"
ROLES = (
    "('owner', 'admin', 'member', 'guest', 'auditor', "
    "'continuity_manager', 'knowledge_steward', 'team_manager')"
)


def _roles(roles: str) -> None:
    for table in ("membership", "invitation"):
        op.drop_constraint(f"ck_{table}_role", table, schema="identity")
        op.create_check_constraint(
            op.f(f"ck_{table}_role"), table, f"role IN {roles}", schema="identity"
        )


def upgrade() -> None:
    role = app_role()
    _roles(ROLES)
    op.add_column(
        "membership",
        sa.Column("member_type", sa.Text(), server_default="employee", nullable=False),
        schema="identity",
    )
    op.create_check_constraint(
        op.f("ck_membership_member_type"),
        "membership",
        "member_type IN ('employee', 'contractor', 'external')",
        schema="identity",
    )

    t = "membership_team_scope"
    op.create_table(
        t,
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("granted_by", sa.Uuid(), nullable=False),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{t}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{t}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{t}_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id", "user_id", "team_id", name=f"uq_{t}_tenant_id_user_id_team_id"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "team_id"],
            ["directory.team.tenant_id", "directory.team.id"],
            name=f"fk_{t}_team",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.user_account.id"], name=f"fk_{t}_user_id_user_account"
        ),
        sa.ForeignKeyConstraint(
            ["granted_by"], ["identity.user_account.id"], name=f"fk_{t}_granted_by_user_account"
        ),
        schema="identity",
    )
    enable_tenant_rls("identity", t)
    grant_table("identity", t, role, ["SELECT", "INSERT", "DELETE"])

    op.add_column(
        "person", sa.Column("manager_person_id", sa.Uuid(), nullable=True), schema="directory"
    )
    op.create_foreign_key(
        "fk_person_manager",
        "person",
        "person",
        ["tenant_id", "manager_person_id"],
        ["tenant_id", "id"],
        source_schema="directory",
        referent_schema="directory",
    )
    op.create_check_constraint(
        op.f("ck_person_not_own_manager"),
        "person",
        "manager_person_id IS NULL OR manager_person_id <> id",
        schema="directory",
    )

    t = "directory_history"
    op.create_table(
        t,
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=True),
        sa.Column("department_id", sa.Uuid(), nullable=True),
        sa.Column("change", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{t}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{t}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{t}_tenant_id_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "person_id"],
            ["directory.person.tenant_id", "directory.person.id"],
            name=f"fk_{t}_person",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "team_id"],
            ["directory.team.tenant_id", "directory.team.id"],
            name=f"fk_{t}_team",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "department_id"],
            ["directory.department.tenant_id", "directory.department.id"],
            name=f"fk_{t}_department",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["identity.user_account.id"],
            name=f"fk_{t}_actor_user_id_user_account",
        ),
        sa.CheckConstraint(
            "change IN ('joined_team', 'left_team', 'joined_department', 'left_department')",
            name=op.f(f"ck_{t}_change"),
        ),
        sa.CheckConstraint(
            "num_nonnulls(team_id, department_id) = 1", name=op.f(f"ck_{t}_one_unit")
        ),
        schema="directory",
    )
    op.create_index(
        f"ix_{t}_tenant_id_person_id", t, ["tenant_id", "person_id"], schema="directory"
    )
    enable_tenant_rls("directory", t)
    grant_table("directory", t, role, ["SELECT", "INSERT"])  # append-only


def downgrade() -> None:
    op.drop_table("directory_history", schema="directory")
    op.drop_constraint("ck_person_not_own_manager", "person", schema="directory")
    op.drop_constraint("fk_person_manager", "person", schema="directory")
    op.drop_column("person", "manager_person_id", schema="directory")
    op.drop_table("membership_team_scope", schema="identity")
    op.drop_constraint("ck_membership_member_type", "membership", schema="identity")
    op.drop_column("membership", "member_type", schema="identity")
    _roles(OLD_ROLES)
