"""Linear integration (read-only): connect, sync, identity review, projects, signals.

Linear stays the work tracker. Relay reads teams, projects, people and issue metadata
to understand continuity: who works on what, which important work has no accountable
owner, and where declared ownership disagrees with observed activity. Nothing here
changes Relay ownership.

Sync runs through the outbox. Each successful sync schedules the next reconciliation
(6 hours later) as a delayed outbox event, so missed changes are always picked up
without any cross-workspace scan.
"""

import hashlib
import secrets
import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import procrastinate
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.audit import service as audit
from relay.catalog import service as catalog
from relay.catalog.models import OwnershipAssignment, Responsibility
from relay.directory.models import Person
from relay.identity.tokens import VerifiedIdentity
from relay.identity.workspace_access import WorkspaceAccess, open_workspace_access
from relay.integrations.linear.client import LinearClient, LinearError, parse_when
from relay.integrations.linear.models import (
    LinearConnection,
    LinearConnectState,
    LinearIdentity,
    LinearIssue,
    LinearProject,
    LinearTeam,
)
from relay.jobs import outbox
from relay.jobs.models import OutboxEvent
from relay.policy.permissions import Permission, authorize, visible
from relay.shared import oauth
from relay.shared import secrets as secret_box
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

SYNC_EVENT = "linear.sync_requested"
STATE_TTL = timedelta(minutes=15)
RECONCILE_EVERY = timedelta(hours=6)
ACTIVITY_DAYS = 90
ACTIVE_THRESHOLD = 3
IMPORTANT_PRIORITIES = (1, 2)  # Linear: 1 urgent, 2 high
_VERB = {"link": "linked", "unlink": "unlinked", "create": "created", "dismiss": "dismissed"}


class ConnectView(BaseModel):
    authorize_url: str


class CompleteConnectIn(StrictInput):
    state: str
    code: str


class ConnectionView(BaseModel):
    id: uuid.UUID
    organization_name: str
    url_key: str | None
    status: str
    last_synced_at: datetime | None
    last_sync_status: str
    last_sync_error: str | None
    next_reconcile_at: datetime | None


class ProjectView(BaseModel):
    id: uuid.UUID
    name: str
    state: str | None
    url: str
    lead: str | None
    open_issues: int
    recent_issues: int
    responsibility_id: uuid.UUID | None
    responsibility_name: str | None


class LinearIntegrationView(BaseModel):
    configured: bool
    connections: list[ConnectionView]
    teams: list[dict[str, Any]]
    projects: list[ProjectView]
    identities_to_review: int


class ProjectLinkIn(StrictInput):
    action: Literal["link", "create", "unlink"]
    responsibility_id: uuid.UUID | None = None


class LinearIdentityView(BaseModel):
    id: uuid.UUID
    name: str
    email: str | None
    active: bool
    link_status: str
    person: dict[str, Any] | None
    suggested_person: dict[str, Any] | None
    match_reason: str | None
    recent_issues: int


class IdentityDecisionIn(StrictInput):
    action: Literal["link", "unlink", "dismiss"]
    person_id: uuid.UUID | None = None


class SignalView(BaseModel):
    key: str
    kind: Literal["unowned_important", "active_uncovered", "owner_absent"]
    severity: Literal["high", "medium", "low"]
    title: str
    explanation: str
    project: str
    project_url: str
    responsibility_id: uuid.UUID | None
    evidence: list[dict[str, str]]


def _norm(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


def _mine(access: WorkspaceAccess, tenant_column: Any) -> Any:
    return visible(access, Permission.INTEGRATION_MANAGE, tenant_column)


def _issue_link(issue: LinearIssue) -> dict[str, str]:
    return {"label": f"{issue.identifier} {issue.title}", "url": issue.url}


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _record(
    access: WorkspaceAccess, action: str, target_id: uuid.UUID, **details: str | None
) -> None:
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=action,
        actor_user_id=access.user_id,
        target_type="linear_connection",
        target_id=target_id,
        details=dict(details),
    )


