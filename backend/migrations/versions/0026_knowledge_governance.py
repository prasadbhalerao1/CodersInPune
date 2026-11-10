"""knowledge governance: versions, review states, stewards, decisions, feedback

- knowledge_item: kinds adr, faq, postmortem, escalation_contact, onboarding_resource and
  project_overview; review_state (draft | verified | disputed; stale, expired and
  inaccessible are derived); steward (separate from the author); validity window and
  applicability; decision lineage (rationale, approver, decided, superseded by);
  dispute reason; version counter.
- knowledge_version: immutable snapshot of every version (append-only).
- knowledge_feedback: people flag an item stale or confirm it authoritative (append-only).

Existing person-authored items become verified (they were reviewed by their authors);
imported (Notion) and AI items start as drafts, so nothing imported is trusted until a
person reviews it. The backfill runs with FORCE RLS lifted for the owner inside this
migration's transaction only.

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CAT = "catalog"
ITEM = "knowledge_item"
OLD_KINDS = ("note", "link", "document", "procedure", "context")
KINDS = (
    *OLD_KINDS,
    "adr",
    "faq",
    "postmortem",
    "escalation_contact",
    "onboarding_resource",
    "project_overview",
)


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


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


def _item_fk(table: str, column: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", column],
        ["catalog.knowledge_item.tenant_id", "catalog.knowledge_item.id"],
        name=name,
    )


def _user(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.user_account.id"], name=f"fk_{table}_{column}_user_account"
    )


def _user_fk(column: str) -> None:
    op.create_foreign_key(
        f"fk_{ITEM}_{column}_user_account",
        ITEM,
        "user_account",
        [column],
        ["id"],
        source_schema=CAT,
        referent_schema="identity",
    )


def _ts(name: str, nullable: bool = False) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=None if nullable else sa.func.now(),
        nullable=nullable,
    )


def upgrade() -> None:
    role = app_role()
    add = op.add_column
    add(
        ITEM,
        sa.Column("review_state", sa.Text(), server_default="draft", nullable=False),
        schema=CAT,
    )
    add(ITEM, sa.Column("version", sa.Integer(), server_default="1", nullable=False), schema=CAT)
    add(ITEM, sa.Column("steward_user_id", sa.Uuid(), nullable=True), schema=CAT)
    add(ITEM, _ts("valid_from", nullable=True), schema=CAT)
    add(ITEM, _ts("valid_until", nullable=True), schema=CAT)
    add(ITEM, sa.Column("applies_to", sa.Text(), nullable=True), schema=CAT)
    add(ITEM, sa.Column("decision_rationale", sa.Text(), nullable=True), schema=CAT)
    add(ITEM, sa.Column("decision_approver", sa.Text(), nullable=True), schema=CAT)
    add(ITEM, _ts("decided_at", nullable=True), schema=CAT)
    add(ITEM, sa.Column("superseded_by_id", sa.Uuid(), nullable=True), schema=CAT)
    add(ITEM, sa.Column("dispute_reason", sa.Text(), nullable=True), schema=CAT)
    add(ITEM, sa.Column("disputed_by", sa.Uuid(), nullable=True), schema=CAT)
    add(ITEM, _ts("disputed_at", nullable=True), schema=CAT)
    _user_fk("steward_user_id")
    _user_fk("disputed_by")
    op.create_foreign_key(
        "fk_knowledge_item_superseded_by",
        ITEM,
        ITEM,
        ["tenant_id", "superseded_by_id"],
        ["tenant_id", "id"],
        source_schema=CAT,
        referent_schema=CAT,
    )
    op.drop_constraint("ck_knowledge_item_kind", ITEM, schema=CAT)
    for name, condition in (
        ("kind", _in("kind", KINDS)),
        ("review_state", _in("review_state", ("draft", "verified", "disputed"))),
        ("dispute", "review_state <> 'disputed' OR dispute_reason IS NOT NULL"),
        ("validity", "valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from"),
        ("not_superseded_by_self", "superseded_by_id IS NULL OR superseded_by_id <> id"),
        ("applies_to_length", "applies_to IS NULL OR char_length(applies_to) <= 500"),
    ):
        op.create_check_constraint(op.f(f"ck_{ITEM}_{name}"), ITEM, condition, schema=CAT)

    t = "knowledge_version"
    op.create_table(
        t,
        *_base(t),
        sa.Column("knowledge_item_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        _ts("changed_at"),
        _item_fk(t, "knowledge_item_id", "fk_knowledge_version_item"),
        _user(t, "changed_by"),
        sa.UniqueConstraint(
            "tenant_id",
            "knowledge_item_id",
            "version",
            name="uq_knowledge_version_tenant_id_knowledge_item_id_version",
        ),
        schema=CAT,
    )

    t = "knowledge_feedback"
    op.create_table(
        t,
        *_base(t),
        sa.Column("knowledge_item_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _item_fk(t, "knowledge_item_id", "fk_knowledge_feedback_item"),
        _user(t, "user_id"),
        sa.CheckConstraint("kind IN ('stale', 'authoritative')", name=op.f(f"ck_{t}_kind")),
        sa.CheckConstraint(
            "note IS NULL OR char_length(note) <= 2000", name=op.f(f"ck_{t}_note_length")
        ),
        schema=CAT,
    )
    op.create_index(
        f"ix_{t}_tenant_id_knowledge_item_id", t, ["tenant_id", "knowledge_item_id"], schema=CAT
    )

    for table in ("knowledge_version", "knowledge_feedback"):
        enable_tenant_rls(CAT, table)
        grant_table(CAT, table, role, ["SELECT", "INSERT"])  # append-only

    # Backfill across every tenant: the owner bypasses RLS only while FORCE is lifted.
    op.execute(f"ALTER TABLE {CAT}.{ITEM} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {CAT}.knowledge_version NO FORCE ROW LEVEL SECURITY")
    op.execute(
        f"UPDATE {CAT}.{ITEM} SET review_state = "
        "CASE WHEN origin = 'person' THEN 'verified' ELSE 'draft' END"
    )
    op.execute(
        f"INSERT INTO {CAT}.knowledge_version "
        "(tenant_id, knowledge_item_id, version, kind, title, body, url, changed_by, changed_at) "
        "SELECT tenant_id, id, 1, kind, title, body, url, author_user_id, updated_at "
        f"FROM {CAT}.{ITEM}"
    )
    op.execute(f"ALTER TABLE {CAT}.knowledge_version FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {CAT}.{ITEM} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("knowledge_feedback", schema=CAT)
    op.drop_table("knowledge_version", schema=CAT)
    for name in (
        "review_state",
        "dispute",
        "validity",
        "not_superseded_by_self",
        "applies_to_length",
        "kind",
    ):
        op.drop_constraint(f"ck_{ITEM}_{name}", ITEM, schema=CAT)
    op.create_check_constraint(op.f(f"ck_{ITEM}_kind"), ITEM, _in("kind", OLD_KINDS), schema=CAT)
    op.drop_constraint("fk_knowledge_item_superseded_by", ITEM, schema=CAT)
    for column in ("steward_user_id", "disputed_by"):
        op.drop_constraint(f"fk_{ITEM}_{column}_user_account", ITEM, schema=CAT)
    for column in (
        "disputed_at",
        "disputed_by",
        "dispute_reason",
        "superseded_by_id",
        "decided_at",
        "decision_approver",
        "decision_rationale",
        "applies_to",
        "valid_until",
        "valid_from",
        "steward_user_id",
        "version",
        "review_state",
    ):
        op.drop_column(ITEM, column, schema=CAT)
