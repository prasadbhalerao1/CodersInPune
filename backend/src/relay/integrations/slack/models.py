"""Slack: one incoming-webhook connection per workspace. See migration 0044."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy import text as sql
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "integrations"


class SlackConnection(Base):
    """Where Relay posts what people choose to share. The webhook URL is a secret: it is
    stored encrypted and never returned; only the channel label is shown."""

    __tablename__ = "slack_connection"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id"),
        CheckConstraint("char_length(channel) BETWEEN 1 AND 80", name="channel_length"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=sql("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    webhook_encrypted: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(Text)
    connected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("identity.user_account.id"))
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
