"""Workspace administration: data export, retention, and ownership transfer.

- Export is owner/admin only (member.manage + audit.read), stays inside the tenant (RLS),
  includes everything an admin can see (managers-only knowledge included, restricted
  responsibilities as the database allows them) and is itself audited.
- Retention purges operational records older than the workspace's retention period:
  read notifications, connector sync history and AI run step events. Audit events, cases,
  ownership history and knowledge versions are never purged by retention.
- Ownership transfer: only an owner can hand ownership to another active member; the
  previous owner becomes an admin, so the workspace always has an owner.
"""

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.audit.models import AuditEvent
from relay.catalog.models import KnowledgeItem, OwnershipAssignment, Responsibility
from relay.continuity.models import CaseScopeItem, CaseTask, ContinuityCase
from relay.directory.models import Person, Team
from relay.governance import service as governance
from relay.governance.models import ConnectorRun
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence.models import AgentRunEvent
from relay.notifications.models import Notification
from relay.policy.permissions import Permission, authorize, visible
from relay.risks.models import RiskRecord
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

EXPORT_VERSION = 1


class RetentionResult(BaseModel):
    retention_days: int
    notifications: int
    connector_runs: int
    ai_run_events: int


class TransferIn(StrictInput):
    user_id: uuid.UUID


def _rows(objects: Any, *fields: str) -> list[dict[str, Any]]:
    out = []
    for o in objects:
        row = {}
        for f in fields:
            value = getattr(o, f)
            row[f] = (
                value.isoformat()
                if isinstance(value, datetime)
                else (str(value) if isinstance(value, uuid.UUID) else value)
            )
        out.append(row)
    return out


async def export_workspace(access: WorkspaceAccess) -> dict[str, Any]:
    authorize(access, Permission.MEMBER_MANAGE)
    authorize(access, Permission.AUDIT_READ)
    s = access.session

    async def all_of(model: Any, *fields: str) -> list[dict[str, Any]]:
        rows = await s.scalars(
            select(model).where(visible(access, Permission.AUDIT_READ, model.tenant_id))
        )
        return _rows(rows, *fields)

    data = {
        "format": "relay-workspace-export",
        "version": EXPORT_VERSION,
        "workspace_id": str(access.tenant_id),
        "exported_at": datetime.now(UTC).isoformat(),
        "responsibilities": await all_of(
            Responsibility, "id", "name", "description", "criticality", "status", "restricted"
        ),
        "ownership": await all_of(
            OwnershipAssignment,
            "id",
            "responsibility_id",
            "role",
            "person_id",
            "team_id",
            "valid_from",
            "valid_to",
            "reason",
        ),
        "people": await all_of(Person, "id", "display_name", "email", "title", "status"),
        "teams": await all_of(Team, "id", "name", "status"),
        "cases": await all_of(
            ContinuityCase, "id", "case_type", "title", "status", "outcome", "starts_at"
        ),
        "case_scope": await all_of(
            CaseScopeItem, "id", "case_id", "responsibility_id", "role", "state"
        ),
        "tasks": await all_of(CaseTask, "id", "case_id", "title", "status", "due_at"),
        "knowledge": await all_of(
            KnowledgeItem,
            "id",
            "responsibility_id",
            "kind",
            "title",
            "body",
            "url",
            "visibility",
            "classification",
            "review_state",
            "version",
        ),
        "risks": await all_of(RiskRecord, "risk_key", "rule", "severity", "title", "status"),
        "audit": await all_of(
            AuditEvent, "occurred_at", "action", "actor_user_id", "target_type", "target_id"
        ),
    }
    audit.record(
        s,
        tenant_id=access.tenant_id,
        action="workspace.exported",
        actor_user_id=access.user_id,
        target_type="workspace",
        target_id=access.tenant_id,
        details={"version": EXPORT_VERSION},
    )
    return data


async def export_audit_csv(access: WorkspaceAccess) -> str:
    authorize(access, Permission.AUDIT_READ)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        ["occurred_at", "action", "actor_type", "actor_user_id", "target_type", "target_id"]
    )
    for e in await access.session.scalars(
        select(AuditEvent)
        .where(visible(access, Permission.AUDIT_READ, AuditEvent.tenant_id))
        .order_by(AuditEvent.occurred_at)
    ):
        writer.writerow(
            [
                e.occurred_at.isoformat(),
                e.action,
                e.actor_type,
                e.actor_user_id,
                e.target_type,
                e.target_id,
            ]
        )
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="audit.exported",
        actor_user_id=access.user_id,
        target_type="workspace",
        target_id=access.tenant_id,
        details={},
    )
    return out.getvalue()


async def purge(session: AsyncSession, now: datetime | None = None) -> RetentionResult:
    """Delete operational records past the retention period (tenant scoped by RLS)."""
    days = (await governance.current(session)).retention_days
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)
    notes = await session.execute(
        delete(Notification).where(
            Notification.read_at.is_not(None), Notification.created_at < cutoff
        )
    )
    runs = await session.execute(delete(ConnectorRun).where(ConnectorRun.finished_at < cutoff))
    events = await session.execute(delete(AgentRunEvent).where(AgentRunEvent.created_at < cutoff))
    return RetentionResult(
        retention_days=days,
        notifications=notes.rowcount,  # type: ignore[attr-defined]
        connector_runs=runs.rowcount,  # type: ignore[attr-defined]
        ai_run_events=events.rowcount,  # type: ignore[attr-defined]
    )


async def apply_retention(access: WorkspaceAccess) -> RetentionResult:
    authorize(access, Permission.POLICY_MANAGE)
    result = await purge(access.session)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="retention.applied",
        actor_user_id=access.user_id,
        target_type="workspace",
        target_id=access.tenant_id,
        details=result.model_dump(),
    )
    return result


async def transfer_ownership(access: WorkspaceAccess, data: TransferIn) -> None:
    authorize(access, Permission.MEMBER_MANAGE)
    if access.role != "owner":
        raise ApiError(403, "owner_required", "Only an owner can transfer ownership.")
    if data.user_id == access.user_id:
        raise ApiError(409, "already_owner", "You already own this workspace.")
    target = await access.session.scalar(
        select(Membership).where(Membership.user_id == data.user_id).with_for_update()
    )
    if target is None or target.status != "active":
        raise ApiError(422, "not_a_member", "Transfer ownership to an active member.")
    me = await access.session.scalar(
        select(Membership).where(Membership.user_id == access.user_id).with_for_update()
    )
    assert me is not None
    target.role, me.role = "owner", "admin"
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="workspace.ownership_transferred",
        actor_user_id=access.user_id,
        target_type="membership",
        target_id=target.id,
        details={"to_user_id": str(data.user_id)},
    )