# ---------------------------------------------------------------- connect


async def start_connect(access: WorkspaceAccess, linear: LinearClient) -> ConnectView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    if not linear.configured:
        raise ApiError(503, "linear_not_configured", "Linear is not configured on this server.")
    token = f"{access.tenant_id}.{secrets.token_urlsafe(32)}"
    access.session.add(
        LinearConnectState(
            tenant_id=access.tenant_id,
            state_hash=_hash(token),
            user_id=access.user_id,
            expires_at=_now() + STATE_TTL,
        )
    )
    return ConnectView(authorize_url=linear.authorize_url(token))


async def complete_connect(
    factory: async_sessionmaker[AsyncSession],
    identity: VerifiedIdentity,
    linear: LinearClient,
    jobs: procrastinate.App,
    data: CompleteConnectIn,
) -> uuid.UUID:
    try:
        workspace_id = uuid.UUID(data.state.split(".", 1)[0])
    except ValueError as exc:
        raise ApiError(400, "invalid_state", "This Linear connection link is not valid.") from exc
    async with open_workspace_access(factory, identity, workspace_id) as access:
        authorize(access, Permission.INTEGRATION_MANAGE)
        state = await access.session.scalar(
            select(LinearConnectState)
            .where(
                LinearConnectState.state_hash == _hash(data.state),
                LinearConnectState.user_id == access.user_id,
                LinearConnectState.used_at.is_(None),
                LinearConnectState.expires_at > func.now(),
            )
            .with_for_update()
        )
        if state is None:
            raise ApiError(400, "invalid_state", "This Linear connection link expired or was used.")
        state.used_at = func.now()
        try:
            grant = await linear.exchange_code(data.code)
            org = await linear.organization(grant.access_token)
        except LinearError as exc:
            raise ApiError(403, "linear_not_authorized", str(exc)) from exc
        settings = linear.settings
        connection = await access.session.scalar(
            select(LinearConnection).where(LinearConnection.organization_id == org.id)
        )
        if connection is None:
            connection = LinearConnection(
                id=uuid.uuid7(),
                tenant_id=access.tenant_id,
                organization_id=org.id,
                organization_name=org.name,
                connected_by=access.user_id,
            )
            access.session.add(connection)
        connection.organization_name, connection.url_key = org.name, org.url_key
        oauth.store(settings, connection, grant)
        connection.status, connection.last_sync_status, connection.last_sync_error = (
            "active",
            "queued",
            None,
        )
        await access.session.flush()
        await outbox.emit(
            access.session,
            jobs,
            tenant_id=access.tenant_id,
            event_type=SYNC_EVENT,
            payload={"connection_ref": str(connection.id)},
        )
        _record(access, "integration.linear_connected", connection.id, organization=org.name)
    return workspace_id


async def _connection(access: WorkspaceAccess, ref: uuid.UUID) -> LinearConnection:
    connection = await access.session.scalar(
        select(LinearConnection)
        .where(
            LinearConnection.id == ref,
            visible(access, Permission.INTEGRATION_MANAGE, LinearConnection.tenant_id),
        )
        .with_for_update()
    )
    if connection is None:
        raise ApiError(404, "connection_not_found", "Linear connection not found.")
    return connection


async def disconnect(access: WorkspaceAccess, ref: uuid.UUID) -> None:
    authorize(access, Permission.INTEGRATION_MANAGE)
    connection = await _connection(access, ref)
    connection.status = "disconnected"
    oauth.forget(connection)  # forget the tokens
    connection.next_reconcile_at = None
    _record(access, "integration.linear_disconnected", connection.id)


