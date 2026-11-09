"""Email delivery: an extra channel for in-app notifications (still the source of truth).

Flow (all through the existing outbox and worker):
1. The in-app handler inserts notifications; for each new one whose recipient has the
   category enabled and an email on file, `queue_for_notifications` inserts an
   `email_delivery` row (unique idempotency key) and emits `email.send`.
2. `_send` locks the row; anything but `pending` is a no-op (duplicate delivery or a
   retry after success). Content is rendered at send time from current data, and only if
   the recipient is still an active member. The provider is called with the row's key as
   Idempotency-Key; the row becomes `sent` only after the provider accepts.
3. Transient failures raise, so the job retries with the outbox's bounded exponential
   backoff; the last attempt (or a permanent rejection) marks the row `failed` with a
   short error code. Admins can retry a failed delivery explicitly.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal

import httpx
import procrastinate
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.config import Settings
from relay.continuity.models import CaseTask, ContinuityCase
from relay.identity.models import Invitation, Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.jobs import outbox
from relay.jobs.models import OutboxEvent
from relay.notifications import email_templates
from relay.notifications.email_provider import (
    EmailMessage,
    EmailSendError,
    email_configured,
    provider_for,
)
from relay.notifications.models import (
    EMAIL_CATEGORIES,
    EmailDelivery,
    EmailPreference,
    Notification,
)
from relay.platform.models import Tenant
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

EVENT = "email.send"
MAX_ATTEMPTS = 5  # matches the outbox job's retry budget
Category = Literal["tasks", "reminders", "approvals", "mentions", "case_updates"]
CATEGORY_OF: dict[str, Category] = {
    "task_assigned": "tasks",
    "task_due_soon": "reminders",
    "task_overdue": "reminders",
    "approval_requested": "approvals",
    "mentioned": "mentions",
    "case_update": "case_updates",
}
CATEGORY_LABEL: dict[str, str] = {
    "tasks": "Tasks assigned to me",
    "reminders": "Due-soon and overdue reminders",
    "approvals": "Approval requests",
    "mentions": "Mentions",
    "case_updates": "Important case updates",
}


class PreferenceView(BaseModel):
    category: Category
    label: str
    enabled: bool


class PreferencesUpdate(StrictInput):
    preferences: dict[Category, bool]


class DeliveryView(BaseModel):
    id: uuid.UUID
    kind: str
    recipient: str
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime
    sent_at: datetime | None


class EmailStatusView(BaseModel):
    configured: bool
    provider: str | None = None
    sender: str | None
    healthy: bool
    sent_24h: int
    failed_24h: int
    pending: int
    recent_failures: list[DeliveryView]


async def _enabled_for(
    session: AsyncSession, users: set[uuid.UUID], category: str
) -> set[uuid.UUID]:
    off = set(
        await session.scalars(
            select(EmailPreference.user_id).where(
                EmailPreference.user_id.in_(users),
                EmailPreference.category == category,
                EmailPreference.enabled.is_(False),
            )
        )
    )
    return users - off


async def _queue(
    session: AsyncSession,
    jobs: procrastinate.App,
    tenant_id: uuid.UUID,
    *,
    key: str,
    kind: str,
    to: str,
    notification_id: uuid.UUID | None = None,
    invitation_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> None:
    delivery_id = await session.scalar(
        insert(EmailDelivery)
        .values(
            tenant_id=tenant_id,
            idempotency_key=key,
            kind=kind,
            notification_id=notification_id,
            invitation_id=invitation_id,
            recipient_user_id=user_id,
            recipient_email=to,
        )
        .on_conflict_do_nothing(index_elements=["tenant_id", "idempotency_key"])
        .returning(EmailDelivery.id)
    )
    if delivery_id is not None:  # already queued once: never queue twice
        await outbox.emit(
            session,
            jobs,
            tenant_id=tenant_id,
            event_type=EVENT,
            payload={"delivery_id": str(delivery_id)},
        )


async def queue_for_notifications(
    session: AsyncSession, ctx: outbox.JobContext, notifications: list[Notification]
) -> None:
    if not notifications or ctx.jobs is None or not email_configured(ctx.settings):
        return
    by_kind: dict[str, list[Notification]] = defaultdict(list)
    for n in notifications:
        if n.kind in CATEGORY_OF:  # automation alerts are in-app only in this release
            by_kind[CATEGORY_OF[n.kind]].append(n)
    emails = dict(
        (
            await session.execute(
                select(Membership.user_id, Membership.email).where(
                    Membership.user_id.in_({n.recipient_user_id for n in notifications}),
                    Membership.status == "active",
                    Membership.email.is_not(None),
                )
            )
        ).all()
    )
    for category, items in by_kind.items():
        allowed = await _enabled_for(session, {n.recipient_user_id for n in items}, category)
        for n in items:
            if n.recipient_user_id in allowed and emails.get(n.recipient_user_id):
                await _queue(
                    session,
                    ctx.jobs,
                    n.tenant_id,
                    key=f"notification:{n.id}",
                    kind=n.kind,
                    to=str(emails[n.recipient_user_id]),
                    notification_id=n.id,
                    user_id=n.recipient_user_id,
                )


async def queue_invitation(
    session: AsyncSession, jobs: procrastinate.App, invitation: Invitation
) -> None:
    await _queue(
        session,
        jobs,
        invitation.tenant_id,
        key=f"invitation:{invitation.id}",
        kind="invitation",
        to=invitation.email,
        invitation_id=invitation.id,
    )


# ---------------------------------------------------------------- sending


async def _render(
    session: AsyncSession, delivery: EmailDelivery, settings: Settings
) -> email_templates.Rendered | None:
    """Current content, or None if the email should no longer be sent."""
    tenant = await session.get(Tenant, delivery.tenant_id)
    if tenant is None:
        return None
    base = settings.frontend_base_url.rstrip("/")
    prefs_url = f"{base}/w/{tenant.id}/settings/notifications"
    if delivery.invitation_id:
        invitation = await session.get(Invitation, delivery.invitation_id)
        if invitation is None or invitation.status != "pending":
            return None
        inviter = await session.scalar(
            select(func.coalesce(Membership.display_name, Membership.email)).where(
                Membership.user_id == invitation.invited_by
            )
        )
        return email_templates.render(
            "invitation",
            workspace=tenant.name,
            url=f"{base}/invitations",
            preferences_url=prefs_url,
            actor=inviter,
        )
    notification = await session.get(Notification, delivery.notification_id)
    if notification is None:
        return None
    active = await session.scalar(
        select(Membership.id).where(
            Membership.user_id == notification.recipient_user_id, Membership.status == "active"
        )
    )
    case = await session.get(ContinuityCase, notification.case_id) if notification.case_id else None
    if active is None or case is None:
        return None  # access removed since: never email what they can no longer see
    task = await session.get(CaseTask, notification.task_id) if notification.task_id else None
    actor = (
        await session.scalar(
            select(func.coalesce(Membership.display_name, Membership.email)).where(
                Membership.user_id == notification.actor_user_id
            )
        )
        if notification.actor_user_id
        else None
    )
    return email_templates.render(
        notification.kind,
        workspace=tenant.name,
        url=f"{base}/w/{tenant.id}/cases/{case.id}",
        preferences_url=prefs_url,
        actor=actor,
        case_title=case.title,
        task_title=task.title if task else None,
        detail=notification.detail,
    )


async def _send(session: AsyncSession, event: OutboxEvent, ctx: outbox.JobContext) -> None:
    delivery = await session.get(
        EmailDelivery, uuid.UUID(event.payload["delivery_id"]), with_for_update=True
    )
    if delivery is None or delivery.status != "pending":
        return  # sent, failed or skipped already: never send twice
    delivery.attempts, delivery.updated_at = event.attempts + 1, func.now()
    provider = provider_for(ctx.settings, ctx.http) if ctx.settings and ctx.http else None
    if provider is None or ctx.settings is None:
        delivery.status, delivery.last_error = "skipped", "email_not_configured"
        return
    rendered = await _render(session, delivery, ctx.settings)
    if rendered is None:
        delivery.status, delivery.last_error = "skipped", "no_longer_relevant"
        return
    try:
        message_id = await provider.send(
            EmailMessage(
                to=delivery.recipient_email,
                subject=rendered.subject,
                html=rendered.html,
                text=rendered.text,
                # Stable across automatic retries; a manual retry starts a new generation.
                idempotency_key=f"relay-{delivery.id}-g{event.payload.get('generation', 0)}",
            )
        )
    except EmailSendError as exc:
        if exc.transient and delivery.attempts < MAX_ATTEMPTS:
            raise  # rolls back; the job retries with backoff and the same idempotency key
        delivery.status, delivery.last_error = "failed", exc.code
        return
    delivery.status, delivery.provider_message_id = "sent", message_id
    delivery.sent_at, delivery.last_error = func.now(), None


outbox.register(EVENT, _send)


# ---------------------------------------------------------------- preferences and admin


async def get_preferences(access: WorkspaceAccess) -> list[PreferenceView]:
    authorize(access, Permission.CASE_READ)
    stored = dict(
        (
            await access.session.execute(
                select(EmailPreference.category, EmailPreference.enabled).where(
                    visible(access, Permission.CASE_READ, EmailPreference.tenant_id),
                    EmailPreference.user_id == access.user_id,
                )
            )
        ).all()
    )
    return [
        PreferenceView(category=c, label=CATEGORY_LABEL[c], enabled=stored.get(c, True))
        for c in EMAIL_CATEGORIES
    ]


async def update_preferences(
    access: WorkspaceAccess, data: PreferencesUpdate
) -> list[PreferenceView]:
    authorize(access, Permission.CASE_READ)
    for category, enabled in data.preferences.items():
        stmt = insert(EmailPreference).values(
            tenant_id=access.tenant_id, user_id=access.user_id, category=category, enabled=enabled
        )
        await access.session.execute(
            stmt.on_conflict_do_update(
                index_elements=["tenant_id", "user_id", "category"],
                set_={"enabled": enabled, "updated_at": func.now()},
            )
        )
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="notification.email_preferences_updated",
        actor_user_id=access.user_id,
        target_type="user",
        target_id=access.user_id,
        details={c: v for c, v in data.preferences.items()},
    )
    return await get_preferences(access)


def _delivery_view(d: EmailDelivery) -> DeliveryView:
    local, _, domain = d.recipient_email.partition("@")
    return DeliveryView(
        id=d.id,
        kind=d.kind,
        recipient=f"{local[:2]}…@{domain}",  # enough to recognise, not to harvest
        status=d.status,
        attempts=d.attempts,
        last_error=d.last_error,
        created_at=d.created_at,
        sent_at=d.sent_at,
    )


async def email_status(access: WorkspaceAccess, settings: Settings) -> EmailStatusView:
    authorize(access, Permission.MEMBER_MANAGE)
    since = datetime.now(UTC) - timedelta(hours=24)
    mine = visible(access, Permission.MEMBER_MANAGE, EmailDelivery.tenant_id)
    sent, failed, pending = (
        await access.session.execute(
            select(
                func.count().filter(
                    EmailDelivery.status == "sent", EmailDelivery.created_at >= since
                ),
                func.count().filter(
                    EmailDelivery.status == "failed", EmailDelivery.created_at >= since
                ),
                func.count().filter(EmailDelivery.status == "pending"),
            ).where(mine)
        )
    ).one()
    failures = await access.session.scalars(
        select(EmailDelivery)
        .where(mine, EmailDelivery.status == "failed")
        .order_by(EmailDelivery.updated_at.desc())
        .limit(20)
    )
    configured = email_configured(settings)
    return EmailStatusView(
        configured=configured,
        provider=("SMTP" if settings.smtp_host else "Resend") if configured else None,
        sender=settings.email_from if configured else None,
        healthy=configured and failed == 0,
        sent_24h=sent,
        failed_24h=failed,
        pending=pending,
        recent_failures=[_delivery_view(d) for d in failures],
    )


async def retry_delivery(
    access: WorkspaceAccess, delivery_id: uuid.UUID, jobs: procrastinate.App
) -> DeliveryView:
    authorize(access, Permission.MEMBER_MANAGE)
    delivery = await access.session.scalar(
        select(EmailDelivery)
        .where(
            EmailDelivery.id == delivery_id,
            visible(access, Permission.MEMBER_MANAGE, EmailDelivery.tenant_id),
        )
        .with_for_update()
    )
    if delivery is None:
        raise ApiError(404, "delivery_not_found", "Email not found.")
    if delivery.status != "failed":
        raise ApiError(409, "not_failed", "Only failed emails can be retried.")
    delivery.status, delivery.last_error, delivery.updated_at = "pending", None, func.now()
    await outbox.emit(
        access.session,
        jobs,
        tenant_id=access.tenant_id,
        event_type=EVENT,
        payload={"delivery_id": str(delivery.id), "generation": int(datetime.now(UTC).timestamp())},
    )
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="notification.email_retried",
        actor_user_id=access.user_id,
        target_type="email_delivery",
        target_id=delivery.id,
    )
    return _delivery_view(delivery)


class TestEmailView(BaseModel):
    sent: bool
    to: str
    error: str | None


async def send_test_email(
    access: WorkspaceAccess, settings: Settings, http: httpx.AsyncClient
) -> TestEmailView:
    """Send one email to the caller's own address through the configured provider.

    Only ever to the requesting admin (never an arbitrary address), rate limited, audited.
    The result is reported directly; nothing is queued or retried.
    """
    authorize(access, Permission.MEMBER_MANAGE)
    provider = provider_for(settings, http)
    if provider is None:
        raise ApiError(409, "email_not_configured", "Email isn't configured on this server.")
    to = await access.session.scalar(
        select(Membership.email).where(
            Membership.user_id == access.user_id,
            visible(access, Permission.MEMBER_MANAGE, Membership.tenant_id),
        )
    )
    if not to:
        raise ApiError(
            422, "email_unknown", "Relay doesn't know your email yet. Sign out and in again."
        )
    error: str | None = None
    try:
        await provider.send(
            EmailMessage(
                to=to,
                subject="Relay test email",
                html="<p>Email from Relay works. Notifications will be delivered here.</p>",
                text="Email from Relay works. Notifications will be delivered here.",
                idempotency_key=f"relay-test-{uuid.uuid7()}",
            )
        )
    except EmailSendError as exc:
        error = exc.code
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="email.test_sent" if error is None else "email.test_failed",
        actor_user_id=access.user_id,
        target_type="membership",
        target_id=access.membership_id,
        details={"error": error},
    )
    return TestEmailView(sent=error is None, to=to, error=error)
