"""Workspace continuity policies. See migration 0020."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "governance"


class WorkspacePolicy(Base):
    """At most one row per workspace; no row means the defaults."""

    __tablename__ = "workspace_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id"),
        CheckConstraint("knowledge_review_days BETWEEN 7 AND 730", name="knowledge_review_days"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    critical_requires_backup: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    knowledge_review_days: Mapped[int] = mapped_column(Integer, server_default="90")
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
