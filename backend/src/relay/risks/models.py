"""What people decided about each computed risk, and when its condition held."""

import uuid
from datetime import datetime
from typing import Final

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
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "risks"
STATUSES: Final = ("open", "acknowledged", "accepted", "resolved")


class RiskRecord(Base):
    __tablename__ = "risk_record"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "risk_key"),
        CheckConstraint(
            "status IN ('open', 'acknowledged', 'accepted', 'resolved')", name="status"
        ),
        CheckConstraint(
            "status <> 'accepted' OR (accepted_until IS NOT NULL AND note IS NOT NULL)",
            name="acceptance",
        ),
        CheckConstraint("severity IN ('high', 'medium', 'low')", name="severity"),
        Index(None, "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    risk_key: Mapped[str] = mapped_column(Text)
    rule: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="open")
    note: Mapped[str | None] = mapped_column(Text)
    accepted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("identity.user_account.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
