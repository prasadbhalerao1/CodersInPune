"""Append-only, tenant-scoped audit log.

The application role may only INSERT and SELECT (grants), and a trigger rejects UPDATE and
DELETE for every role. Metadata must be minimal identifiers and enums: never tokens,
secrets or user-authored content.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "audit"


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("actor_type IN ('user', 'system')", name="actor_type"),
        CheckConstraint(r"action ~ '^[a-z_]+(\.[a-z_]+)+$'", name="action_format"),
        CheckConstraint(
            "(actor_type = 'user') = (actor_user_id IS NOT NULL)", name="actor_consistency"
        ),
        Index(None, "tenant_id", "occurred_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    actor_type: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("identity.user_account.id"))
    action: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str | None] = mapped_column(Text)
    target_id: Mapped[uuid.UUID | None]
    details: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, server_default=text("'{}'::jsonb")
    )
