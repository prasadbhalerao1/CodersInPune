"""tenant sample owner: marks a sample workspace and who created it

`platform.tenant.sample_owner_id` is set only on sample workspaces. Its creator may switch
their own role there to experience Relay as any role, and can always switch back.

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenant", sa.Column("sample_owner_id", sa.Uuid(), nullable=True), schema="platform"
    )


def downgrade() -> None:
    op.drop_column("tenant", "sample_owner_id", schema="platform")
