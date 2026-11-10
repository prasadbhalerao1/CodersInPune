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
    ForeignKeyConstraint,
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
ROLES: Final = (
    "owner",
    "admin",
    "member",
    "guest",
    "auditor",
    "continuity_manager",
    "knowledge_steward",
    "team_manager",
)
MEMBER_TYPES: Final = ("employee", "contractor", "external")
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
        CheckConstraint(_in("member_type", MEMBER_TYPES), name="member_type"),
        Index(None, "user_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    member_type: Mapped[str] = mapped_column(Text, server_default="employee")
    # Self-reported at sign-in; for display only, never for authorization.
    display_name: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
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
        ForeignKey("platform.tenant.id", ondelete="CASCADE", deferrable=True, initially="DEFERRED")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Invitation(Base):
    """Invitation bound to a normalised email; accepting requires that verified email."""

    __tablename__ = "invitation"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("email = lower(email) AND email LIKE '%_@_%'", name="email"),
        CheckConstraint(_in("role", ROLES), name="role"),
        CheckConstraint("status IN ('pending', 'accepted', 'revoked')", name="status"),
        Index(
            "uq_invitation_pending_email",
            "tenant_id",
            "email",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    email: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    workspace_name: Mapped[str] = mapped_column(Text)
    workos_invitation_id: Mapped[str | None] = mapped_column(Text)
    invited_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    accepted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("identity.user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MembershipTeamScope(Base):
    """A team a team manager manages: they manage responsibilities those teams hold."""

    __tablename__ = "membership_team_scope"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "user_id", "team_id"),
        ForeignKeyConstraint(
            ["tenant_id", "team_id"],
            ["directory.team.tenant_id", "directory.team.id"],
            name="fk_membership_team_scope_team",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    team_id: Mapped[uuid.UUID]
    granted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
