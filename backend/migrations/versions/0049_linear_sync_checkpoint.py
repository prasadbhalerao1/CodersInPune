"""linear sync checkpoint: incremental Linear issue sync with daily reconciliation

The same checkpoint as GitHub (0048): `linear_connection.sync_cursor` is the start of the last
successful sync; the next sync fetches issues from there minus an overlap. `reconciled_at` is
the last full-window run, repeated daily. Expand-only.

Revision ID: 0049
Revises: 0048
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S, T = "integrations", "linear_connection"


def upgrade() -> None:
    op.add_column(T, sa.Column("sync_cursor", sa.DateTime(timezone=True)), schema=S)
    op.add_column(T, sa.Column("reconciled_at", sa.DateTime(timezone=True)), schema=S)


def downgrade() -> None:
    op.drop_column(T, "reconciled_at", schema=S)
    op.drop_column(T, "sync_cursor", schema=S)
