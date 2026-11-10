"""Notion integration (read-only): connect, discover, map, import into Knowledge.

Notion stays the editor. Relay discovers the pages and databases a person shared with
the integration; an admin maps each one to a responsibility and a visibility. Only
mapped sources are imported (fail closed): each page becomes a knowledge item with
origin 'notion' that keeps the Notion URL, last-edited time and a content revision.

Sync is idempotent and cheap: a page whose last-edited time hasn't moved is not fetched,
and a page whose text hash is unchanged is not rewritten. Changed content needs a fresh
human review (imported text never passes as reviewed knowledge). Pages deleted, archived
or unshared in Notion, and sources an admin unmaps, are withdrawn, never deleted.
"""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import procrastinate
from pydantic import BaseModel, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.audit import service as audit
from relay.catalog import service as catalog
from relay.catalog.models import KnowledgeItem, Responsibility
from relay.identity.tokens import VerifiedIdentity
from relay.identity.workspace_access import WorkspaceAccess, open_workspace_access
from relay.integrations import connectors
from relay.integrations.notion.client import (
    NotionClient,
    NotionError,
    is_database_row,
    is_gone,
    parse_when,
    title_of,
)
from relay.integrations.notion.models import (
    NotionConnection,
    NotionConnectState,
    NotionPage,
    NotionSource,
)
from relay.jobs import outbox
from relay.jobs.models import OutboxEvent
from relay.policy.permissions import Permission, authorize, visible
from relay.shared import oauth
from relay.shared import secrets as secret_box
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

SYNC_EVENT = "notion.sync_requested"
STATE_TTL = timedelta(minutes=15)
RECONCILE_EVERY = timedelta(hours=6)
BODY_LIMIT = 19000
TRUNCATED = "\n\n[Truncated in Relay. Open the page in Notion for the rest.]"


class ConnectView(BaseModel):
    authorize_url: str


class CompleteConnectIn(StrictInput):
    state: str
    code: str


class ConnectionView(BaseModel):
    id: uuid.UUID
    workspace_name: str
    status: str
    last_synced_at: datetime | None
    last_sync_status: str
    last_sync_error: str | None
    next_reconcile_at: datetime | None


class SourceView(BaseModel):
    id: uuid.UUID
    kind: str
    title: str
    url: str
    last_edited_at: datetime | None
    removed: bool
    responsibility_id: uuid.UUID | None
    responsibility_name: str | None
    visibility: str | None
    imported_pages: int
    withdrawn_pages: int
    last_imported_at: datetime | None


class NotionIntegrationView(BaseModel):
    configured: bool
    connections: list[ConnectionView]
    sources: list[SourceView]


class SourceMappingIn(StrictInput):
    """Both set to import; both null to stop importing (and withdraw what was imported)."""

    responsibility_id: uuid.UUID | None
    visibility: Literal["workspace", "managers"] | None

    @model_validator(mode="after")
    def _complete(self) -> SourceMappingIn:
        if (self.responsibility_id is None) != (self.visibility is None):
            raise ValueError("Choose both a responsibility and a visibility, or neither.")
        return self


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _mine(access: WorkspaceAccess, tenant_column: Any) -> Any:
    return visible(access, Permission.INTEGRATION_MANAGE, tenant_column)


def _record(
    access: WorkspaceAccess, action: str, target_id: uuid.UUID, **details: str | None
) -> None:
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=action,
        actor_user_id=access.user_id,
        target_type="notion_connection",
        target_id=target_id,
        details=dict(details),
    )


async def _queue(
    session: AsyncSession, jobs: procrastinate.App, connection: NotionConnection
) -> None:
    connection.last_sync_status = "queued"
    await outbox.emit(
        session,
        jobs,
        tenant_id=connection.tenant_id,
        event_type=SYNC_EVENT,
        payload={"connection_ref": str(connection.id)},
    )


# ---------------------------------------------------------------- connect


