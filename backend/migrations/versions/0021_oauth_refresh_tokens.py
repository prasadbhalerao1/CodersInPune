"""oauth refresh tokens for linear and notion connections

Providers that issue short-lived access tokens also return a refresh token and an
expiry. Both are stored (refresh token encrypted like the access token) so a sync can
refresh instead of reporting the connection as revoked. Expand only.

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("linear_connection", "notion_connection")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(
            table,
            sa.Column("refresh_token_ciphertext", sa.Text(), nullable=True),
            schema="integrations",
        )
        op.add_column(
            table,
            sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
            schema="integrations",
        )


def downgrade() -> None:
    for table in TABLES:
        op.drop_column(table, "token_expires_at", schema="integrations")
        op.drop_column(table, "refresh_token_ciphertext", schema="integrations")
