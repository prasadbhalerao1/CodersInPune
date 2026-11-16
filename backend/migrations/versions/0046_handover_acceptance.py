"""handover acceptance: the incoming owner accepts each handed-over responsibility

`case_scope_item.accepted_at/accepted_by` record the incoming person's explicit acceptance.
A case cannot complete while a scope item with a recipient is unaccepted. Changing the
recipient or declining clears it. Expand-only.

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

C = "continuity"
ITEM = "case_scope_item"


def upgrade() -> None:
    op.add_column(ITEM, sa.Column("accepted_at", sa.DateTime(timezone=True)), schema=C)
    op.add_column(ITEM, sa.Column("accepted_by", sa.Uuid()), schema=C)
    op.create_foreign_key(
        f"fk_{ITEM}_accepted_by_user_account",
        ITEM,
        "user_account",
        ["accepted_by"],
        ["id"],
        source_schema=C,
        referent_schema="identity",
    )


def downgrade() -> None:
    op.drop_constraint(f"fk_{ITEM}_accepted_by_user_account", ITEM, schema=C)
    op.drop_column(ITEM, "accepted_by", schema=C)
    op.drop_column(ITEM, "accepted_at", schema=C)
