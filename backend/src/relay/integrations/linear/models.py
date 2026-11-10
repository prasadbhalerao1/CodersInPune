"""Linear integration records (read-only). See migration 0018."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "integrations"
_UUIDV7 = text("uuidv7()")
_USER = "identity.user_account.id"


def _fk(columns: list[str], target: str, name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["tenant_id", *columns], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


class LinearConnectState(Base):
    __tablename__ = "linear_connect_state"
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


class LinearConnection(Base):
    __tablename__ = "linear_connection"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "organization_id"),
        CheckConstraint("status IN ('active', 'revoked', 'disconnected')", name="status"),
        CheckConstraint(
            "last_sync_status IN ('never', 'queued', 'ok', 'partial', 'error')",
            name="last_sync_status",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    organization_id: Mapped[str] = mapped_column(Text)
    organization_name: Mapped[str] = mapped_column(Text)
    url_key: Mapped[str | None] = mapped_column(Text)
    token_ciphertext: Mapped[str | None] = mapped_column(Text)
    refresh_token_ciphertext: Mapped[str | None] = mapped_column(Text)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, server_default="active")
    connected_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str] = mapped_column(Text, server_default="never")
    # Paused: credentials and data are kept, but no sync runs.
    paused: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Source snapshots are purged 30 days after this (connectors.purge_disconnected).
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_error: Mapped[str | None] = mapped_column(Text)
    next_reconcile_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LinearTeam(Base):
    __tablename__ = "linear_team"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "linear_id"),
        _fk(["connection_ref"], "integrations.linear_connection", "fk_linear_team_connection"),
        _fk(["team_id"], "directory.team", "fk_linear_team_team"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    connection_ref: Mapped[uuid.UUID]
    linear_id: Mapped[str] = mapped_column(Text)
    key: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    team_id: Mapped[uuid.UUID | None]
    removed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class LinearProject(Base):
    __tablename__ = "linear_project"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "linear_id"),
        _fk(["connection_ref"], "integrations.linear_connection", "fk_linear_project_connection"),
        _fk(["responsibility_id"], "catalog.responsibility", "fk_linear_project_responsibility"),
        CheckConstraint("audience IN ('workspace', 'managers')", name="audience"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    connection_ref: Mapped[uuid.UUID]
    linear_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    lead_linear_id: Mapped[str | None] = mapped_column(Text)
    team_linear_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    responsibility_id: Mapped[uuid.UUID | None]
    # Who in Relay may see this project's issues (migration 0037).
    audience: Mapped[str] = mapped_column(Text, server_default="managers")
    removed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LinearIdentity(Base):
    __tablename__ = "linear_identity"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "linear_id"),
        _fk(["person_id"], "directory.person", "fk_linear_identity_person"),
        _fk(["suggested_person_id"], "directory.person", "fk_linear_identity_suggested_person"),
        CheckConstraint(
            "link_status IN ('unmatched', 'suggested', 'linked', 'dismissed')", name="link_status"
        ),
        CheckConstraint("(link_status = 'linked') = (person_id IS NOT NULL)", name="linked_person"),
        Index(
            "uq_linear_identity_tenant_id_person_id",
            "tenant_id",
            "person_id",
            unique=True,
            postgresql_where=text("person_id IS NOT NULL"),
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    linear_id: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    link_status: Mapped[str] = mapped_column(Text, server_default="unmatched")
    person_id: Mapped[uuid.UUID | None]
    suggested_person_id: Mapped[uuid.UUID | None]
    match_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LinearIssue(Base):
    """Issue metadata only; no descriptions or comments are fetched or stored."""

    __tablename__ = "linear_issue"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "linear_id"),
        _fk(["connection_ref"], "integrations.linear_connection", "fk_linear_issue_connection"),
        CheckConstraint("priority BETWEEN 0 AND 4", name="priority"),
        Index(None, "tenant_id", "project_linear_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    connection_ref: Mapped[uuid.UUID]
    linear_id: Mapped[str] = mapped_column(Text)
    identifier: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    state_type: Mapped[str] = mapped_column(Text)
    state_name: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, server_default="0")
    assignee_linear_id: Mapped[str | None] = mapped_column(Text)
    creator_linear_id: Mapped[str | None] = mapped_column(Text)
    team_linear_id: Mapped[str | None] = mapped_column(Text)
    project_linear_id: Mapped[str | None] = mapped_column(Text)
    parent_identifier: Mapped[str | None] = mapped_column(Text)
    labels: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    url: Mapped[str] = mapped_column(Text)
    li_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    li_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
