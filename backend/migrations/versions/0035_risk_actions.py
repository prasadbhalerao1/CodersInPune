"""risk finding actions: an assignee and a linked case

- risks.risk_record.assignee_user_id: the member asked to fix the condition.
- risks.risk_record.case_id: the continuity case opened to resolve it (composite FK).

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "risks"
T = "risk_record"
ASSIGNEE_FK = "fk_risk_record_assignee_user_id_user_account"
CASE_FK = "fk_risk_record_tenant_id_case_id_continuity_case"
CASE_IX = "ix_risk_record_tenant_id_case_id"


def upgrade() -> None:
    op.add_column(T, sa.Column("assignee_user_id", sa.Uuid(), nullable=True), schema=S)
    op.add_column(T, sa.Column("case_id", sa.Uuid(), nullable=True), schema=S)
    op.create_foreign_key(
        ASSIGNEE_FK,
        T,
        "user_account",
        ["assignee_user_id"],
        ["id"],
        source_schema=S,
        referent_schema="identity",
    )
    op.create_foreign_key(
        CASE_FK,
        T,
        "continuity_case",
        ["tenant_id", "case_id"],
        ["tenant_id", "id"],
        source_schema=S,
        referent_schema="continuity",
    )
    op.create_index(CASE_IX, T, ["tenant_id", "case_id"], schema=S)


def downgrade() -> None:
    op.drop_index(CASE_IX, T, schema=S)
    op.drop_constraint(CASE_FK, T, schema=S, type_="foreignkey")
    op.drop_constraint(ASSIGNEE_FK, T, schema=S, type_="foreignkey")
    op.drop_column(T, "case_id", schema=S)
    op.drop_column(T, "assignee_user_id", schema=S)