async def start_connect(access: WorkspaceAccess, notion: NotionClient) -> ConnectView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    if not notion.configured:
        raise ApiError(503, "notion_not_configured", "Notion is not configured on this server.")
    token = f"{access.tenant_id}.{secrets.token_urlsafe(32)}"
    access.session.add(
        NotionConnectState(
            tenant_id=access.tenant_id,
            state_hash=_hash(token),
            user_id=access.user_id,
            expires_at=_now() + STATE_TTL,
        )
    )
    return ConnectView(authorize_url=notion.authorize_url(token))


async def complete_connect(
    factory: async_sessionmaker[AsyncSession],
    identity: VerifiedIdentity,
    notion: NotionClient,
    jobs: procrastinate.App,
    data: CompleteConnectIn,
) -> uuid.UUID:
    try:
        workspace_id = uuid.UUID(data.state.split(".", 1)[0])
    except ValueError as exc:
        raise ApiError(400, "invalid_state", "This Notion connection link is not valid.") from exc
    async with open_workspace_access(factory, identity, workspace_id) as access:
        authorize(access, Permission.INTEGRATION_MANAGE)
        state = await access.session.scalar(
            select(NotionConnectState)
            .where(
                NotionConnectState.state_hash == _hash(data.state),
                NotionConnectState.user_id == access.user_id,
                NotionConnectState.used_at.is_(None),
                NotionConnectState.expires_at > func.now(),
            )
            .with_for_update()
        )
        if state is None:
            raise ApiError(400, "invalid_state", "This Notion connection link expired or was used.")
        state.used_at = func.now()
        try:
            grant = await notion.exchange_code(data.code)
        except NotionError as exc:
            raise ApiError(403, "notion_not_authorized", str(exc)) from exc
        connection = await access.session.scalar(
            select(NotionConnection).where(NotionConnection.workspace_id == grant.workspace_id)
        )
        if connection is None:
            connection = NotionConnection(
                id=uuid.uuid7(),
                tenant_id=access.tenant_id,
                workspace_id=grant.workspace_id,
                workspace_name=grant.workspace_name,
                connected_by=access.user_id,
            )
            access.session.add(connection)
        connection.workspace_name = grant.workspace_name
        oauth.store(notion.settings, connection, grant.token)
        connection.status, connection.last_sync_error = "active", None
        await access.session.flush()
        await _queue(access.session, jobs, connection)
        _record(access, "integration.notion_connected", connection.id)
    return workspace_id


async def _connection(access: WorkspaceAccess, ref: uuid.UUID) -> NotionConnection:
    connection = await access.session.scalar(
        select(NotionConnection)
        .where(NotionConnection.id == ref, _mine(access, NotionConnection.tenant_id))
        .with_for_update()
    )
    if connection is None:
        raise ApiError(404, "connection_not_found", "Notion connection not found.")
    return connection


async def disconnect(access: WorkspaceAccess, ref: uuid.UUID) -> None:
    """Forget the token. Imported knowledge stays as a snapshot and stops updating."""
    authorize(access, Permission.INTEGRATION_MANAGE)
    connection = await _connection(access, ref)
    connection.status = "disconnected"
    oauth.forget(connection)
    connection.next_reconcile_at = None
    _record(access, "integration.notion_disconnected", connection.id)


async def request_sync(access: WorkspaceAccess, ref: uuid.UUID, jobs: procrastinate.App) -> None:
    authorize(access, Permission.INTEGRATION_MANAGE)
    connection = await _connection(access, ref)
    if connection.status != "active" or connection.token_ciphertext is None:
        raise ApiError(409, "reconnect_required", "Reconnect Notion to sync.")
    await _queue(access.session, jobs, connection)
    _record(access, "integration.notion_sync_requested", connection.id)


# ---------------------------------------------------------------- mapping