async def request_sync(access: WorkspaceAccess, ref: uuid.UUID, jobs: procrastinate.App) -> None:
    authorize(access, Permission.INTEGRATION_MANAGE)
    connection = await _connection(access, ref)
    if connection.status != "active" or connection.token_ciphertext is None:
        raise ApiError(409, "reconnect_required", "Reconnect Linear to sync.")
    connection.last_sync_status = "queued"
    await outbox.emit(
        access.session,
        jobs,
        tenant_id=access.tenant_id,
        event_type=SYNC_EVENT,
        payload={"connection_ref": str(connection.id)},
    )
    _record(access, "integration.linear_sync_requested", connection.id)


# ---------------------------------------------------------------- sync


async def _refresh(connection: Any, client: LinearClient, settings: Any) -> str | None:
    """A new access token, or None without a refresh token or when Linear rejects it."""
    if connection.refresh_token_ciphertext is None:
        return None
    try:
        grant = await client.refresh(
            secret_box.decrypt(settings, connection.refresh_token_ciphertext)
        )
    except LinearError as exc:
        if exc.transient:
            raise
        return None
    oauth.store(settings, connection, grant)
    return grant.access_token


def _match(identity: LinearIdentity, people: list[Person]) -> None:
    """Suggest only; Linear emails are not proof of identity in Relay."""
    if identity.link_status in ("linked", "dismissed") or identity.decided_by is not None:
        return
    for found, reason in (
        (
            [p for p in people if identity.email and _norm(p.email) == _norm(identity.email)],
            "Linear email matches the person's email",
        ),
        ([p for p in people if _norm(p.display_name) == _norm(identity.name)], "Name matches"),
    ):
        if len(found) == 1:
            identity.link_status, identity.suggested_person_id = "suggested", found[0].id
            identity.match_reason = reason
            return
        if len(found) > 1:
            identity.link_status, identity.suggested_person_id = "unmatched", None
            identity.match_reason = "Several people match; choose one"
            return
    identity.link_status, identity.suggested_person_id, identity.match_reason = (
        "unmatched",
        None,
        None,
    )


