import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
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
    action: str
    target_type: str | None
    target_id: uuid.UUID | None
    metadata: dict[str, Any]


async def list_events(access: WorkspaceAccess, *, limit: int = 50) -> list[AuditEventView]:
    authorize(access, Permission.AUDIT_READ)
    rows = await access.session.scalars(
        select(AuditEvent)
        .where(visible(access, Permission.AUDIT_READ, AuditEvent.tenant_id))
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    return [
        AuditEventView(
            id=e.id,
            occurred_at=e.occurred_at,
            actor_type=e.actor_type,
            actor_user_id=e.actor_user_id,
            action=e.action,
            target_type=e.target_type,
            target_id=e.target_id,
            metadata=e.details,
        )
        for e in rows
    ]