async def _withdraw(session: AsyncSession, pages: list[NotionPage]) -> int:
    items = {
        i.id: i
        for i in await session.scalars(
            select(KnowledgeItem).where(KnowledgeItem.id.in_([p.knowledge_item_id for p in pages]))
        )
    }
    count = 0
    for page in pages:
        if page.status == "active":
            page.status, count = "withdrawn", count + 1
        item = items.get(page.knowledge_item_id)
        if item is not None and item.status == "active":
            item.status, item.updated_at = "withdrawn", func.now()
    return count


async def map_source(
    access: WorkspaceAccess, source_id: uuid.UUID, data: SourceMappingIn, jobs: procrastinate.App
) -> None:
    authorize(access, Permission.INTEGRATION_MANAGE)
    source = await access.session.scalar(
        select(NotionSource)
        .where(NotionSource.id == source_id, _mine(access, NotionSource.tenant_id))
        .with_for_update()
    )
    if source is None:
        raise ApiError(404, "source_not_found", "Notion page or database not found.")
    if data.responsibility_id is not None:
        await catalog.require_active_responsibility(access, data.responsibility_id)
    source.responsibility_id, source.visibility = data.responsibility_id, data.visibility
    source.mapped_by, source.mapped_at = access.user_id, _now()
    pages = list(
        await access.session.scalars(select(NotionPage).where(NotionPage.source_ref == source.id))
    )
    if data.responsibility_id is None:
        await _withdraw(access.session, pages)
    elif pages:  # re-home and re-scope what was already imported, immediately
        for item in await access.session.scalars(
            select(KnowledgeItem).where(KnowledgeItem.id.in_([p.knowledge_item_id for p in pages]))
        ):
            item.responsibility_id = data.responsibility_id
            item.visibility = str(data.visibility)
            item.updated_at = func.now()
    connection = await access.session.get(NotionConnection, source.connection_ref)
    if connection is not None and connection.status == "active" and data.responsibility_id:
        await _queue(access.session, jobs, connection)
    _record(
        access,
        "integration.notion_source_mapped"
        if data.responsibility_id
        else "integration.notion_source_unmapped",
        source.connection_ref,
        source_id=str(source.id),
        responsibility_id=str(data.responsibility_id) if data.responsibility_id else None,
        visibility=data.visibility,
    )


class PreviewPage(BaseModel):
    title: str
    url: str
    last_edited_at: datetime | None
    already_imported: bool


class SourcePreviewView(BaseModel):
    source_id: uuid.UUID
    kind: str
    title: str
    pages: list[PreviewPage]
    more: bool


async def preview_source(
    access: WorkspaceAccess, source_id: uuid.UUID, notion: NotionClient
) -> SourcePreviewView:
    """What mapping this source would import, read live from Notion (titles only)."""
    authorize(access, Permission.INTEGRATION_MANAGE)
    source = await access.session.scalar(
        select(NotionSource).where(
            NotionSource.id == source_id, _mine(access, NotionSource.tenant_id)
        )
    )
    if source is None:
        raise ApiError(404, "source_not_found", "Notion page or database not found.")
    connection = await access.session.get(NotionConnection, source.connection_ref)
    if connection is None or connection.status != "active" or connection.token_ciphertext is None:
        raise ApiError(409, "reconnect_required", "Reconnect Notion to preview.")
    imported = set(
        await access.session.scalars(
            select(NotionPage.notion_id).where(
                _mine(access, NotionPage.tenant_id), NotionPage.status == "active"
            )
        )
    )
    limit = 20
    rows: list[dict[str, Any]]
    try:
        token = secret_box.decrypt(notion.settings, connection.token_ciphertext)
        if source.kind == "page":
            rows = [
                {
                    "id": source.notion_id,
                    "url": source.url,
                    "properties": {},
                    "_title": source.title,
                    "last_edited_time": source.last_edited_at.isoformat()
                    if source.last_edited_at
                    else None,
                }
            ]
        else:
            rows = await notion.database_pages(token, source.notion_id, limit + 1)
    except NotionError as exc:
        if exc.status == 404:
            raise ApiError(
                410, "source_gone", "This source is no longer shared with Relay."
            ) from exc
        raise ApiError(502, "notion_unavailable", "Notion didn't answer. Try again.") from exc
    except secret_box.SecretBoxUnavailableError as exc:
        raise ApiError(409, "reconnect_required", "Reconnect Notion to preview.") from exc
    live = [r for r in rows if not is_gone(r)]
    return SourcePreviewView(
        source_id=source.id,
        kind=source.kind,
        title=source.title,
        pages=[
            PreviewPage(
                title=str(r.get("_title") or title_of(r))[:200],
                url=str(r["url"]),
                last_edited_at=parse_when(r.get("last_edited_time")),
                already_imported=str(r["id"]) in imported,
            )
            for r in live[:limit]
        ],
        more=len(live) > limit,
    )