async def handle_sync(session: AsyncSession, event: OutboxEvent, ctx: outbox.JobContext) -> None:
    """Idempotent: upserts by Linear id converge on the source's current state."""
    if ctx.http is None or ctx.settings is None:
        raise RuntimeError("Linear sync needs an HTTP client and settings")
    connection = await session.get(
        LinearConnection, uuid.UUID(event.payload["connection_ref"]), with_for_update=True
    )
    if connection is None or connection.status != "active" or connection.token_ciphertext is None:
        return
    linear = LinearClient(ctx.settings, ctx.http)
    try:
        token = secret_box.decrypt(ctx.settings, connection.token_ciphertext)
    except secret_box.SecretBoxUnavailableError:
        connection.last_sync_status = "error"
        connection.last_sync_error = (
            "Stored Linear credentials can't be read (encryption key missing or changed). "
            "Reconnect Linear."
        )
        return
    if oauth.expiring(connection):
        token = await _refresh(connection, linear, ctx.settings) or token
    since = _now() - timedelta(days=ACTIVITY_DAYS)
    try:
        teams, projects, users, issues = (
            await linear.teams(token),
            await linear.projects(token),
            await linear.users(token),
            await linear.issues(token, since),
        )
    except LinearError as exc:
        if exc.transient:
            raise  # retried by the outbox job with backoff
        if (
            exc.status == 401
            and ctx.jobs is not None
            and not event.payload.get("after_refresh")
            and await _refresh(connection, linear, ctx.settings)
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
            connection.last_sync_error = "Linear access was revoked. Reconnect Linear."
        else:
            connection.last_sync_error = "Linear rejected the sync query. Retry, or reconnect."
        return
    tenant = connection.tenant_id

    async def upsert(model: Any, rows: list[dict[str, Any]], update: list[str]) -> None:
        for row in rows:
            stmt = insert(model).values(tenant_id=tenant, **row)
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["tenant_id", "linear_id"],
                    set_={k: stmt.excluded[k] for k in update},
                )
            )

    await upsert(
        LinearTeam,
        [
            {
                "connection_ref": connection.id,
                "linear_id": t["id"],
                "key": t["key"],
                "name": t["name"],
                "removed": False,
            }
            for t in teams
        ],
        ["key", "name", "removed"],
    )
    await upsert(
        LinearProject,
        [
            {
                "connection_ref": connection.id,
                "linear_id": p["id"],
                "name": p["name"],
                "state": p.get("state"),
                "url": p["url"],
                "lead_linear_id": (p.get("lead") or {}).get("id"),
                "team_linear_ids": [t["id"] for t in (p.get("teams") or {}).get("nodes", [])],
                "removed": False,
                "updated_at": _now(),
            }
            for p in projects
        ],
        ["name", "state", "url", "lead_linear_id", "team_linear_ids", "removed", "updated_at"],
    )
    await upsert(
        LinearIdentity,
        [
            {
                "linear_id": u["id"],
                "name": u.get("displayName") or u["name"],
                "email": (u.get("email") or "").lower() or None,
                "active": bool(u.get("active", True)),
            }
            for u in users
        ],
        ["name", "email", "active"],
    )
    for issue in issues:  # metadata only, newer-wins guard against out-of-order syncs
        row = {
            "connection_ref": connection.id,
            "linear_id": issue["id"],
            "identifier": issue["identifier"],
            "title": str(issue.get("title") or "")[:300],
            "state_type": (issue.get("state") or {}).get("type") or "unknown",
            "state_name": (issue.get("state") or {}).get("name"),
            "priority": int(issue.get("priority") or 0),
            "assignee_linear_id": (issue.get("assignee") or {}).get("id"),
            "creator_linear_id": (issue.get("creator") or {}).get("id"),
            "team_linear_id": (issue.get("team") or {}).get("id"),
            "project_linear_id": (issue.get("project") or {}).get("id"),
            "parent_identifier": (issue.get("parent") or {}).get("identifier"),
            "labels": [lb["name"] for lb in (issue.get("labels") or {}).get("nodes", [])],
            "url": issue["url"],
            "li_created_at": parse_when(issue["createdAt"]),
            "li_updated_at": parse_when(issue["updatedAt"]),
            "completed_at": parse_when(issue.get("completedAt")),
            "canceled_at": parse_when(issue.get("canceledAt")),
        }
        stmt = insert(LinearIssue).values(tenant_id=tenant, **row)
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["tenant_id", "linear_id"],
                set_={k: stmt.excluded[k] for k in row if k != "connection_ref"},
                where=LinearIssue.li_updated_at <= stmt.excluded.li_updated_at,
            )
        )
    # Things deleted or no longer visible in Linear are marked removed, never deleted.
    seen_teams, seen_projects = {t["id"] for t in teams}, {p["id"] for p in projects}
    for team in await session.scalars(
        select(LinearTeam).where(LinearTeam.connection_ref == connection.id)
    ):
        team.removed = team.linear_id not in seen_teams
    for project in await session.scalars(
        select(LinearProject).where(LinearProject.connection_ref == connection.id)
    ):
        project.removed = project.linear_id not in seen_projects
    people = list(await session.scalars(select(Person).where(Person.status == "active")))
    for identity in await session.scalars(select(LinearIdentity)):
        _match(identity, people)
    connection.last_synced_at, connection.last_sync_status = func.now(), "ok"
    connection.last_sync_error = None
    # Self-scheduling reconciliation: at most one future sync is pending at a time.
    if ctx.jobs is not None and (
        connection.next_reconcile_at is None or connection.next_reconcile_at <= _now()
    ):
        connection.next_reconcile_at = _now() + RECONCILE_EVERY
        await outbox.emit(
            session,
            ctx.jobs,
            tenant_id=tenant,
            event_type=SYNC_EVENT,
            payload={"connection_ref": str(connection.id), "reconcile": True},
            schedule_at=connection.next_reconcile_at,
        )


