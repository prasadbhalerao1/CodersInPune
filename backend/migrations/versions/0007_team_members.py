"""directory.team_member: people assigned to teams

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "team_member",
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("team_id", sa.Uuid(), nullable=False),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name="pk_team_member"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name="fk_team_member_tenant_id_tenant"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "team_id"],
            ["directory.team.tenant_id", "directory.team.id"],
            name="fk_team_member_team",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "person_id"],
            ["directory.person.tenant_id", "directory.person.id"],
            name="fk_team_member_person",
        ),
        sa.UniqueConstraint("tenant_id", "id", name="uq_team_member_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id", "team_id", "person_id", name="uq_team_member_tenant_id_team_id_person_id"
        ),
        schema="directory",
    )
    enable_tenant_rls("directory", "team_member")
    grant_table("directory", "team_member", app_role(), ["SELECT", "INSERT", "DELETE"])


def downgrade() -> None:
    op.drop_table("team_member", schema="directory")
