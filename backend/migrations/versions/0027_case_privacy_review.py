"""case consent and privacy review

- continuity_case.excluded_sources: connected systems left out of this case's evidence
  (github, linear, notion). Relay's own records are always in scope.
- continuity_case.privacy_notice_at / _by: when a manager confirmed the data-use notice.
- case_review_item: what the case will share (a responsibility's handover, a knowledge
  item, a connected source), with whom (audience), and the outgoing owner's decision:
  pending, confirmed, corrected (with the correction) or disputed (with the reason).
  A dispute never deletes the source or its history; it narrows what the case shares.

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

C = "continuity"
CASE = "continuity_case"


def upgrade() -> None:
    role = app_role()
    op.add_column(
        CASE,
        sa.Column("excluded_sources", JSONB(), server_default=sa.text("'[]'"), nullable=False),
        schema=C,
    )
    op.add_column(
        CASE, sa.Column("privacy_notice_at", sa.DateTime(timezone=True), nullable=True), schema=C
    )
    op.add_column(CASE, sa.Column("privacy_notice_by", sa.Uuid(), nullable=True), schema=C)
    op.create_foreign_key(
        f"fk_{CASE}_privacy_notice_by_user_account",
        CASE,
        "user_account",
        ["privacy_notice_by"],
        ["id"],
        source_schema=C,
        referent_schema="identity",
    )

    t = "case_review_item"
    op.create_table(
        t,
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("audience", sa.Text(), nullable=False),
        sa.Column("reviewer_person_id", sa.Uuid(), nullable=True),
        sa.Column("decision", sa.Text(), server_default="pending", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{t}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{t}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{t}_tenant_id_id"),
        sa.UniqueConstraint(
            "tenant_id",
            "case_id",
            "subject_type",
            "subject_id",
            name="uq_case_review_item_tenant_id_case_id_subject_type_subject_id",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["continuity.continuity_case.tenant_id", "continuity.continuity_case.id"],
            name="fk_case_review_item_case",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "reviewer_person_id"],
            ["directory.person.tenant_id", "directory.person.id"],
            name="fk_case_review_item_reviewer",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["identity.user_account.id"], name=f"fk_{t}_decided_by_user_account"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["identity.user_account.id"], name=f"fk_{t}_created_by_user_account"
        ),
        sa.CheckConstraint(
            "subject_type IN ('responsibility', 'knowledge', 'source')",
            name=op.f(f"ck_{t}_subject_type"),
        ),
        sa.CheckConstraint(
            "audience IN ('case', 'workspace', 'managers')", name=op.f(f"ck_{t}_audience")
        ),
        sa.CheckConstraint(
            "decision IN ('pending', 'confirmed', 'corrected', 'disputed')",
            name=op.f(f"ck_{t}_decision"),
        ),
        sa.CheckConstraint(
            "decision IN ('pending', 'confirmed') OR note IS NOT NULL",
            name=op.f(f"ck_{t}_explained"),
        ),
        schema=C,
    )
    enable_tenant_rls(C, t)
    grant_table(C, t, role, ["SELECT", "INSERT", "UPDATE"])


def downgrade() -> None:
    op.drop_table("case_review_item", schema=C)
    op.drop_constraint(f"fk_{CASE}_privacy_notice_by_user_account", CASE, schema=C)
    for column in ("privacy_notice_by", "privacy_notice_at", "excluded_sources"):
        op.drop_column(CASE, column, schema=C)
