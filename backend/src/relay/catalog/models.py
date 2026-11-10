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
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "catalog"
CRITICALITIES: Final = ("critical", "high", "standard", "low")
ROLES: Final = ("primary", "co_owner", "backup", "temporary")
CHANGE_TYPES: Final = ("assigned", "ended", "extended", "corrected")
DEPENDENCY_TYPES: Final = ("depends_on", "feeds", "escalates_to", "shares_access")
KNOWLEDGE_KINDS: Final = (
    "note",
    "link",
    "document",
    "procedure",
    "context",
    "adr",
    "faq",
    "postmortem",
    "escalation_contact",
    "onboarding_resource",
    "project_overview",
)
PROVENANCES: Final = ("manual", "github", "linear", "notion", "import", "ai_accepted")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Responsibility(Base):
    __tablename__ = "responsibility"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 200", name="name_length"),
        CheckConstraint(_in("criticality", CRITICALITIES), name="criticality"),
        CheckConstraint("status IN ('active', 'archived', 'withdrawn')", name="status"),
        CheckConstraint(
            "review_cadence_days IS NULL OR review_cadence_days BETWEEN 7 AND 730",
            name="review_cadence_days",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "type_id"],
            ["catalog.responsibility_type.tenant_id", "catalog.responsibility_type.id"],
            name="fk_responsibility_type",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "accountable_person_id"],
            ["directory.person.tenant_id", "directory.person.id"],
            name="fk_responsibility_accountable_person",
        ),
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
    # Fail-closed: hidden (also by a row policy) from anyone who isn't a manager, granted
    # access, or a current holder.
    restricted: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    type_id: Mapped[uuid.UUID | None]
    escalation_path: Mapped[str | None] = mapped_column(Text)
    escalation_contact: Mapped[str | None] = mapped_column(Text)
    review_cadence_days: Mapped[int | None]
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identity.user_account.id")
    )
    needs_verification: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    procedures: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'"))
    access_prerequisites: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'"))
    # For team-owned critical responsibilities: the person to call.
    accountable_person_id: Mapped[uuid.UUID | None]


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


ASSET_TYPES: Final = (
    "repository",
    "service",
    "project",
    "process",
    "vendor",
    "document_collection",
    "customer_account",
    "infrastructure",
    "other",
)
ASSET_LIFECYCLES: Final = ("planned", "active", "deprecated", "retired")


class Asset(Base):
    """Something a responsibility stewards. Assets have no owners of their own (D1)."""

    __tablename__ = "asset"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 200", name="name_length"),
        CheckConstraint(_in("asset_type", ASSET_TYPES), name="asset_type"),
        CheckConstraint("status IN ('active', 'archived')", name="status"),
        CheckConstraint("url IS NULL OR url ~ '^https?://'", name="url_scheme"),
        CheckConstraint(
            "criticality IS NULL OR criticality IN ('critical', 'high', 'standard', 'low')",
            name="criticality",
        ),
        CheckConstraint(_in("lifecycle", ASSET_LIFECYCLES), name="lifecycle"),
        CheckConstraint(
            "external_source IS NULL "
            "OR external_source IN ('github', 'linear', 'notion', 'manual')",
            name="external_source",
        ),
        CheckConstraint("source_state IN ('available', 'unavailable')", name="source_state"),
        CheckConstraint("cardinality(tags) <= 20", name="tags"),
        Index("ix_asset_tags", "tags", postgresql_using="gin"),
        Index(None, "tenant_id", "status"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    name: Mapped[str] = mapped_column(Text)
    asset_type: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    criticality: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    lifecycle: Mapped[str] = mapped_column(Text, server_default="active")
    external_source: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)
    # Typed per asset type (see catalog.assets.METADATA_FIELDS).
    meta: Mapped[dict[str, str]] = mapped_column("metadata", JSONB, server_default=text("'{}'"))
    # "unavailable" when the external source no longer resolves (never silently dropped).
    source_state: Mapped[str] = mapped_column(Text, server_default="available")


