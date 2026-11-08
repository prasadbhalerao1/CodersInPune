"""In-app notifications. Identifiers and enums only; titles are read at display time."""

import uuid
from datetime import datetime
from typing import Final

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
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "notifications"
KINDS: Final = (
    "task_assigned",
    "task_due_soon",
    "task_overdue",
    "approval_requested",
    "mentioned",
    "case_update",
)
_USER = "identity.user_account.id"


class Notification(Base):
    __tablename__ = "notification"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "dedupe_key"),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["continuity.continuity_case.tenant_id", "continuity.continuity_case.id"],
            name="fk_notification_case",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["continuity.case_task.tenant_id", "continuity.case_task.id"],
            name="fk_notification_task",
        ),
        CheckConstraint(f"kind IN ({', '.join(repr(k) for k in KINDS)})", name="kind"),
        Index(None, "tenant_id", "recipient_user_id", "read_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    kind: Mapped[str] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
    case_id: Mapped[uuid.UUID]
    task_id: Mapped[uuid.UUID | None]
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    dedupe_key: Mapped[str] = mapped_column(Text)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


EMAIL_CATEGORIES: Final = ("tasks", "reminders", "approvals", "mentions", "case_updates")


class EmailPreference(Base):
    """A user's opt-out (or back in) for one category; no row means the default (on)."""

    __tablename__ = "email_preference"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "user_id", "category"),
        CheckConstraint(
            f"category IN ({', '.join(repr(c) for c in EMAIL_CATEGORIES)})", name="category"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    category: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmailDelivery(Base):
    """One email Relay intends to send; `idempotency_key` makes it send at most once."""

    __tablename__ = "email_delivery"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "idempotency_key"),
        ForeignKeyConstraint(
            ["tenant_id", "notification_id"],
            ["notifications.notification.tenant_id", "notifications.notification.id"],
            name="fk_email_delivery_notification",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "invitation_id"],
            ["identity.invitation.tenant_id", "identity.invitation.id"],
            name="fk_email_delivery_invitation",
        ),
        CheckConstraint("status IN ('pending', 'sent', 'failed', 'skipped')", name="status"),
        CheckConstraint("num_nonnulls(notification_id, invitation_id) = 1", name="subject"),
        Index(None, "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    idempotency_key: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    notification_id: Mapped[uuid.UUID | None]
    invitation_id: Mapped[uuid.UUID | None]
    recipient_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    recipient_email: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    provider_message_id: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
