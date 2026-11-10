"""Workspace continuity policies. See migration 0020."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
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


class SavedView(Base):
    """A person's named filter for a list page; `query` is the page's URL query string."""

    __tablename__ = "saved_view"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "user_id", "page", "name"),
        CheckConstraint(
            "page IN ('cases', 'responsibilities', 'assets', 'knowledge')", name="page"
        ),
        CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="name_length"),
        CheckConstraint("char_length(query) <= 1000", name="query_length"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    page: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    query: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CriticalityPolicy(Base):
    """Per criticality tier; no row means the built-in defaults (governance.service)."""

    __tablename__ = "criticality_policy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "criticality"),
        CheckConstraint(
            "criticality IN ('critical', 'high', 'standard', 'low')", name="criticality"
        ),
        CheckConstraint("review_days BETWEEN 7 AND 730", name="review_days"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    criticality: Mapped[str] = mapped_column(Text)
    requires_backup: Mapped[bool] = mapped_column(Boolean)
    review_days: Mapped[int] = mapped_column(Integer)
    requires_accountable_contact: Mapped[bool] = mapped_column(Boolean)
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
