"""Responsibilities and their ownership history (Register D1, D25).

Ownership attaches only to responsibilities. Each assignment has a valid-time range
`[valid_from, valid_to)` (half-open; `valid_to` NULL = open-ended). The database enforces:
- at most one primary owner at any instant (EXCLUDE on overlapping primary ranges);
- an assignee holds at most one role on a responsibility at any instant;
- assignee is exactly one of person or team, both same-tenant (composite FKs).
Every assignment mutation also writes an append-only `ownership_assignment_change` row.
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

SCHEMA = "catalog"
CRITICALITIES: Final = ("critical", "high", "standard", "low")
ROLES: Final = ("primary", "co_owner", "backup", "temporary")
CHANGE_TYPES: Final = ("assigned", "ended", "extended")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Responsibility(Base):
    __tablename__ = "responsibility"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 200", name="name_length"),
        CheckConstraint(_in("criticality", CRITICALITIES), name="criticality"),
        CheckConstraint("status IN ('active', 'archived')", name="status"),
        Index(None, "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    criticality: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    version: Mapped[int] = mapped_column(server_default="1")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OwnershipAssignment(Base):
    __tablename__ = "ownership_assignment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_ownership_assignment_responsibility",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "person_id"],
            ["directory.person.tenant_id", "directory.person.id"],
            name="fk_ownership_assignment_person",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "team_id"],
            ["directory.team.tenant_id", "directory.team.id"],
            name="fk_ownership_assignment_team",
        ),
        CheckConstraint(_in("role", ROLES), name="role"),
        CheckConstraint("num_nonnulls(person_id, team_id) = 1", name="one_assignee"),
        CheckConstraint("valid_to IS NULL OR valid_to > valid_from", name="valid_range"),
        CheckConstraint("role <> 'temporary' OR valid_to IS NOT NULL", name="temporary_bounded"),
        Index(None, "tenant_id", "responsibility_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    responsibility_id: Mapped[uuid.UUID]
    role: Mapped[str] = mapped_column(Text)
    person_id: Mapped[uuid.UUID | None]
    team_id: Mapped[uuid.UUID | None]
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OwnershipAssignmentChange(Base):
    """Append-only record of who changed an assignment, when and why (D25)."""

    __tablename__ = "ownership_assignment_change"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["catalog.ownership_assignment.tenant_id", "catalog.ownership_assignment.id"],
            name="fk_assignment_change_assignment",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_assignment_change_responsibility",
        ),
        CheckConstraint(_in("change_type", CHANGE_TYPES), name="change_type"),
        Index(
            "ix_assignment_change_responsibility_changed_at",
            "tenant_id",
            "responsibility_id",
            "changed_at",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    assignment_id: Mapped[uuid.UUID]
    responsibility_id: Mapped[uuid.UUID]
    change_type: Mapped[str] = mapped_column(Text)
    # Snapshot of the assignment's period after the change.
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
