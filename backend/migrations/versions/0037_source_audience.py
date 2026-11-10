"""source audience: who in Relay may see evidence from a linked source (FR-INT-010)

Relay cannot mirror each person's GitHub or Linear permissions, so every linked source
carries an audience: 'managers' (owners, admins and continuity managers) or 'workspace'.

- GitHub repositories: private repositories start as 'managers', public ones as
  'workspace'. An admin may widen a private repository explicitly; a repository that turns
  private is narrowed back to 'managers' on the next sync.
- Linear projects: 'managers' until an admin links the project with 'workspace'.
- Notion sources already carry the visibility an admin chose when mapping them.

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "integrations"
TABLES = ("github_repository", "linear_project")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("audience", sa.Text(), nullable=False, server_default="managers"),
            schema=S,
        )
        op.create_check_constraint(
            op.f(f"ck_{table}_audience"), table, "audience IN ('workspace', 'managers')", schema=S
        )
    op.execute(f"UPDATE {S}.github_repository SET audience = 'workspace' WHERE NOT private")


def downgrade() -> None:
    for table in TABLES:
        op.drop_constraint(op.f(f"ck_{table}_audience"), table, schema=S)
        op.drop_column(table, "audience", schema=S)
