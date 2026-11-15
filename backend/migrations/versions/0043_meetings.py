"""meetings: transcripts and the decisions, actions, questions and risks found in them

`intelligence.meeting` keeps a meeting's notes or transcript as evidence;
`intelligence.meeting_item` holds each extracted item with the transcript lines it cites.
Items are proposals until a person accepts them.

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "intelligence"


def _base(table: str) -> list[sa.SchemaItem]:
    return [
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["platform.tenant.id"], name=f"fk_{table}_tenant_id_tenant"
        ),
        sa.UniqueConstraint("tenant_id", "id", name=f"uq_{table}_tenant_id_id"),
    ]


def _fk(cols: list[str], target: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", *cols], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


def _user(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.user_account.id"], name=f"fk_{table}_{column}_user_account"
    )


def _check(table: str, name: str, condition: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(condition, name=op.f(f"ck_{table}_{name}"))


def _ts(name: str, nullable: bool = False) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=None if nullable else sa.func.now(),
        nullable=nullable,
    )


def upgrade() -> None:
    t = "meeting"
    op.create_table(
        t,
        *_base(t),
        sa.Column("title", sa.Text(), nullable=False),
        _ts("held_at"),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column("responsibility_id", sa.Uuid(), nullable=True),
        sa.Column("case_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("extract_mode", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        _ts("created_at"),
        _fk(["responsibility_id"], "catalog.responsibility", "fk_meeting_responsibility"),
        _fk(["case_id"], "continuity.continuity_case", "fk_meeting_case"),
        _user(t, "created_by"),
        _check(t, "title_length", "char_length(title) BETWEEN 1 AND 200"),
        _check(t, "transcript_length", "char_length(transcript) BETWEEN 1 AND 60000"),
        _check(t, "mode", "extract_mode IS NULL OR extract_mode IN ('ai', 'rules')"),
        schema=S,
    )
    op.create_index("ix_meeting_tenant_id_held_at", t, ["tenant_id", "held_at"], schema=S)

    t = "meeting_item"
    op.create_table(
        t,
        *_base(t),
        sa.Column("meeting_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("owner_name", sa.Text(), nullable=True),
        sa.Column("due_text", sa.Text(), nullable=True),
        sa.Column("lines", JSONB(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="proposed", nullable=False),
        sa.Column("result_ref", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        _ts("reviewed_at", nullable=True),
        _ts("created_at"),
        _fk(["meeting_id"], "intelligence.meeting", "fk_meeting_item_meeting"),
        _user(t, "reviewed_by"),
        _check(t, "kind", "kind IN ('decision', 'action', 'question', 'risk')"),
        _check(t, "status", "status IN ('proposed', 'accepted', 'dismissed')"),
        _check(t, "source", "source IN ('ai', 'rules')"),
        _check(t, "text_length", "char_length(text) BETWEEN 1 AND 500"),
        schema=S,
    )
    op.create_index(
        "ix_meeting_item_tenant_id_meeting_id", t, ["tenant_id", "meeting_id"], schema=S
    )
    op.create_index(
        "ix_meeting_item_tenant_id_kind_status", t, ["tenant_id", "kind", "status"], schema=S
    )

    enable_tenant_rls(S, "meeting")
    grant_table(S, "meeting", app_role(), ["SELECT", "INSERT", "UPDATE"])
    # Re-extracting replaces the items nobody has reviewed yet.
    enable_tenant_rls(S, "meeting_item")
    grant_table(S, "meeting_item", app_role(), ["SELECT", "INSERT", "UPDATE", "DELETE"])


def downgrade() -> None:
    op.drop_table("meeting_item", schema=S)
    op.drop_table("meeting", schema=S)
