"""People and teams that can own responsibilities.

A person is a directory record, not a login: they need no WorkOS account or Relay
membership to be an owner. Linking a person to a Relay user is a later concern.
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

SCHEMA = "directory"
STATUSES: Final = ("active", "archived")


class Department(Base):
    """A lightweight grouping of people and teams (not an HR org chart)."""

    __tablename__ = "department"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "name"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 200", name="name_length"),
        CheckConstraint("status IN ('active', 'archived')", name="status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _department_fk(table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["tenant_id", "department_id"],
        ["directory.department.tenant_id", "directory.department.id"],
        name=f"fk_{table}_department",
    )


class Person(Base):
    __tablename__ = "person"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("char_length(display_name) BETWEEN 1 AND 200", name="display_name_length"),
        Index(
            "uq_person_tenant_id_github_login",
            "tenant_id",
            "github_login",
            unique=True,
            postgresql_where=text("github_login IS NOT NULL"),
        ),
        CheckConstraint("status IN ('active', 'archived')", name="status"),
        CheckConstraint(
            "manager_person_id IS NULL OR manager_person_id <> id", name="not_own_manager"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "manager_person_id"],
            ["directory.person.tenant_id", "directory.person.id"],
            name="fk_person_manager",
        ),
        _department_fk("person"),
        Index(None, "tenant_id", "department_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    department_id: Mapped[uuid.UUID | None]
    display_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    github_login: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    # Reporting line (who this person reports to).
    manager_person_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Team(Base):
    __tablename__ = "team"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 200", name="name_length"),
        Index(
            "uq_team_tenant_id_github_slug",
            "tenant_id",
            "github_slug",
            unique=True,
            postgresql_where=text("github_slug IS NOT NULL"),
        ),
        CheckConstraint("status IN ('active', 'archived')", name="status"),
        _department_fk("team"),
        Index(None, "tenant_id", "department_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    department_id: Mapped[uuid.UUID | None]
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    github_slug: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TeamMember(Base):
    __tablename__ = "team_member"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "team_id", "person_id"),
        ForeignKeyConstraint(
            ["tenant_id", "team_id"],
            ["directory.team.tenant_id", "directory.team.id"],
            name="fk_team_member_team",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "person_id"],
            ["directory.person.tenant_id", "directory.person.id"],
            name="fk_team_member_person",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    team_id: Mapped[uuid.UUID]
    person_id: Mapped[uuid.UUID]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DirectoryHistory(Base):
    """Append-only: when someone joined or left a team or department, and who recorded it."""

    __tablename__ = "directory_history"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "person_id"],
            ["directory.person.tenant_id", "directory.person.id"],
            name="fk_directory_history_person",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "team_id"],
            ["directory.team.tenant_id", "directory.team.id"],
            name="fk_directory_history_team",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "department_id"],
            ["directory.department.tenant_id", "directory.department.id"],
            name="fk_directory_history_department",
        ),
        CheckConstraint(
            "change IN ('joined_team', 'left_team', 'joined_department', 'left_department')",
            name="change",
        ),
        CheckConstraint("num_nonnulls(team_id, department_id) = 1", name="one_unit"),
        Index(None, "tenant_id", "person_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    person_id: Mapped[uuid.UUID]
    team_id: Mapped[uuid.UUID | None]
    department_id: Mapped[uuid.UUID | None]
    change: Mapped[str] = mapped_column(Text)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