outbox.register(SYNC_EVENT, handle_sync)


# ---------------------------------------------------------------- reads and review


async def get_integration(access: WorkspaceAccess, *, configured: bool) -> LinearIntegrationView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    connections = list(
        await access.session.scalars(
            select(LinearConnection).where(
                _mine(access, LinearConnection.tenant_id), LinearConnection.status != "disconnected"
            )
        )
    )
    teams = list(
        await access.session.scalars(
            select(LinearTeam).where(
                _mine(access, LinearTeam.tenant_id), LinearTeam.removed.is_(False)
            )
        )
    )
    projects = list(
        await access.session.scalars(
            select(LinearProject)
            .where(_mine(access, LinearProject.tenant_id), LinearProject.removed.is_(False))
            .order_by(LinearProject.name)
        )
    )
    identities = {
        i.linear_id: i
        for i in await access.session.scalars(
            select(LinearIdentity).where(_mine(access, LinearIdentity.tenant_id))
        )
    }
    since = _now() - timedelta(days=ACTIVITY_DAYS)
    issues = list(
        await access.session.scalars(
            select(LinearIssue).where(_mine(access, LinearIssue.tenant_id))
        )
    )
    names = dict(
        (
            await access.session.execute(
                select(Responsibility.id, Responsibility.name).where(
                    visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id)
                )
            )
        ).all()
    )
    return LinearIntegrationView(
        configured=configured,
        connections=[
            ConnectionView(
                id=c.id,
                organization_name=c.organization_name,
                url_key=c.url_key,
                status=c.status,
                last_synced_at=c.last_synced_at,
                last_sync_status=c.last_sync_status,
                last_sync_error=c.last_sync_error,
                next_reconcile_at=c.next_reconcile_at,
            )
            for c in connections
        ],
        teams=[{"id": str(t.id), "key": t.key, "name": t.name} for t in teams],
        projects=[
            ProjectView(
                id=p.id,
                name=p.name,
                state=p.state,
                url=p.url,
                lead=identities[p.lead_linear_id].name if p.lead_linear_id in identities else None,
                open_issues=sum(
                    1
                    for i in issues
                    if i.project_linear_id == p.linear_id
                    and i.state_type not in ("completed", "canceled")
                ),
                recent_issues=sum(
                    1
                    for i in issues
                    if i.project_linear_id == p.linear_id and i.li_updated_at >= since
                ),
                responsibility_id=p.responsibility_id,
                responsibility_name=names.get(p.responsibility_id) if p.responsibility_id else None,
            )
            for p in projects
        ],
        identities_to_review=sum(
            1
            for i in identities.values()
            if i.link_status in ("suggested", "unmatched") and i.active
        ),
    )


async def link_project(access: WorkspaceAccess, project_id: uuid.UUID, data: ProjectLinkIn) -> None:
    authorize(access, Permission.INTEGRATION_MANAGE)
    project = await access.session.scalar(
        select(LinearProject)
        .where(
            LinearProject.id == project_id,
            visible(access, Permission.INTEGRATION_MANAGE, LinearProject.tenant_id),
        )
        .with_for_update()
    )
    if project is None:
        raise ApiError(404, "project_not_found", "Linear project not found.")
    if data.action == "unlink":
        project.responsibility_id = None
    elif data.action == "create":
        created = await catalog.add_responsibility(
            access,
            catalog.ResponsibilityIn(
                name=f"Deliver {project.name}"[:200], description=f"Linear project: {project.url}"
            ),
        )
        project.responsibility_id = created.id
    else:
        if data.responsibility_id is None:
            raise ApiError(422, "responsibility_required", "Choose a responsibility.")
        await catalog.require_active_responsibility(access, data.responsibility_id)
        project.responsibility_id = data.responsibility_id
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=f"integration.linear_project_{_VERB[data.action]}",
        actor_user_id=access.user_id,
        target_type="linear_project",
        target_id=project.id,
        details={
            "responsibility_id": str(project.responsibility_id)
            if project.responsibility_id
            else None
        },
    )


