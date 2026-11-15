"""responsibility knowledge and case handover records

- catalog.knowledge_item: notes, links, documents, procedures and operational context on
  a responsibility. Authorship and source URL are kept; `last_reviewed_*` drives
  freshness. `origin` records where content came from (people only, in this release)
  so generated content can never pass silently as reviewed knowledge. Full-text search
  via a generated tsvector (PostgreSQL FTS; no embeddings).
- continuity.case_knowledge: what was handed over, or noted as missing, during a case.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSVECTOR

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH = (
    "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(body, '')), 'B')"
)


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


def _ts(name: str, nullable: bool = False) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=None if nullable else sa.func.now(),
        nullable=nullable,
    )


def _user(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.user_account.id"], name=f"fk_{table}_{column}_user_account"
    )


def upgrade() -> None:
    role = app_role()
    op.create_table(
        "knowledge_item",
        *_base("knowledge_item"),
        sa.Column("responsibility_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("visibility", sa.Text(), server_default="workspace", nullable=False),
        sa.Column("origin", sa.Text(), server_default="person", nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("last_reviewed_by", sa.Uuid(), nullable=True),
        _ts("last_reviewed_at", nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("search", TSVECTOR(), sa.Computed(SEARCH, persisted=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_knowledge_item_responsibility",
        ),
        _user("knowledge_item", "author_user_id"),
        _user("knowledge_item", "last_reviewed_by"),
        sa.CheckConstraint(
            "kind IN ('note', 'link', 'document', 'procedure', 'context')",
            name=op.f("ck_knowledge_item_kind"),
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 200", name=op.f("ck_knowledge_item_title_length")
        ),
        sa.CheckConstraint(
            "body IS NULL OR char_length(body) <= 20000", name=op.f("ck_knowledge_item_body_length")
        ),
        sa.CheckConstraint("url IS NULL OR url ~ '^https?://'", name=op.f("ck_knowledge_item_url")),
        sa.CheckConstraint(
            "body IS NOT NULL OR url IS NOT NULL", name=op.f("ck_knowledge_item_has_content")
        ),
        sa.CheckConstraint(
            "visibility IN ('workspace', 'managers')", name=op.f("ck_knowledge_item_visibility")
        ),
        sa.CheckConstraint("origin IN ('person')", name=op.f("ck_knowledge_item_origin")),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name=op.f("ck_knowledge_item_status")
        ),
        schema="catalog",
    )
    op.create_index(
        "ix_knowledge_item_tenant_id_responsibility_id",
        "knowledge_item",
        ["tenant_id", "responsibility_id"],
        schema="catalog",
    )
    op.create_index(
        "ix_knowledge_item_search",
        "knowledge_item",
        ["search"],
        schema="catalog",
        postgresql_using="gin",
    )
    enable_tenant_rls("catalog", "knowledge_item")
    grant_table("catalog", "knowledge_item", role, ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "case_knowledge",
        *_base("case_knowledge"),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("responsibility_id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_item_id", sa.Uuid(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Uuid(), nullable=False),
        _ts("recorded_at"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["continuity.continuity_case.tenant_id", "continuity.continuity_case.id"],
            name="fk_case_knowledge_case",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_case_knowledge_responsibility",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "knowledge_item_id"],
            ["catalog.knowledge_item.tenant_id", "catalog.knowledge_item.id"],
            name="fk_case_knowledge_knowledge_item",
        ),
        _user("case_knowledge", "recorded_by"),
        sa.CheckConstraint(
            "outcome IN ('handed_over', 'missing')", name=op.f("ck_case_knowledge_outcome")
        ),
        sa.CheckConstraint(
            "outcome = 'missing' OR knowledge_item_id IS NOT NULL",
            name=op.f("ck_case_knowledge_item_required"),
        ),
        sa.CheckConstraint(
            "note IS NULL OR char_length(note) <= 4000", name=op.f("ck_case_knowledge_note_length")
        ),
        schema="continuity",
    )
    op.create_index(
        "uq_case_knowledge_tenant_id_case_id_knowledge_item_id",
        "case_knowledge",
        ["tenant_id", "case_id", "knowledge_item_id"],
        unique=True,
        schema="continuity",
        postgresql_where=sa.text("knowledge_item_id IS NOT NULL"),
    )
    enable_tenant_rls("continuity", "case_knowledge")
    grant_table("continuity", "case_knowledge", role, ["SELECT", "INSERT"])


def downgrade() -> None:
    op.drop_table("case_knowledge", schema="continuity")
    op.drop_table("knowledge_item", schema="catalog")