class ResponsibilityAsset(Base):
    __tablename__ = "responsibility_asset"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "responsibility_id", "asset_id"),
        ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_responsibility_asset_responsibility",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "asset_id"],
            ["catalog.asset.tenant_id", "catalog.asset.id"],
            name="fk_responsibility_asset_asset",
        ),
        CheckConstraint("relationship IN ('stewards', 'uses')", name="relationship"),
        Index(None, "tenant_id", "asset_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    responsibility_id: Mapped[uuid.UUID]
    asset_id: Mapped[uuid.UUID]
    relationship: Mapped[str] = mapped_column(Text, server_default="stewards")
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


KNOWLEDGE_SEARCH = (
    "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(body, '')), 'B')"
)


class KnowledgeItem(Base):
    """Knowledge attached to a responsibility. Authorship and source are kept; freshness
    comes from `last_reviewed_at`. Only people author knowledge in this release."""

    __tablename__ = "knowledge_item"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_knowledge_item_responsibility",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "superseded_by_id"],
            ["catalog.knowledge_item.tenant_id", "catalog.knowledge_item.id"],
            name="fk_knowledge_item_superseded_by",
        ),
        CheckConstraint(_in("kind", KNOWLEDGE_KINDS), name="kind"),
        CheckConstraint("review_state IN ('draft', 'verified', 'disputed')", name="review_state"),
        CheckConstraint("review_state <> 'disputed' OR dispute_reason IS NOT NULL", name="dispute"),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from",
            name="validity",
        ),
        CheckConstraint(
            "superseded_by_id IS NULL OR superseded_by_id <> id", name="not_superseded_by_self"
        ),
        CheckConstraint(
            "applies_to IS NULL OR char_length(applies_to) <= 500", name="applies_to_length"
        ),
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint("body IS NULL OR char_length(body) <= 20000", name="body_length"),
        CheckConstraint("url IS NULL OR url ~ '^https?://'", name="url"),
        CheckConstraint("body IS NOT NULL OR url IS NOT NULL", name="has_content"),
        CheckConstraint("visibility IN ('workspace', 'managers')", name="visibility"),
        CheckConstraint("origin IN ('person', 'notion', 'ai')", name="origin"),
        CheckConstraint("status IN ('active', 'archived')", name="status"),
        Index(None, "tenant_id", "responsibility_id"),
        Index("ix_knowledge_item_search", "search", postgresql_using="gin"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    responsibility_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    visibility: Mapped[str] = mapped_column(Text, server_default="workspace")
    origin: Mapped[str] = mapped_column(Text, server_default="person")
    status: Mapped[str] = mapped_column(Text, server_default="active")
    author_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    last_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identity.user_account.id")
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    search: Mapped[str | None] = mapped_column(TSVECTOR, Computed(KNOWLEDGE_SEARCH, persisted=True))
    # Persisted review state; stale/expired/inaccessible are derived (catalog.knowledge).
    review_state: Mapped[str] = mapped_column(Text, server_default="draft")
    version: Mapped[int] = mapped_column(server_default="1")
    steward_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("identity.user_account.id")
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applies_to: Mapped[str | None] = mapped_column(Text)
    decision_rationale: Mapped[str | None] = mapped_column(Text)
    decision_approver: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_by_id: Mapped[uuid.UUID | None]
    dispute_reason: Mapped[str | None] = mapped_column(Text)
    disputed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("identity.user_account.id"))
    disputed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeVersion(Base):
    """Immutable snapshot of each version of a knowledge item (no UPDATE grant)."""

    __tablename__ = "knowledge_version"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "knowledge_item_id", "version"),
        ForeignKeyConstraint(
            ["tenant_id", "knowledge_item_id"],
            ["catalog.knowledge_item.tenant_id", "catalog.knowledge_item.id"],
            name="fk_knowledge_version_item",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    knowledge_item_id: Mapped[uuid.UUID]
    version: Mapped[int]
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    change_note: Mapped[str | None] = mapped_column(Text)
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeFeedback(Base):
    __tablename__ = "knowledge_feedback"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "knowledge_item_id"],
            ["catalog.knowledge_item.tenant_id", "catalog.knowledge_item.id"],
            name="fk_knowledge_feedback_item",
        ),
        CheckConstraint("kind IN ('stale', 'authoritative')", name="kind"),
        CheckConstraint("note IS NULL OR char_length(note) <= 2000", name="note_length"),
        Index(None, "tenant_id", "knowledge_item_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    knowledge_item_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResponsibilityType(Base):
    """Managed responsibility types (replacing free-text categories)."""

    __tablename__ = "responsibility_type"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "name"),
        CheckConstraint("char_length(name) BETWEEN 1 AND 80", name="name_length"),
        CheckConstraint(
            "review_cadence_days IS NULL OR review_cadence_days BETWEEN 7 AND 730",
            name="review_cadence_days",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    review_cadence_days: Mapped[int | None]
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResponsibilityAccess(Base):
    """An explicit grant to see a restricted responsibility."""

    __tablename__ = "responsibility_access"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "responsibility_id", "user_id"),
        ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_responsibility_access_responsibility",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    responsibility_id: Mapped[uuid.UUID]
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    granted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResponsibilityDependency(Base):
    __tablename__ = "responsibility_dependency"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_responsibility_dependency_responsibility",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "depends_on_responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_responsibility_dependency_target",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "depends_on_asset_id"],
            ["catalog.asset.tenant_id", "catalog.asset.id"],
            name="fk_responsibility_dependency_asset",
        ),
        CheckConstraint(
            "num_nonnulls(depends_on_responsibility_id, depends_on_asset_id) = 1",
            name="one_target",
        ),
        CheckConstraint(
            "depends_on_responsibility_id IS NULL "
            "OR depends_on_responsibility_id <> responsibility_id",
            name="not_self",
        ),
        CheckConstraint(_in("relationship", DEPENDENCY_TYPES), name="relationship"),
        CheckConstraint(_in("provenance", PROVENANCES), name="provenance"),
        Index(None, "tenant_id", "responsibility_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    responsibility_id: Mapped[uuid.UUID]
    depends_on_responsibility_id: Mapped[uuid.UUID | None]
    depends_on_asset_id: Mapped[uuid.UUID | None]
    relationship: Mapped[str] = mapped_column(Text)
    provenance: Mapped[str] = mapped_column(Text, server_default="manual")
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssetLink(Base):
    """An asset linked to knowledge, a case or a task."""

    __tablename__ = "asset_link"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "asset_id"],
            ["catalog.asset.tenant_id", "catalog.asset.id"],
            name="fk_asset_link_asset",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "knowledge_item_id"],
            ["catalog.knowledge_item.tenant_id", "catalog.knowledge_item.id"],
            name="fk_asset_link_knowledge_item",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "case_id"],
            ["continuity.continuity_case.tenant_id", "continuity.continuity_case.id"],
            name="fk_asset_link_case",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "task_id"],
            ["continuity.case_task.tenant_id", "continuity.case_task.id"],
            name="fk_asset_link_task",
        ),
        CheckConstraint("num_nonnulls(knowledge_item_id, case_id, task_id) = 1", name="one_target"),
        Index(None, "tenant_id", "asset_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=text("uuidv7()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    asset_id: Mapped[uuid.UUID]
    knowledge_item_id: Mapped[uuid.UUID | None]
    case_id: Mapped[uuid.UUID | None]
    task_id: Mapped[uuid.UUID | None]
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("identity.user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
