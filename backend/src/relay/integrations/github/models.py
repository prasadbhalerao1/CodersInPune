"""GitHub integration records. No GitHub credentials are persisted here.

Installation tokens are minted from the App's private key for each sync and discarded;
the installing user's OAuth token is used once to verify the installation and discarded.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relay.shared.db.base import Base

SCHEMA = "integrations"
_UUIDV7 = text("uuidv7()")
_USER = "identity.user_account.id"


class GitHubConnectState(Base):
    """Single-use CSRF state for the install flow, bound to workspace + user."""

    __tablename__ = "github_connect_state"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id", "state_hash", name="uq_github_connect_state_tenant_id_state_hash"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    state_hash: Mapped[str] = mapped_column(Text)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GitHubInstallation(Base):
    __tablename__ = "github_installation"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id",
            "installation_id",
            name="uq_github_installation_tenant_id_installation_id",
        ),
        CheckConstraint("status IN ('active', 'revoked', 'disconnected')", name="status"),
        CheckConstraint(
            "last_sync_status IN ('never', 'queued', 'ok', 'partial', 'error')",
            name="last_sync_status",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    installation_id: Mapped[int] = mapped_column(BigInteger)
    account_login: Mapped[str] = mapped_column(Text)
    account_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    connected_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(_USER))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str] = mapped_column(Text, server_default="never")
    # Paused: credentials and data are kept, but no sync runs.
    paused: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Source snapshots are purged 30 days after this (connectors.purge_disconnected).
    disconnected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_error: Mapped[str | None] = mapped_column(Text)


class GitHubRepository(Base):
    __tablename__ = "github_repository"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id", "github_repo_id", name="uq_github_repository_tenant_id_github_repo_id"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "installation_ref"],
            ["integrations.github_installation.tenant_id", "integrations.github_installation.id"],
            name="fk_github_repository_installation",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "responsibility_id"],
            ["catalog.responsibility.tenant_id", "catalog.responsibility.id"],
            name="fk_github_repository_responsibility",
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    installation_ref: Mapped[uuid.UUID]
    github_repo_id: Mapped[int] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(Text)
    html_url: Mapped[str] = mapped_column(Text)
    default_branch: Mapped[str | None] = mapped_column(Text)
    private: Mapped[bool] = mapped_column(Boolean)
    archived: Mapped[bool] = mapped_column(Boolean)
    selected: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    accessible: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    responsibility_id: Mapped[uuid.UUID | None]
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sync_error: Mapped[str | None] = mapped_column(Text)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OwnershipSuggestion(Base):
    """Evidence-backed proposal; approving it goes through the catalog's ownership service."""

    __tablename__ = "ownership_suggestion"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id", "repository_id", "handle", name="uq_ownership_suggestion_repository_handle"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "repository_id"],
            ["integrations.github_repository.tenant_id", "integrations.github_repository.id"],
            name="fk_ownership_suggestion_repository",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "assignment_id"],
            ["catalog.ownership_assignment.tenant_id", "catalog.ownership_assignment.id"],
            name="fk_ownership_suggestion_assignment",
        ),
        CheckConstraint("handle_type IN ('user', 'team', 'catalog')", name="handle_type"),
        CheckConstraint("proposed_role IN ('primary', 'co_owner', 'backup')", name="proposed_role"),
        CheckConstraint(
            "status IN ('open', 'approved', 'dismissed', 'deferred', 'withdrawn')", name="status"
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    repository_id: Mapped[uuid.UUID]
    handle: Mapped[str] = mapped_column(Text)
    handle_type: Mapped[str] = mapped_column(Text)
    proposed_role: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    evidence_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="open")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignment_id: Mapped[uuid.UUID | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def _fk(columns: list[str], target: str, name: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["tenant_id", *columns], [f"{target}.tenant_id", f"{target}.id"], name=name
    )


class GitHubIdentity(Base):
    """A GitHub user seen in evidence. Linked to a person only by an explicit decision."""

    __tablename__ = "github_identity"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "github_user_id"),
        _fk(["person_id"], "directory.person", "fk_github_identity_person"),
        _fk(["suggested_person_id"], "directory.person", "fk_github_identity_suggested_person"),
        CheckConstraint(
            "link_status IN ('unmatched', 'suggested', 'linked', 'dismissed')", name="link_status"
        ),
        CheckConstraint("(link_status = 'linked') = (person_id IS NOT NULL)", name="linked_person"),
        Index(
            "uq_github_identity_tenant_id_person_id",
            "tenant_id",
            "person_id",
            unique=True,
            postgresql_where=text("person_id IS NOT NULL"),
        ),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    github_user_id: Mapped[int] = mapped_column(BigInteger)
    login: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    public_email: Mapped[str | None] = mapped_column(Text)
    link_status: Mapped[str] = mapped_column(Text, server_default="unmatched")
    person_id: Mapped[uuid.UUID | None]
    suggested_person_id: Mapped[uuid.UUID | None]
    match_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(_USER))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GitHubTeam(Base):
    __tablename__ = "github_team"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "github_team_id"),
        _fk(
            ["installation_ref"], "integrations.github_installation", "fk_github_team_installation"
        ),
        _fk(["team_id"], "directory.team", "fk_github_team_team"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    installation_ref: Mapped[uuid.UUID]
    github_team_id: Mapped[int] = mapped_column(BigInteger)
    org_login: Mapped[str] = mapped_column(Text)
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    team_id: Mapped[uuid.UUID | None]
    removed: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GitHubTeamMember(Base):
    __tablename__ = "github_team_member"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "github_team_ref", "identity_ref"),
        _fk(["github_team_ref"], "integrations.github_team", "fk_github_team_member_team"),
        _fk(["identity_ref"], "integrations.github_identity", "fk_github_team_member_identity"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    github_team_ref: Mapped[uuid.UUID]
    identity_ref: Mapped[uuid.UUID]


class GitHubWorkItem(Base):
    """Pull request / issue metadata only: no bodies, comments, diffs or code."""

    __tablename__ = "github_work_item"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "repository_id", "kind", "number"),
        _fk(["repository_id"], "integrations.github_repository", "fk_github_work_item_repository"),
        CheckConstraint("kind IN ('pull_request', 'issue')", name="kind"),
        CheckConstraint("state IN ('open', 'closed', 'merged')", name="state"),
        Index(None, "tenant_id", "repository_id", "gh_updated_at"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    repository_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(Text)
    number: Mapped[int] = mapped_column(Integer)
    github_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)
    author_login: Mapped[str | None] = mapped_column(Text)
    assignee_logins: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    reviewer_logins: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    labels: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    html_url: Mapped[str] = mapped_column(Text)
    gh_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    gh_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookDelivery(Base):
    """One row per X-GitHub-Delivery per workspace: the dedupe key for redeliveries."""

    __tablename__ = "webhook_delivery"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "delivery_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    delivery_id: Mapped[str] = mapped_column(Text)
    event: Mapped[str] = mapped_column(Text)
    action: Mapped[str | None] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class GitHubInstallationRoute(Base):
    """installation id -> workspace, for routing webhooks (see migration 0015)."""

    __tablename__ = "github_installation_route"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "installation_id"),
        {"schema": SCHEMA},
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, server_default=_UUIDV7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform.tenant.id"))
    installation_id: Mapped[int] = mapped_column(BigInteger)
