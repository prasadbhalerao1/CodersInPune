"""Notion integration records (read-only). See migration 0019."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "integrations"
_UUIDV7 = text("uuidv7()")
_USER = "identity.user_account.id"


def _fk(columns: list[str], target: str, name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["tenant_id", *columns], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


class NotionConnectState(Base):
    __tablename__ = "notion_connect_state"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "state_hash"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    state_hash: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotionConnection(Base):
    __tablename__ = "notion_connection"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "workspace_id"),
        CheckConstraint("status IN ('active', 'revoked', 'disconnected')", name="status"),
        CheckConstraint(
            "last_sync_status IN ('never', 'queued', 'ok', 'partial', 'error')",
            name="last_sync_status",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    workspace_id: Mapped[str] = mapped_column(Text)
    workspace_name: Mapped[str] = mapped_column(Text)
    token_ciphertext: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    connected_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str] = mapped_column(Text, server_default="never")
    last_sync_error: Mapped[str | None] = mapped_column(Text)
    next_reconcile_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotionSource(Base):
    """A page or database shared with the integration. Imported only once mapped."""

    __tablename__ = "notion_source"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "notion_id"),
        _fk(["connection_ref"], "integrations.notion_connection", "fk_notion_source_connection"),
        _fk(["responsibility_id"], "catalog.responsibility", "fk_notion_source_responsibility"),
        CheckConstraint("kind IN ('page', 'database')", name="kind"),
        CheckConstraint(
            "visibility IS NULL OR visibility IN ('workspace', 'managers')", name="visibility"
        ),
        CheckConstraint(
            "(responsibility_id IS NULL) = (visibility IS NULL)", name="mapping_complete"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    connection_ref: Mapped[uuid.UUID]
    notion_id: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    last_edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    responsibility_id: Mapped[uuid.UUID | None]
    visibility: Mapped[str | None] = mapped_column(Text)
    mapped_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    mapped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotionPage(Base):
    """An imported page. `revision` hashes the imported text; unchanged means no write."""

    __tablename__ = "notion_page"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "notion_id"),
        _fk(["source_ref"], "integrations.notion_source", "fk_notion_page_source"),
        _fk(["knowledge_item_id"], "catalog.knowledge_item", "fk_notion_page_knowledge_item"),
        CheckConstraint("status IN ('active', 'withdrawn')", name="status"),
        Index(None, "tenant_id", "source_ref"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    source_ref: Mapped[uuid.UUID]
    notion_id: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    last_edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revision: Mapped[str] = mapped_column(Text)
    knowledge_item_id: Mapped[uuid.UUID]
    status: Mapped[str] = mapped_column(Text, server_default="active")
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