async def list_identities(
    access: WorkspaceAccess, *, review_only: bool = False
) -> list[LinearIdentityView]:
    authorize(access, Permission.INTEGRATION_MANAGE)
    stmt = select(LinearIdentity).where(
        visible(access, Permission.INTEGRATION_MANAGE, LinearIdentity.tenant_id)
    )
    if review_only:
        stmt = stmt.where(
            LinearIdentity.link_status.in_(("suggested", "unmatched")),
            LinearIdentity.active.is_(True),
        )
    identities = list(await access.session.scalars(stmt.order_by(LinearIdentity.name)))
    people = {
        p.id: p
        for p in await access.session.scalars(
            select(Person).where(visible(access, Permission.DIRECTORY_READ, Person.tenant_id))
        )
    }
    since = _now() - timedelta(days=ACTIVITY_DAYS)
    counts = Counter(
        a
        for (a,) in await access.session.execute(
            select(LinearIssue.assignee_linear_id).where(
                visible(access, Permission.INTEGRATION_MANAGE, LinearIssue.tenant_id),
                LinearIssue.li_updated_at >= since,
            )
        )
        if a
    )

    def ref(pid: uuid.UUID) -> dict[str, Any] | None:
        return {"id": str(pid), "name": people[pid].display_name} if pid in people else None

    order = {"suggested": 0, "unmatched": 1, "linked": 2, "dismissed": 3}
    return sorted(
        (
            LinearIdentityView(
                id=i.id,
                name=i.name,
                email=i.email,
                active=i.active,
                link_status=i.link_status,
                person=ref(i.person_id) if i.person_id else None,
                suggested_person=ref(i.suggested_person_id) if i.suggested_person_id else None,
                match_reason=i.match_reason,
                recent_issues=counts.get(i.linear_id, 0),
            )
            for i in identities
        ),
        key=lambda v: (order[v.link_status], -v.recent_issues, v.name),
    )


async def decide_identity(
    access: WorkspaceAccess, identity_id: uuid.UUID, data: IdentityDecisionIn
) -> LinearIdentityView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    identity = await access.session.scalar(
        select(LinearIdentity)
        .where(
            LinearIdentity.id == identity_id,
            visible(access, Permission.INTEGRATION_MANAGE, LinearIdentity.tenant_id),
        )
        .with_for_update()
    )
    if identity is None:
        raise ApiError(404, "identity_not_found", "Linear user not found.")
    if data.action == "link":
        if data.person_id is None:
            raise ApiError(422, "person_required", "Choose the person to link.")
        person = await access.session.scalar(
            select(Person).where(
                Person.id == data.person_id,
                visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
            )
        )
        if person is None or person.status != "active":
            raise ApiError(422, "person_not_found", "That person does not exist.")
        identity.link_status, identity.person_id, identity.suggested_person_id = (
            "linked",
            person.id,
            None,
        )
    elif data.action == "unlink":
        identity.link_status, identity.person_id = "unmatched", None
    else:
        if identity.person_id is not None:
            raise ApiError(409, "linked", "Unlink before dismissing.")
        identity.link_status, identity.suggested_person_id = "dismissed", None
    identity.decided_by, identity.decided_at = access.user_id, _now()
    try:
        async with access.session.begin_nested():
            await access.session.flush()
    except IntegrityError as exc:
        raise ApiError(
            409, "person_already_linked", "That person is already linked to another Linear user."
        ) from exc
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=f"integration.linear_identity_{_VERB[data.action]}",
        actor_user_id=access.user_id,
        target_type="linear_identity",
        target_id=identity.id,
        details={"person_id": str(identity.person_id) if identity.person_id else None},
    )
    return next(v for v in await list_identities(access) if v.id == identity.id)


