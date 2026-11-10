"""source data retention after a connector is disconnected (FR-INT-012, D13)

- `disconnected_at` on the GitHub installation and the Linear and Notion connections.
- DELETE grants so the retention job can remove source snapshots (issues, projects, teams,
  repositories, work items, suggestions, Notion pages and sources) 30 days after
  disconnect. Identity mappings and Relay's own records are kept.

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, grant_table, qualified

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "integrations"
CONNECTIONS = ("github_installation", "linear_connection", "notion_connection")
PURGED = (
    "linear_issue",
    "linear_project",
    "linear_team",
    "notion_page",
    "notion_source",
    "github_work_item",
    "github_team",
    "github_repository",
    "ownership_suggestion",
)


def upgrade() -> None:
    for table in CONNECTIONS:
        op.add_column(
            table, sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True), schema=S
        )
    for table in PURGED:
        grant_table(S, table, app_role(), ["DELETE"])


def downgrade() -> None:
    for table in PURGED:
        op.execute(f"REVOKE DELETE ON {qualified(S, table)} FROM {app_role()}")
    for table in CONNECTIONS:
        op.drop_column(table, "disconnected_at", schema=S)
