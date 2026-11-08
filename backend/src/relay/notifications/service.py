"""Notifications for case workflows: requested in the domain transaction, delivered later.

`request()` only emits an outbox event (same transaction as the change that caused it).
The handler resolves recipients, drops the actor and anyone no longer an active member,
and inserts rows keyed by `dedupe_key`, so redelivery never notifies twice. Reminders are
the same event scheduled for later; the handler re-checks that the task is still open,
still assigned to the same person and still due at the same time.

Delivery is in-app only: Relay has no transactional email provider yet (WorkOS sends
invitation emails only), and notification content is never put in emails or metadata.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Literal

import procrastinate
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from relay.continuity.models import CaseTask, ContinuityCase
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.jobs import outbox
from relay.jobs.models import OutboxEvent
from relay.notifications.models import Notification
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.shared.api_types import StrictInput

EVENT = "notification.requested"
Kind = Literal[
    "task_assigned",
    "task_due_soon",
    "task_overdue",
    "approval_requested",
    "mentioned",
    "case_update",
]
# Audiences resolved at delivery time from current memberships.
Audience = Literal["approvers"]
DUE_SOON = timedelta(hours=24)


class NotificationView(BaseModel):
    id: uuid.UUID
    kind: str
    detail: str | None
    case_id: uuid.UUID
    case_title: str
    case_emergency: bool
    task_id: uuid.UUID | None
    task_title: str | None
    actor_name: str | None
    created_at: datetime
    read_at: datetime | None


class InboxView(BaseModel):
    unread: int
    items: list[NotificationView]


class MarkReadIn(StrictInput):
    ids: list[uuid.UUID] | None = None  # None marks everything read


async def request(
    session: AsyncSession,
    jobs: procrastinate.App,
    *,
    tenant_id: uuid.UUID,
    kind: Kind,
    case_id: uuid.UUID,
    dedupe: str,
    recipients: list[uuid.UUID] | None = None,
    audience: Audience | None = None,
    task_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    detail: str | None = None,
    schedule_at: datetime | None = None,
    due_at: datetime | None = None,
) -> None:
    payload: dict[str, Any] = {
        "kind": kind,
        "case_id": str(case_id),
        "dedupe": dedupe,
        "recipients": [str(r) for r in recipients or []],
        "audience": audience,
        "task_id": str(task_id) if task_id else None,
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "detail": detail,
        "due_at": due_at.isoformat() if due_at else None,
    }
    await outbox.emit(
        session,
        jobs,
        tenant_id=tenant_id,
        event_type=EVENT,
        payload=payload,
        schedule_at=schedule_at,
    )


async def request_task_notifications(
    session: AsyncSession, jobs: procrastinate.App, task: CaseTask, actor_user_id: uuid.UUID
) -> None:
    """Assignment now; due-soon and overdue reminders scheduled for later."""
    if task.assignee_user_id is None:
        return
    common: dict[str, Any] = {
        "tenant_id": task.tenant_id,
        "case_id": task.case_id,
        "task_id": task.id,
        "recipients": [task.assignee_user_id],
        "actor_user_id": actor_user_id,
    }
    await request(session, jobs, kind="task_assigned", dedupe=f"task_assigned:{task.id}", **common)
    if task.due_at is None:
        return
    now = datetime.now(task.due_at.tzinfo)
    if task.due_at - DUE_SOON > now:
        await request(
            session,
            jobs,
            kind="task_due_soon",
            dedupe=f"task_due_soon:{task.id}:{task.due_at.isoformat()}",
            schedule_at=task.due_at - DUE_SOON,
            due_at=task.due_at,
            **common,
        )
    await request(
        session,
        jobs,
        kind="task_overdue",
        dedupe=f"task_overdue:{task.id}:{task.due_at.isoformat()}",
        schedule_at=max(task.due_at, now),
        due_at=task.due_at,
        **common,
    )


async def _active_members(session: AsyncSession) -> dict[uuid.UUID, str]:
    rows = await session.execute(
        select(Membership.user_id, Membership.role).where(Membership.status == "active")
    )
    return {user_id: role for user_id, role in rows}


async def _still_due(session: AsyncSession, payload: dict[str, Any]) -> bool:
    task = await session.get(CaseTask, uuid.UUID(payload["task_id"]))
    case = await session.get(ContinuityCase, uuid.UUID(payload["case_id"]))
    return (
        task is not None
        and case is not None
        and case.status in ("draft", "planning", "executing")
        and task.status == "open"
        and str(task.assignee_user_id) in payload["recipients"]
        and task.due_at is not None
        and task.due_at.isoformat() == payload["due_at"]
    )


async def _deliver(session: AsyncSession, event: OutboxEvent, _ctx: outbox.JobContext) -> None:
    payload = event.payload
    if payload["kind"] in ("task_due_soon", "task_overdue") and not await _still_due(
        session, payload
    ):
        return
    members = await _active_members(session)
    recipients = {uuid.UUID(r) for r in payload["recipients"]}
    if payload.get("audience") == "approvers":
        recipients |= {
            u for u, role in members.items() if role_allows(role, Permission.CASE_APPROVE)
        }
    actor = uuid.UUID(payload["actor_user_id"]) if payload.get("actor_user_id") else None
    rows = [
        {
            "tenant_id": event.tenant_id,
            "recipient_user_id": user_id,
            "kind": payload["kind"],
            "detail": payload.get("detail"),
            "case_id": uuid.UUID(payload["case_id"]),
            "task_id": uuid.UUID(payload["task_id"]) if payload.get("task_id") else None,
            "actor_user_id": actor,
            "dedupe_key": f"{payload['dedupe']}:{user_id}",
        }
        for user_id in sorted(recipients)
        if user_id != actor and user_id in members
    ]
    if rows:
        await session.execute(
            insert(Notification)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["tenant_id", "dedupe_key"])
        )


outbox.register(EVENT, _deliver)


# ---------------------------------------------------------------- reading


async def inbox(access: WorkspaceAccess, *, unread_only: bool = False) -> InboxView:
    authorize(access, Permission.CASE_READ)
    mine = (
        visible(access, Permission.CASE_READ, Notification.tenant_id),
        Notification.recipient_user_id == access.user_id,
    )
    stmt = (
        select(Notification, ContinuityCase.title, ContinuityCase.emergency, CaseTask.title)
        .join(ContinuityCase, ContinuityCase.id == Notification.case_id)
        .outerjoin(CaseTask, CaseTask.id == Notification.task_id)
        .where(*mine)
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    rows = (
        await access.session.execute(
            stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(100)
        )
    ).all()
    names = dict(
        (
            await access.session.execute(
                select(Membership.user_id, func.coalesce(Membership.display_name, Membership.email))
            )
        ).all()
    )
    unread = await access.session.scalar(
        select(func.count()).select_from(Notification).where(*mine, Notification.read_at.is_(None))
    )
    return InboxView(
        unread=unread or 0,
        items=[
            NotificationView(
                id=n.id,
                kind=n.kind,
                detail=n.detail,
                case_id=n.case_id,
                case_title=case_title,
                case_emergency=emergency,
                task_id=n.task_id,
                task_title=task_title,
                actor_name=(names.get(n.actor_user_id) or "Member") if n.actor_user_id else None,
                created_at=n.created_at,
                read_at=n.read_at,
            )
            for n, case_title, emergency, task_title in rows
        ],
    )


async def mark_read(access: WorkspaceAccess, data: MarkReadIn) -> None:
    authorize(access, Permission.CASE_READ)
    stmt = update(Notification).where(
        visible(access, Permission.CASE_READ, Notification.tenant_id),
        Notification.recipient_user_id == access.user_id,
        Notification.read_at.is_(None),
    )
    if data.ids is not None:
        stmt = stmt.where(Notification.id.in_(data.ids))
    await access.session.execute(stmt.values(read_at=func.now()))
