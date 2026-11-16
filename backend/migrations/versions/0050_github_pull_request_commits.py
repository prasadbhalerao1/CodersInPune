"""github pull request commits: each pull request keeps its commits for Memory Replay

`github_work_item.commits` holds sha, the first line of the message, author and date for a
pull request's commits (never diffs or code). Expand-only: existing rows start empty.

Revision ID: 0050
Revises: 0049
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S, T = "integrations", "github_work_item"


def upgrade() -> None:
    op.add_column(
        T,
        sa.Column("commits", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        schema=S,
    )


def downgrade() -> None:
    op.drop_column(T, "commits", schema=S)
