"""The small contract every connector (GitHub, Linear, Notion) shares: health, pause and
resume, and a recorded history of sync runs.

Connect, disconnect, test (a sync) and permissions stay in each provider's service; this
module only standardises what an admin sees and the guarantees around syncing:

- a paused connector keeps credentials and data but runs no syncs (a run is recorded as
  skipped, so the history explains the gap);
- every sync records its outcome and duration;
- health is derived from the connection and its recent runs, never stored, so it can't
  drift from reality.
"""

import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.governance.models import ConnectorRun
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.github.models import GitHubInstallation
from relay.integrations.linear.models import LinearConnection
from relay.integrations.notion.models import NotionConnection
from relay.jobs import outbox
from relay.jobs.models import OutboxEvent
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.errors import ApiError

Provider = Literal["github", "linear", "notion"]
Health = Literal[
    "healthy",
    "stale",
    "partial",
    "attention_required",
    "rate_limited",
    "permission_changed",
    "paused",
    "revoked",
    "failed",
]
STALE_AFTER = timedelta(hours=24)
MODELS: dict[str, Any] = {
    "github": GitHubInstallation,
    "linear": LinearConnection,
    "notion": NotionConnection,
}
_NAME = {
    "github": lambda c: c.account_login,
    "linear": lambda c: c.organization_name,
    "notion": lambda c: c.workspace_name,
}
Handler = Callable[[AsyncSession, OutboxEvent, outbox.JobContext], Awaitable[None]]


class RunView(BaseModel):
    status: str
    error: str | None
    duration_ms: int
    finished_at: datetime


class ConnectorView(BaseModel):
    provider: Provider
    ref: uuid.UUID
    name: str
    health: Health
    # What the admin can do about it, in plain words.
    advice: str
    last_synced_at: datetime | None
    last_success_at: datetime | None
    failure_rate: float | None  # over the recent runs; None without history
    runs: list[RunView]


def recorded(provider: Provider, ref_key: str, handler: Handler) -> Handler:
    """Wrap a sync handler: skip while paused; record the run's outcome and duration."""
    model = MODELS[provider]

    async def run(session: AsyncSession, event: OutboxEvent, ctx: outbox.JobContext) -> None:
        ref = uuid.UUID(str(event.payload[ref_key]))
        connection = await session.get(model, ref)
        if connection is None:
            return
        if connection.paused:
            session.add(
                ConnectorRun(
                    tenant_id=event.tenant_id,
                    provider=provider,
                    connection_ref=ref,
                    status="skipped",
                    error="Paused by an admin",
                )
            )
            return
        started = time.monotonic()
        await handler(session, event, ctx)
        # Flush first: refresh() would otherwise discard the handler's unflushed changes.
        await session.flush()
        await session.refresh(connection)
        outcome = connection.last_sync_status
        if outcome not in ("ok", "partial", "error"):
            return  # the handler re-queued itself (e.g. after a token refresh): no outcome yet
        session.add(
            ConnectorRun(
                tenant_id=event.tenant_id,
                provider=provider,
                connection_ref=ref,
                status=outcome,
                error=connection.last_sync_error if outcome != "ok" else None,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )

    return run


def _health(c: Any, runs: list[ConnectorRun], now: datetime) -> tuple[Health, str]:
    error = (c.last_sync_error or "").lower()
    if c.status in ("revoked", "suspended", "uninstalled"):
        return "revoked", "Access was revoked. Reconnect to resume syncing."
    if c.paused:
        return "paused", "Paused by an admin. Resume to sync again."
    if c.last_sync_status == "error":
        if "429" in error or "rate" in error:
            return "rate_limited", "The provider is rate-limiting Relay; it retries automatically."
        if any(w in error for w in ("permission", "forbidden", "403", "access", "revoked")):
            return (
                "permission_changed",
                "Relay lost access to some data. Check the app's permissions, then sync.",
            )
        recent = [r for r in runs[:3] if r.status != "skipped"]
        if len(recent) >= 3 and all(r.status == "error" for r in recent):
            return "failed", f"The last syncs failed: {c.last_sync_error}"
        return "attention_required", c.last_sync_error or "The last sync failed. Retry it."
    expires = getattr(c, "token_expires_at", None)
    if (
        expires is not None
        and expires <= now
        and getattr(c, "refresh_token_ciphertext", None) is None
    ):
        return "attention_required", "The credentials expired. Reconnect."
    if c.last_sync_status == "partial":
        return "partial", "Some records couldn't be read; the rest is current."
    if c.last_synced_at is None or c.last_synced_at < now - STALE_AFTER:
        return "stale", "Not synced in the last day. Sync now."
    return "healthy", "Up to date."


async def health(access: WorkspaceAccess) -> list[ConnectorView]:
    authorize(access, Permission.INTEGRATION_MANAGE)
    now = datetime.now(UTC)
    views = []
    for provider, model in MODELS.items():
        for c in await access.session.scalars(
            select(model).where(
                visible(access, Permission.INTEGRATION_MANAGE, model.tenant_id),
                model.status != "disconnected",
            )
        ):
            runs = list(
                await access.session.scalars(
                    select(ConnectorRun)
                    .where(ConnectorRun.connection_ref == c.id)
                    .order_by(ConnectorRun.finished_at.desc())
                    .limit(20)
                )
            )
            counted = [r for r in runs if r.status != "skipped"]
            state, advice = _health(c, runs, now)
            views.append(
                ConnectorView(
                    provider=provider,
                    ref=c.id,
                    name=_NAME[provider](c),
                    health=state,
                    advice=advice,
                    last_synced_at=c.last_synced_at,
                    last_success_at=next((r.finished_at for r in runs if r.status == "ok"), None),
                    failure_rate=round(
                        sum(1 for r in counted if r.status == "error") / len(counted), 2
                    )
                    if counted
                    else None,
                    runs=[RunView.model_validate(r, from_attributes=True) for r in runs[:10]],
                )
            )
    return views


async def set_paused(
    access: WorkspaceAccess, provider: Provider, ref: uuid.UUID, paused: bool
) -> list[ConnectorView]:
    authorize(access, Permission.INTEGRATION_MANAGE)
    model = MODELS[provider]
    connection = await access.session.scalar(
        select(model)
        .where(model.id == ref, visible(access, Permission.INTEGRATION_MANAGE, model.tenant_id))
        .with_for_update()
    )
    if connection is None:
        raise ApiError(404, "connection_not_found", "Connection not found.")
    connection.paused, connection.paused_at = paused, func.now() if paused else None
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=f"integration.{provider}_{'paused' if paused else 'resumed'}",
        actor_user_id=access.user_id,
        target_type=f"{provider}_connection",
        target_id=connection.id,
        details={},
    )
    await access.session.flush()
    return await health(access)
