"""Relay users and workspace memberships.

WorkOS establishes identity (`workos_user_id`); Relay owns memberships and roles.
`user_account` and `workspace_creation_request` are global (not tenant-scoped) tables
protected by principal-based RLS; `membership` follows the tenant-table conventions.
"""

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

SCHEMA = "identity"
_UUIDV7 = text("uuidv7()")

# Workspace roles (Blueprint §F tier 1). Fine-grained permissions arrive with the
# permission registry; these values only constrain what can be stored.
ROLES: Final = ("owner", "admin", "member", "guest", "auditor")
STATUSES: Final = ("active", "suspended", "removed")
OWNER_ROLE: Final = "owner"
ACTIVE: Final = "active"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class UserAccount(Base):
    __tablename__ = "user_account"
    __table_args__ = (
        UniqueConstraint("workos_user_id"),
        CheckConstraint(
            "char_length(workos_user_id) BETWEEN 1 AND 255", name="workos_user_id_length"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    workos_user_id: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "membership"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "user_id"),
        CheckConstraint(_in("role", ROLES), name="role"),
        CheckConstraint(_in("status", STATUSES), name="status"),
        Index(None, "user_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkspaceCreationRequest(Base):
    """Idempotency record: one workspace per (user, Idempotency-Key)."""

    __tablename__ = "workspace_creation_request"
    __table_args__ = ({"schema": SCHEMA},)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("identity.user_account.id"), primary_key=True
    )
    idempotency_key: Mapped[str] = mapped_column(Text, primary_key=True)
    # Deferred so the claim can be inserted before the tenant row in one transaction.
    created_tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform.tenant.id", deferrable=True, initially="DEFERRED")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