# ---------------------------------------------------------------- sync


async def _refresh(connection: Any, client: NotionClient, settings: Any) -> str | None:
    """A new access token, or None without a refresh token or when Notion rejects it."""
    if connection.refresh_token_ciphertext is None:
        return None
    try:
        grant = await client.refresh(
            secret_box.decrypt(settings, connection.refresh_token_ciphertext)
        )
    except NotionError as exc:
        if exc.transient:
            raise
        return None
    oauth.store(settings, connection, grant)
    return grant.access_token


def _body(text: str) -> str | None:
    if not text:
        return None
    return text if len(text) <= BODY_LIMIT else text[:BODY_LIMIT] + TRUNCATED


async def _import_page(
    session: AsyncSession,
    notion: NotionClient,
    token: str,
    source: NotionSource,
    obj: dict[str, Any],
    stats: dict[str, int],
) -> bool:
    """Import or refresh one page. Returns False when the page is gone."""
    notion_id, edited = str(obj["id"]), parse_when(obj.get("last_edited_time")) or _now()
    page = await session.scalar(select(NotionPage).where(NotionPage.notion_id == notion_id))
    if page is not None and page.source_ref != source.id:
        page.source_ref = source.id  # moved between mapped sources
    if page is not None and page.status == "active" and page.last_edited_at >= edited:
        return True  # unchanged since the last import: not even fetched
    try:
        text = await notion.page_text(token, notion_id)
    except NotionError as exc:
        if exc.status == 404:
            return False
        raise
    title = title_of(obj)[:200]
    revision = _hash(f"{title}\n{obj.get('url')}\n{text}")
    assert source.responsibility_id
    assert source.visibility
    assert source.mapped_by
    if page is None:
        item = KnowledgeItem(
            id=uuid.uuid7(),
            tenant_id=source.tenant_id,
            responsibility_id=source.responsibility_id,
            kind="document",
            title=title,
            body=_body(text),
            url=str(obj["url"]),
            visibility=source.visibility,
            origin="notion",
            author_user_id=source.mapped_by,
        )
        session.add(item)
        await session.flush()
        session.add(
            NotionPage(
                tenant_id=source.tenant_id,
                source_ref=source.id,
                notion_id=notion_id,
                title=title,
                url=str(obj["url"]),
                last_edited_at=edited,
                revision=revision,
                knowledge_item_id=item.id,
            )
        )
        stats["imported"] += 1
        return True
    existing = await session.get(KnowledgeItem, page.knowledge_item_id)
    assert existing is not None
    item = existing
    page.last_edited_at, page.synced_at = edited, func.now()
    if page.status == "withdrawn":
        page.status = "active"
        if item.status == "withdrawn":
            item.status, item.updated_at = "active", func.now()
        stats["restored"] += 1
    if page.revision == revision:
        return True  # edited in Notion but the imported text is identical
    page.revision, page.title, page.url = revision, title, str(obj["url"])
    item.title, item.body, item.url = title, _body(text), str(obj["url"])
    item.updated_at = func.now()
    item.last_reviewed_at = item.last_reviewed_by = None  # changed content needs review
    stats["updated"] += 1
    return True


