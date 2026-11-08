"""In-app notifications. Identifiers and enums only; titles are read at display time."""

import uuid
from datetime import datetime
from typing import Final

from sqlalchemy import (
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
