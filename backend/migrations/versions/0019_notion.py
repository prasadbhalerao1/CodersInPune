"""Notion integration (read-only knowledge discovery)

- notion_connect_state / notion_connection: OAuth like Linear; the access token is stored
  encrypted (Fernet, server-side key) and never returned.
- notion_source: pages and databases shared with the integration. Nothing is imported
  until an admin maps a source to a responsibility and a visibility (fail closed).
- notion_page: each imported Notion page, with its Notion id, URL, last-edited time and
  a content revision (hash), linked to the knowledge item it feeds.
- catalog.knowledge_item: origin gains 'notion'; status gains 'withdrawn' (the page was
  deleted, unshared or unmapped in Notion; kept for history, hidden from search).

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from relay.shared.db.migration_ops import app_role, enable_tenant_rls, grant_table

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

S = "integrations"


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


def _fk(cols: list[str], target: str, name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["tenant_id", *cols], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


def _user(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["identity.user_account.id"], name=f"fk_{table}_{column}_user_account"
    )


def _finish(table: str, privileges: list[str]) -> None:
    enable_tenant_rls(S, table)
    grant_table(S, table, app_role(), privileges)


def _knowledge_checks(origin: str, status: str) -> None:
    for name, condition in (("origin", origin), ("status", status)):
        op.drop_constraint(f"ck_knowledge_item_{name}", "knowledge_item", schema="catalog")
        op.create_check_constraint(
            op.f(f"ck_knowledge_item_{name}"), "knowledge_item", condition, schema="catalog"
        )


def upgrade() -> None:
    _knowledge_checks(
        "origin IN ('person', 'notion')", "status IN ('active', 'archived', 'withdrawn')"
    )

    op.create_table(
        "notion_connect_state",
        *_base("notion_connect_state"),
        sa.Column("state_hash", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _ts("expires_at", nullable=False),
        _ts("used_at", nullable=True),
        _user("notion_connect_state", "user_id"),
        sa.UniqueConstraint(
            "tenant_id", "state_hash", name="uq_notion_connect_state_tenant_id_state_hash"
        ),
        schema=S,
    )
    _finish("notion_connect_state", ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "notion_connection",
        *_base("notion_connection"),
        sa.Column("workspace_id", sa.Text(), nullable=False),
        sa.Column("workspace_name", sa.Text(), nullable=False),
        sa.Column("token_ciphertext", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("connected_by", sa.Uuid(), nullable=False),
        _ts("created_at"),
        _ts("last_synced_at", nullable=True),
        sa.Column("last_sync_status", sa.Text(), server_default="never", nullable=False),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        _ts("next_reconcile_at", nullable=True),
        _user("notion_connection", "connected_by"),
        sa.UniqueConstraint(
            "tenant_id", "workspace_id", name="uq_notion_connection_tenant_id_workspace_id"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'revoked', 'disconnected')",
            name=op.f("ck_notion_connection_status"),
        ),
        sa.CheckConstraint(
            "last_sync_status IN ('never', 'queued', 'ok', 'partial', 'error')",
            name=op.f("ck_notion_connection_last_sync_status"),
        ),
        schema=S,
    )
    _finish("notion_connection", ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "notion_source",
        *_base("notion_source"),
        sa.Column("connection_ref", sa.Uuid(), nullable=False),
        sa.Column("notion_id", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        _ts("last_edited_at", nullable=True),
        sa.Column("removed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("responsibility_id", sa.Uuid(), nullable=True),
        sa.Column("visibility", sa.Text(), nullable=True),
        sa.Column("mapped_by", sa.Uuid(), nullable=True),
        _ts("mapped_at", nullable=True),
        _fk(["connection_ref"], "integrations.notion_connection", "fk_notion_source_connection"),
        _fk(["responsibility_id"], "catalog.responsibility", "fk_notion_source_responsibility"),
        _user("notion_source", "mapped_by"),
        sa.UniqueConstraint("tenant_id", "notion_id", name="uq_notion_source_tenant_id_notion_id"),
        sa.CheckConstraint("kind IN ('page', 'database')", name=op.f("ck_notion_source_kind")),
        sa.CheckConstraint(
            "visibility IS NULL OR visibility IN ('workspace', 'managers')",
            name=op.f("ck_notion_source_visibility"),
        ),
        sa.CheckConstraint(
            "(responsibility_id IS NULL) = (visibility IS NULL)",
            name=op.f("ck_notion_source_mapping_complete"),
        ),
        schema=S,
    )
    _finish("notion_source", ["SELECT", "INSERT", "UPDATE"])

    op.create_table(
        "notion_page",
        *_base("notion_page"),
        sa.Column("source_ref", sa.Uuid(), nullable=False),
        sa.Column("notion_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        _ts("last_edited_at", nullable=False),
        sa.Column("revision", sa.Text(), nullable=False),
        sa.Column("knowledge_item_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        _ts("synced_at"),
        _fk(["source_ref"], "integrations.notion_source", "fk_notion_page_source"),
        _fk(["knowledge_item_id"], "catalog.knowledge_item", "fk_notion_page_knowledge_item"),
        sa.UniqueConstraint("tenant_id", "notion_id", name="uq_notion_page_tenant_id_notion_id"),
        sa.CheckConstraint("status IN ('active', 'withdrawn')", name=op.f("ck_notion_page_status")),
        schema=S,
    )
    op.create_index(
        "ix_notion_page_tenant_id_source_ref", "notion_page", ["tenant_id", "source_ref"], schema=S
    )
    _finish("notion_page", ["SELECT", "INSERT", "UPDATE"])


def downgrade() -> None:
    for table in ("notion_page", "notion_source", "notion_connection", "notion_connect_state"):
        op.drop_table(table, schema=S)
    op.execute("UPDATE catalog.knowledge_item SET status = 'archived' WHERE status = 'withdrawn'")
    _knowledge_checks("origin IN ('person')", "status IN ('active', 'archived')")
