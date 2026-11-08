"""GitHub webhooks: verify, route, dedupe, then process asynchronously.

Receive (HTTP, no user session): the HMAC-SHA256 signature over the raw body must match
the App's webhook secret, or the request is rejected before anything is parsed. The
installation id routes the delivery to workspace(s) via `github_installation_route`; in
each, `webhook_delivery` (unique per X-GitHub-Delivery) makes redelivery a no-op, and an
outbox event carries a *normalised, minimal* payload (identifiers and PR/issue metadata;
never bodies, commit contents or raw payloads).

Process (worker, tenant context): PR/issue metadata is upserted with an updated-at guard
(older snapshots never win, so delayed or out-of-order events are harmless). Structural
events (installation, repositories, teams, membership, ownership-file pushes) queue a full
re-sync, because GitHub's current state, not the event, is the source of truth. Nothing
here changes Relay ownership: at most it refreshes evidence and suggestions.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import procrastinate
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.audit import service as audit
from relay.config import Settings
from relay.integrations.github import directory_sync
from relay.integrations.github.client import User, WorkItem, work_item
from relay.integrations.github.models import (
    GitHubInstallation,
    GitHubInstallationRoute,
    GitHubRepository,
    WebhookDelivery,
)
from relay.integrations.github.service import CATALOG_PATHS, CODEOWNERS_PATHS, SYNC_EVENT
from relay.jobs import outbox
from relay.jobs.models import OutboxEvent
from relay.shared.db import unit_of_work
from relay.shared.errors import ApiError

EVENT = "github.webhook"
MAX_BODY = 5 * 1024 * 1024  # GitHub caps payloads at 25 MB; we need only small ones
RESYNC_EVENTS = {
    "installation",
    "installation_repositories",
    "repository",
    "team",
    "membership",
    "member",
    "organization",
}
WORK_ITEM_EVENTS = {"pull_request": "pull_request", "issues": "issue"}


def verify_signature(secret: str, body: bytes, signature: str | None) -> bool:
    if not signature or not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def _touches_ownership_files(payload: dict[str, Any]) -> bool:
    watched = set(CODEOWNERS_PATHS) | set(CATALOG_PATHS)
    ref = str(payload.get("ref", ""))
    default = (payload.get("repository") or {}).get("default_branch")
    if default and ref != f"refs/heads/{default}":
        return False
    return any(
        path in watched
        for commit in payload.get("commits") or []
        for key in ("added", "modified", "removed")
        for path in commit.get(key) or []
    )


def normalise(event: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """The only data that leaves the request: ids, an action, PR/issue metadata."""
    installation_id = (payload.get("installation") or {}).get("id")
    if not installation_id:
        return None
    out: dict[str, Any] = {
        "event": event,
        "action": payload.get("action"),
        "installation_id": int(installation_id),
        "repository_id": (payload.get("repository") or {}).get("id"),
    }
    kind = WORK_ITEM_EVENTS.get(event)
    if kind:
        item = work_item(payload[event if kind == "pull_request" else "issue"], kind)
        out["item"] = {
            "kind": item.kind,
            "number": item.number,
            "github_id": item.github_id,
            "title": item.title,
            "state": item.state,
            "user": [item.author.github_id, item.author.login] if item.author else None,
            "assignees": [[u.github_id, u.login] for u in item.assignees],
            "reviewers": [[u.github_id, u.login] for u in item.reviewers],
            "labels": list(item.labels),
            "html_url": item.html_url,
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat(),
            "closed_at": item.closed_at.isoformat() if item.closed_at else None,
            "merged_at": item.merged_at.isoformat() if item.merged_at else None,
        }
    elif event == "push":
        if not _touches_ownership_files(payload):
            return None
    elif event not in RESYNC_EVENTS:
        return None
    return out


async def receive(
    factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    jobs: procrastinate.App,
    *,
    event: str,
    delivery_id: str,
    signature: str | None,
    body: bytes,
) -> int:
    """Returns how many workspaces queued the delivery (0 for ignored/duplicate)."""
    if settings.github_webhook_secret is None:
        raise ApiError(503, "webhooks_disabled", "GitHub webhooks are not configured.")
    if len(body) > MAX_BODY:
        raise ApiError(413, "payload_too_large", "Payload too large.")
    if not verify_signature(settings.github_webhook_secret.get_secret_value(), body, signature):
        raise ApiError(401, "bad_signature", "Invalid webhook signature.")
    if not delivery_id or len(delivery_id) > 100:
        raise ApiError(422, "missing_delivery", "Missing X-GitHub-Delivery.")
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise ApiError(422, "bad_payload", "Payload is not JSON.") from exc
    message = normalise(event, payload) if isinstance(payload, dict) else None
    if message is None:
        return 0
    # Routing lookup outside any tenant context (the route table's lookup policy).
    async with factory() as session:
        tenants = list(
            await session.scalars(
                select(GitHubInstallationRoute.tenant_id).where(
                    GitHubInstallationRoute.installation_id == message["installation_id"]
                )
            )
        )
    queued = 0
    for tenant_id in tenants:
        async with unit_of_work(factory, tenant_id) as session:
            fresh = await session.scalar(
                insert(WebhookDelivery)
                .values(
                    tenant_id=tenant_id,
                    delivery_id=delivery_id,
                    event=event,
                    action=message["action"],
                )
                .on_conflict_do_nothing(index_elements=["tenant_id", "delivery_id"])
                .returning(WebhookDelivery.id)
            )
            if fresh is None:
                continue  # redelivery: already queued once for this workspace
            await outbox.emit(session, jobs, tenant_id=tenant_id, event_type=EVENT, payload=message)
            queued += 1
    return queued


async def _queue_resync(
    session: AsyncSession, installation: GitHubInstallation, jobs: procrastinate.App | None
) -> None:
    if jobs is None or installation.last_sync_status == "queued":
        return  # a sync is already pending; it will see the latest state
    installation.last_sync_status = "queued"
    await outbox.emit(
        session,
        jobs,
        tenant_id=installation.tenant_id,
        event_type=SYNC_EVENT,
        payload={"installation_ref": str(installation.id)},
    )


async def handle_webhook(session: AsyncSession, event: OutboxEvent, ctx: outbox.JobContext) -> None:
    message = event.payload
    installation = await session.scalar(
        select(GitHubInstallation)
        .where(GitHubInstallation.installation_id == message["installation_id"])
        .with_for_update()
    )
    if installation is None or installation.status == "disconnected":
        return
    name, action = message["event"], message.get("action")
    if name == "installation" and action in ("deleted", "suspend"):
        installation.status, installation.last_sync_status = "revoked", "error"
        installation.last_sync_error = (
            "The GitHub App was uninstalled on GitHub. Reconnect GitHub."
            if action == "deleted"
            else "The GitHub App installation was suspended on GitHub. Unsuspend it to resume."
        )
        audit.record(
            session,
            tenant_id=event.tenant_id,
            action=f"integration.github_installation_{action}",
            actor_user_id=None,
            target_type="github_installation",
            target_id=installation.id,
        )
        return
    if name in WORK_ITEM_EVENTS:
        repo = await session.scalar(
            select(GitHubRepository).where(
                GitHubRepository.installation_ref == installation.id,
                GitHubRepository.github_repo_id == message["repository_id"],
                GitHubRepository.selected.is_(True),
            )
        )
        if repo is not None:
            await directory_sync.upsert_work_items(session, repo, [_item(message["item"])])
        return
    if name == "installation" and action in ("unsuspend", "new_permissions_accepted"):
        installation.status = "active"
    await _queue_resync(session, installation, ctx.jobs)


def _item(data: dict[str, Any]) -> WorkItem:
    def when(value: str | None) -> datetime | None:
        return datetime.fromisoformat(value) if value else None

    def users(values: list[list[Any]]) -> tuple[User, ...]:
        return tuple(User(int(i), str(login)) for i, login in values)

    return WorkItem(
        kind=data["kind"],
        number=data["number"],
        github_id=data["github_id"],
        title=data["title"],
        state=data["state"],
        author=User(int(data["user"][0]), data["user"][1]) if data["user"] else None,
        assignees=users(data["assignees"]),
        reviewers=users(data["reviewers"]),
        labels=tuple(data["labels"]),
        html_url=data["html_url"],
        created_at=when(data["created_at"]),  # type: ignore[arg-type]
        updated_at=when(data["updated_at"]),  # type: ignore[arg-type]
        closed_at=when(data["closed_at"]),
        merged_at=when(data["merged_at"]),
    )


outbox.register(EVENT, handle_webhook)


async def reconcile(
    factory: async_sessionmaker[AsyncSession],
    jobs: procrastinate.App,
    *,
    stale_after: timedelta = timedelta(hours=6),
) -> int:
    """Periodic safety net: re-sync installations not synced recently, so a missed or
    failed webhook can never leave Relay's view permanently out of date. A sync marked
    'queued' with no recent unprocessed sync event (e.g. its job exhausted retries) is
    re-queued."""
    async with factory() as session:  # routing lookup outside any tenant context
        tenants = set(await session.scalars(select(GitHubInstallationRoute.tenant_id)))
    now = datetime.now(UTC)
    queued = 0
    for tenant_id in sorted(tenants):
        async with unit_of_work(factory, tenant_id) as session:
            installations = await session.scalars(
                select(GitHubInstallation)
                .where(GitHubInstallation.status == "active")
                .with_for_update(skip_locked=True)
            )
            for installation in installations:
                last = installation.last_synced_at
                if last is not None and last > now - stale_after:
                    continue
                if installation.last_sync_status == "queued":
                    pending = await session.scalar(
                        select(OutboxEvent.id)
                        .where(
                            OutboxEvent.event_type == SYNC_EVENT,
                            OutboxEvent.processed_at.is_(None),
                            OutboxEvent.payload["installation_ref"].astext == str(installation.id),
                            OutboxEvent.created_at > now - 2 * stale_after,
                        )
                        .limit(1)
                    )
                    if pending is None:  # queued long ago and never processed: recover
                        installation.last_sync_status = "error"
                before = installation.last_sync_status
                await _queue_resync(session, installation, jobs)
                queued += before != "queued"
    return queued
