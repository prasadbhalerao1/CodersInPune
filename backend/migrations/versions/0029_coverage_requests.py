"""self-requested coverage

- continuity_case.self_requested / activated_by / activated_at: a member can request
  cover for their own absence; it stays a request until a case manager activates it.

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

C = "continuity"
CASE = "continuity_case"


def upgrade() -> None:
    op.add_column(
        CASE,
        sa.Column("self_requested", sa.Boolean(), server_default=sa.false(), nullable=False),
        schema=C,
    )
    op.add_column(CASE, sa.Column("activated_by", sa.Uuid(), nullable=True), schema=C)
    op.add_column(
        CASE, sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True), schema=C
    )
    op.create_foreign_key(
        f"fk_{CASE}_activated_by_user_account",
        CASE,
        "user_account",
        ["activated_by"],
        ["id"],
        source_schema=C,
        referent_schema="identity",
    )
    op.create_check_constraint(
        op.f(f"ck_{CASE}_self_request_coverage"),
        CASE,
        "NOT self_requested OR case_type = 'coverage'",
        schema=C,
    )


def downgrade() -> None:
    op.drop_constraint(f"ck_{CASE}_self_request_coverage", CASE, schema=C)
    op.drop_constraint(f"fk_{CASE}_activated_by_user_account", CASE, schema=C)
    for column in ("activated_at", "activated_by", "self_requested"):
        op.drop_column(CASE, column, schema=C)