async def signals(access: WorkspaceAccess) -> list[SignalView]:
    """Deterministic, evidence-backed; recomputed on read; never changes ownership."""
    authorize(access, Permission.INTEGRATION_MANAGE)
    now = _now()
    since = now - timedelta(days=ACTIVITY_DAYS)
    projects = list(
        await access.session.scalars(
            select(LinearProject).where(
                _mine(access, LinearProject.tenant_id), LinearProject.removed.is_(False)
            )
        )
    )
    issues = list(
        await access.session.scalars(
            select(LinearIssue).where(
                _mine(access, LinearIssue.tenant_id), LinearIssue.li_updated_at >= since
            )
        )
    )
    identities = {
        i.linear_id: i
        for i in await access.session.scalars(
            select(LinearIdentity).where(_mine(access, LinearIdentity.tenant_id))
        )
    }
    primaries = {
        a.responsibility_id: a
        for a in await access.session.scalars(
            select(OwnershipAssignment).where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
                OwnershipAssignment.role == "primary",
                catalog.active_at(now),
            )
        )
    }
    by_project: dict[str, list[LinearIssue]] = defaultdict(list)
    for issue in issues:
        if issue.project_linear_id:
            by_project[issue.project_linear_id].append(issue)
    out: list[SignalView] = []
    for p in projects:
        mine_issues = sorted(
            by_project.get(p.linear_id, []), key=lambda i: i.li_updated_at, reverse=True
        )
        open_important = [
            i
            for i in mine_issues
            if i.priority in IMPORTANT_PRIORITIES and i.state_type not in ("completed", "canceled")
        ]
        base = {"project": p.name, "project_url": p.url, "responsibility_id": p.responsibility_id}
        owner = primaries.get(p.responsibility_id) if p.responsibility_id else None
        if open_important and (p.responsibility_id is None or owner is None):
            out.append(
                SignalView(
                    key=f"unowned_important:{p.id}",
                    kind="unowned_important",
                    severity="high",
                    title="Important work without an accountable owner",
                    explanation=f"{len(open_important)} urgent or high-priority open issues, but "
                    + (
                        "no responsibility covers this project."
                        if p.responsibility_id is None
                        else "its responsibility has no primary owner."
                    ),
                    evidence=[_issue_link(i) for i in open_important[:3]],
                    **base,
                )
            )
        if (
            p.responsibility_id is None
            and len(mine_issues) >= ACTIVE_THRESHOLD
            and not open_important
        ):
            out.append(
                SignalView(
                    key=f"active_uncovered:{p.id}",
                    kind="active_uncovered",
                    severity="medium",
                    title="Active project without responsibility coverage",
                    explanation=f"{len(mine_issues)} issues updated in the last "
                    f"{ACTIVITY_DAYS} days; link it to a responsibility.",
                    evidence=[_issue_link(i) for i in mine_issues[:3]],
                    **base,
                )
            )
        if owner is not None and owner.person_id is not None:
            owner_ids = {i.linear_id for i in identities.values() if i.person_id == owner.person_id}
            involved = {
                x for i in mine_issues for x in (i.assignee_linear_id, i.creator_linear_id) if x
            }
            others = [
                i
                for i in mine_issues
                if i.assignee_linear_id and i.assignee_linear_id not in owner_ids
            ]
            if owner_ids and not (owner_ids & involved) and len(others) >= ACTIVE_THRESHOLD:
                out.append(
                    SignalView(
                        key=f"owner_absent:{p.id}",
                        kind="owner_absent",
                        severity="medium",
                        title="Declared owner not seen in the project's work",
                        explanation="The responsibility's primary owner created or was "
                        "assigned none of the "
                        f"{len(mine_issues)} recent issues; {len(others)} are assigned to others.",
                        evidence=[_issue_link(i) for i in others[:3]],
                        **base,
                    )
                )
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(out, key=lambda s: (order[s.severity], s.project))