async def handle_sync(session: AsyncSession, event: OutboxEvent, ctx: outbox.JobContext) -> None:
    """Idempotent: converges on what is currently shared and mapped in Notion."""
    if ctx.http is None or ctx.settings is None:
        raise RuntimeError("Notion sync needs an HTTP client and settings")
    connection = await session.get(
        NotionConnection, uuid.UUID(event.payload["connection_ref"]), with_for_update=True
    )
    if connection is None or connection.status != "active" or connection.token_ciphertext is None:
        return
    notion, limit = NotionClient(ctx.settings, ctx.http), ctx.settings.notion_page_limit
    try:
        token = secret_box.decrypt(ctx.settings, connection.token_ciphertext)
    except secret_box.SecretBoxUnavailableError:
        connection.last_sync_status = "error"
        connection.last_sync_error = (
            "Stored Notion credentials can't be read (encryption key missing or changed). "
            "Reconnect Notion."
        )
        return
    if oauth.expiring(connection):
        token = await _refresh(connection, notion, ctx.settings) or token
    stats = {"imported": 0, "updated": 0, "restored": 0, "withdrawn": 0}
    truncated = False
    try:
        shared = await notion.search(token, limit)
        truncated = len(shared) >= limit
        found = {str(o["id"]): o for o in shared if not is_database_row(o)}
        sources = {
            s.notion_id: s
            for s in await session.scalars(
                select(NotionSource).where(NotionSource.connection_ref == connection.id)
            )
        }
        for notion_id, obj in found.items():
            source = sources.get(notion_id)
            if source is None:
                source = NotionSource(
                    id=uuid.uuid7(),
                    tenant_id=connection.tenant_id,
                    connection_ref=connection.id,
                    notion_id=notion_id,
                    kind="database" if obj.get("object") == "database" else "page",
                    title="",
                    url="",
                )
                session.add(source)
                sources[notion_id] = source
            source.title, source.url = title_of(obj)[:300], str(obj["url"])
            source.last_edited_at = parse_when(obj.get("last_edited_time"))
            source.removed = is_gone(obj)
        for notion_id, source in sources.items():
            if notion_id not in found:
                source.removed = True  # unshared or deleted in Notion
        await session.flush()

        budget = limit
        for source in sources.values():
            pages = {
                p.notion_id: p
                for p in await session.scalars(
                    select(NotionPage).where(NotionPage.source_ref == source.id)
                )
            }
            seen: set[str] = set()
            if source.responsibility_id is not None and not source.removed:
                if source.kind == "page":
                    candidates = [found[source.notion_id]]
                else:
                    try:
                        candidates = await notion.database_pages(token, source.notion_id, budget)
                    except NotionError as exc:
                        if exc.status != 404:
                            raise
                        source.removed, candidates = True, []
                for obj in candidates[:budget]:
                    if is_gone(obj):
                        continue
                    budget -= 1
                    if await _import_page(session, notion, token, source, obj, stats):
                        seen.add(str(obj["id"]))
                truncated = truncated or budget <= 0
            stats["withdrawn"] += await _withdraw(
                session, [p for nid, p in pages.items() if nid not in seen]
            )
    except NotionError as exc:
        if exc.transient:
            raise  # retried by the outbox job with backoff
        if (
            exc.status == 401
            and ctx.jobs is not None
            and not event.payload.get("after_refresh")
            and await _refresh(connection, notion, ctx.settings)
        ):
            # Expired, not revoked: keep the new tokens (commit) and sync again with them.
            connection.last_sync_status, connection.last_sync_error = "queued", None
            await outbox.emit(
                session,
                ctx.jobs,
                tenant_id=connection.tenant_id,
                event_type=SYNC_EVENT,
                payload={"connection_ref": str(connection.id), "after_refresh": True},
            )
            return
        connection.last_sync_status = "error"
        if exc.status == 401:
            connection.status = "revoked"
            connection.last_sync_error = "Notion access was revoked. Reconnect Notion."
        else:
            connection.last_sync_error = "Notion rejected the sync. Retry, or reconnect."
        return
    connection.last_synced_at = func.now()
    connection.last_sync_status = "partial" if truncated else "ok"
    connection.last_sync_error = (
        f"Stopped after {limit} pages (RELAY_NOTION_PAGE_LIMIT). Share fewer pages with "
        "Relay, or raise the limit."
        if truncated
        else None
    )
    if any(stats.values()):
        audit.record(
            session,
            tenant_id=connection.tenant_id,
            action="integration.notion_synced",
            actor_user_id=None,
            target_type="notion_connection",
            target_id=connection.id,
            details={k: str(v) for k, v in stats.items()},
        )
    if ctx.jobs is not None and (
        connection.next_reconcile_at is None or connection.next_reconcile_at <= _now()
    ):
        connection.next_reconcile_at = _now() + RECONCILE_EVERY
        await outbox.emit(
            session,
            ctx.jobs,
            tenant_id=connection.tenant_id,
            event_type=SYNC_EVENT,
            payload={"connection_ref": str(connection.id), "reconcile": True},
            schedule_at=connection.next_reconcile_at,
        )


