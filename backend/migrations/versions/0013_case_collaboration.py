"""case collaboration: comments, @mentions and the emergency flag

- continuity.case_comment: human notes on a case (append-only: no UPDATE/DELETE grant).
- continuity.case_mention: workspace members mentioned in a comment.
- continuity_case.emergency: marks a case as urgent. It changes visibility and ordering
  only; no permission, approval or ownership rule is relaxed.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base(table: str) -> list[sa.SchemaItem]:
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{table}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{table}_tenant_id_id"),
    ]


def upgrade() -> None:
    role = app_role()
    op.create_table(
        "case_comment",
        *_base("case_comment"),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["continuity.continuity_case.tenant_id", "continuity.continuity_case.id"],
            name="fk_case_comment_case",
        ),
        sa.ForeignKeyConstraint(
            ["author_user_id"],
            ["identity.user_account.id"],
            name="fk_case_comment_author_user_id_user_account",
        ),
        sa.CheckConstraint(
            "char_length(body) BETWEEN 1 AND 5000", name=op.f("ck_case_comment_body_length")
        ),
        schema="continuity",
    )
    op.create_index(
        "ix_case_comment_tenant_id_case_id",
        "case_comment",
        ["tenant_id", "case_id"],
        schema="continuity",
    )
    enable_tenant_rls("continuity", "case_comment")
    grant_table("continuity", "case_comment", role, ["SELECT", "INSERT"])

    op.create_table(
        "case_mention",
        *_base("case_mention"),
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "comment_id"],
            ["continuity.case_comment.tenant_id", "continuity.case_comment.id"],
            name="fk_case_mention_comment",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["identity.user_account.id"], name="fk_case_mention_user_id_user_account"
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "comment_id",
            "user_id",
            name="uq_case_mention_tenant_id_comment_id_user_id",
        ),
        schema="continuity",
    )
    enable_tenant_rls("continuity", "case_mention")
    grant_table("continuity", "case_mention", role, ["SELECT", "INSERT"])

    op.add_column(
        "continuity_case",
        sa.Column("emergency", sa.Boolean(), server_default=sa.false(), nullable=False),
        schema="continuity",
    )
    op.add_column(
        "continuity_case",
        sa.Column("emergency_reason", sa.Text(), nullable=True),
        schema="continuity",
    )
    op.create_check_constraint(
        op.f("ck_continuity_case_emergency_reason"),
        "continuity_case",
        "NOT emergency OR emergency_reason IS NOT NULL",
        schema="continuity",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_continuity_case_emergency_reason"),
        "continuity_case",
        schema="continuity",
        type_="check",
    )
    op.drop_column("continuity_case", "emergency_reason", schema="continuity")
    op.drop_column("continuity_case", "emergency", schema="continuity")
    op.drop_table("case_mention", schema="continuity")
    op.drop_table("case_comment", schema="continuity")
