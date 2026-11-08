import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit.models import AuditEvent
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible

MetadataValue = str | int | bool | None


def record(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action: str,
    actor_user_id: uuid.UUID | None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    details: dict[str, MetadataValue] | None = None,
) -> None:
    """Add an audit event to the caller's transaction (commits or rolls back with it).

    `actor_user_id=None` means the system (background jobs).
    """
    session.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_type="user" if actor_user_id else "system",
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
        )
    )


class AuditEventView(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    actor_type: str
    actor_user_id: uuid.UUID | None
    actor_name: str | None = None
    action: str
    target_type: str | None
    target_id: uuid.UUID | None
    target_label: str | None = None
    metadata: dict[str, Any]


async def _labels(
    session: AsyncSession, events: list[AuditEvent]
) -> dict[tuple[str, uuid.UUID], str]:
    """Display names for targets, read from their own tables (never stored in metadata)."""
    # Imported here: domain modules import this module to record events.
    from relay.catalog.models import Asset, Responsibility
    from relay.continuity.models import ContinuityCase
    from relay.directory.models import Department, Person, Team

    sources: dict[str, Select[uuid.UUID, str]] = {
        "responsibility": select(Responsibility.id, Responsibility.name),
        "asset": select(Asset.id, Asset.name),
        "continuity_case": select(ContinuityCase.id, ContinuityCase.title),
        "person": select(Person.id, Person.display_name),
        "team": select(Team.id, Team.name),
        "department": select(Department.id, Department.name),
    }
    labels: dict[tuple[str, uuid.UUID], str] = {}
    for target_type, stmt in sources.items():
        ids = {e.target_id for e in events if e.target_type == target_type and e.target_id}
        if ids:
            model_id = stmt.selected_columns[0]
            for row_id, label in await session.execute(stmt.where(model_id.in_(ids))):
                labels[(target_type, row_id)] = label
    return labels


async def list_events(
    access: WorkspaceAccess,
    *,
    limit: int = 50,
    category: str | None = None,
    actor_user_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    before: datetime | None = None,
) -> list[AuditEventView]:
    """Newest first. `category` is an action prefix such as "case" or "ownership";
    `before` pages backwards. Metadata holds identifiers and enums only (never content)."""
    from relay.identity.models import Membership

    authorize(access, Permission.AUDIT_READ)
    stmt = select(AuditEvent).where(visible(access, Permission.AUDIT_READ, AuditEvent.tenant_id))
    if category:
        stmt = stmt.where(AuditEvent.action.startswith(f"{category}.", autoescape=True))
    if actor_user_id:
        stmt = stmt.where(AuditEvent.actor_user_id == actor_user_id)
    if target_type:
        stmt = stmt.where(AuditEvent.target_type == target_type)
    if target_id:
        stmt = stmt.where(AuditEvent.target_id == target_id)
    if before:
        stmt = stmt.where(AuditEvent.occurred_at < before)
    events = list(
        await access.session.scalars(
            stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(limit)
        )
    )
    names = {
        user_id: name or email or "Member"
        for user_id, name, email in await access.session.execute(
            select(Membership.user_id, Membership.display_name, Membership.email).where(
                visible(access, Permission.MEMBER_READ, Membership.tenant_id)
            )
        )
    }
    labels = await _labels(access.session, events)
    return [
        AuditEventView(
            id=e.id,
            occurred_at=e.occurred_at,
            actor_type=e.actor_type,
            actor_user_id=e.actor_user_id,
            actor_name=(names.get(e.actor_user_id) or "Former member")
            if e.actor_user_id
            else "Relay",
            action=e.action,
            target_type=e.target_type,
            target_id=e.target_id,
            target_label=labels.get((e.target_type, e.target_id))
            if e.target_type and e.target_id
            else None,
            metadata=e.details,
        )
        for e in events
    ]