outbox.register(SYNC_EVENT, connectors.recorded("notion", "connection_ref", handle_sync))


# ---------------------------------------------------------------- reads


async def get_integration(access: WorkspaceAccess, *, configured: bool) -> NotionIntegrationView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    connections = list(
        await access.session.scalars(
            select(NotionConnection).where(
                _mine(access, NotionConnection.tenant_id), NotionConnection.status != "disconnected"
            )
        )
    )
    live = [c.id for c in connections]
    sources = list(
        await access.session.scalars(
            select(NotionSource)
            .where(_mine(access, NotionSource.tenant_id), NotionSource.connection_ref.in_(live))
            .order_by(NotionSource.removed, NotionSource.title)
        )
    )
    counts: dict[tuple[uuid.UUID, str], tuple[int, datetime | None]] = {
        (ref, status): (n, last)
        for ref, status, n, last in await access.session.execute(
            select(
                NotionPage.source_ref,
                NotionPage.status,
                func.count(),
                func.max(NotionPage.synced_at),
            )
            .where(_mine(access, NotionPage.tenant_id))
            .group_by(NotionPage.source_ref, NotionPage.status)
        )
    }
    names = dict(
        (
            await access.session.execute(
                select(Responsibility.id, Responsibility.name).where(
                    visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id)
                )
            )
        ).all()
    )
    return NotionIntegrationView(
        configured=configured,
        connections=[
            ConnectionView(
                id=c.id,
                workspace_name=c.workspace_name,
                status=c.status,
                last_synced_at=c.last_synced_at,
                last_sync_status=c.last_sync_status,
                last_sync_error=c.last_sync_error,
                next_reconcile_at=c.next_reconcile_at,
            )
            for c in connections
        ],
        sources=[
            SourceView(
                id=s.id,
                kind=s.kind,
                title=s.title,
                url=s.url,
                last_edited_at=s.last_edited_at,
                removed=s.removed,
                responsibility_id=s.responsibility_id,
                responsibility_name=names.get(s.responsibility_id) if s.responsibility_id else None,
                visibility=s.visibility,
                imported_pages=counts.get((s.id, "active"), (0, None))[0],
                withdrawn_pages=counts.get((s.id, "withdrawn"), (0, None))[0],
                last_imported_at=counts.get((s.id, "active"), (0, None))[1],
            )
            for s in sources
        ],
    )
