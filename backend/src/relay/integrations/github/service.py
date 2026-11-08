"""GitHub integration: connect, sync and evidence-based ownership suggestions.

Connect (security-critical; `installation_id` on GitHub's redirect can be spoofed):
1. A manager starts the flow; Relay stores a single-use state (hash) bound to the
   workspace and user, and sends them to GitHub's install page with `state`.
2. GitHub returns `code` + `installation_id` + `state`. Relay checks the state against the
   caller's verified membership, exchanges `code` for a user token and only accepts the
   installation if it appears in that user's `GET /user/installations`. The user token is
   discarded; only the installation id is stored.

Suggestions never change ownership by themselves. Approving one goes through the catalog
service (authorize + valid-time history + audit) and refuses to replace a primary owner.
"""

import asyncio
import hashlib
import json
import logging
import secrets
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import procrastinate
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.audit import service as audit
from relay.catalog import service as catalog
from relay.directory.models import Person, Team
from relay.identity.tokens import VerifiedIdentity
from relay.identity.workspace_access import WorkspaceAccess, open_workspace_access
from relay.integrations.github import directory_sync
from relay.integrations.github.client import (
    GitHubClient,
    GitHubError,
    GitHubNotConfiguredError,
    User,
    WorkItem,
)
from relay.integrations.github.models import (
    GitHubConnectState,
    GitHubInstallation,
    GitHubRepository,
    OwnershipSuggestion,
)
from relay.integrations.github.parsing import (
    OwnerEvidence,
    catalog_owner_slug,
    parse_catalog_info,
    parse_codeowners,
)
from relay.jobs import outbox
from relay.jobs.models import OutboxEvent
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import LongText, StrictInput
from relay.shared.errors import ApiError

logger = logging.getLogger(__name__)

SYNC_EVENT = "github.sync_requested"
STATE_TTL = timedelta(minutes=15)
CODEOWNERS_PATHS = (".github/CODEOWNERS", "CODEOWNERS", "docs/CODEOWNERS")
CATALOG_PATHS = ("catalog-info.yaml", "catalog-info.yml")
# Concurrent repositories per sync; well inside GitHub's secondary rate limits.
FETCH_CONCURRENCY = 8


# ---------------------------------------------------------------- schemas


class InstallationView(BaseModel):
    id: uuid.UUID
    installation_id: int
    account_login: str
    account_type: str
    status: str
    last_synced_at: datetime | None
    last_sync_status: str
    last_sync_error: str | None


class RepositoryView(BaseModel):
    id: uuid.UUID
    installation_ref: uuid.UUID
    full_name: str
    html_url: str
    private: bool
    archived: bool
    selected: bool
    accessible: bool
    last_synced_at: datetime | None
    sync_error: str | None
    responsibility_id: uuid.UUID | None


class IntegrationView(BaseModel):
    configured: bool
    installations: list[InstallationView]
    repositories: list[RepositoryView]
    open_suggestions: int


class MatchView(BaseModel):
    type: Literal["person", "team"]
    id: uuid.UUID
    name: str


class SuggestionView(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    repository: str
    repository_url: str
    handle: str
    handle_type: str
    proposed_role: str
    reason: str
    evidence: list[dict[str, Any]]
    status: str
    match: MatchView | None
    responsibility_id: uuid.UUID | None


class DecisionView(BaseModel):
    id: uuid.UUID
    status: str
    assignment_id: uuid.UUID | None


class ConnectView(BaseModel):
    install_url: str


class CompleteConnectIn(StrictInput):
    state: str
    code: str
    installation_id: int


class RepositoryUpdate(StrictInput):
    selected: bool


class SuggestionDecisionIn(StrictInput):
    action: Literal["approve", "dismiss", "defer", "reopen"]
    role: Literal["primary", "co_owner", "backup"] | None = None
    person_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    note: LongText | None = None


# ---------------------------------------------------------------- helpers


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _record(
    access: WorkspaceAccess,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    **details: str | int | None,
) -> None:
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=action,
        actor_user_id=access.user_id,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )


def _installation_view(i: GitHubInstallation) -> InstallationView:
    return InstallationView(
        id=i.id,
        installation_id=i.installation_id,
        account_login=i.account_login,
        account_type=i.account_type,
        status=i.status,
        last_synced_at=i.last_synced_at,
        last_sync_status=i.last_sync_status,
        last_sync_error=i.last_sync_error,
    )


def _repository_view(r: GitHubRepository) -> RepositoryView:
    return RepositoryView(
        id=r.id,
        installation_ref=r.installation_ref,
        full_name=r.full_name,
        html_url=r.html_url,
        private=r.private,
        archived=r.archived,
        selected=r.selected,
        accessible=r.accessible,
        last_synced_at=r.last_synced_at,
        sync_error=r.sync_error,
        responsibility_id=r.responsibility_id,
    )


async def _installation(access: WorkspaceAccess, installation_ref: uuid.UUID) -> GitHubInstallation:
    found = await access.session.scalar(
        select(GitHubInstallation)
        .where(
            GitHubInstallation.id == installation_ref,
            visible(access, Permission.INTEGRATION_MANAGE, GitHubInstallation.tenant_id),
        )
        .with_for_update()
    )
    if found is None:
        raise ApiError(404, "installation_not_found", "GitHub connection not found.")
    return found


# ---------------------------------------------------------------- connect / disconnect


async def start_connect(access: WorkspaceAccess, github: GitHubClient) -> ConnectView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    if not github.configured:
        raise ApiError(
            503, "github_not_configured", "The GitHub App is not configured on this server."
        )
    token = f"{access.tenant_id}.{secrets.token_urlsafe(32)}"
    access.session.add(
        GitHubConnectState(
            tenant_id=access.tenant_id,
            state_hash=_hash(token),
            user_id=access.user_id,
            expires_at=_now() + STATE_TTL,
        )
    )
    return ConnectView(install_url=github.install_url(token))


async def complete_connect(
    factory: async_sessionmaker[AsyncSession],
    identity: VerifiedIdentity,
    github: GitHubClient,
    jobs: procrastinate.App,
    data: CompleteConnectIn,
) -> uuid.UUID:
    """Returns the workspace id the installation was connected to."""
    try:
        workspace_id = uuid.UUID(data.state.split(".", 1)[0])
    except ValueError as exc:
        raise ApiError(400, "invalid_state", "This GitHub connection link is not valid.") from exc
    async with open_workspace_access(factory, identity, workspace_id) as access:
        authorize(access, Permission.INTEGRATION_MANAGE)
        state = await access.session.scalar(
            select(GitHubConnectState)
            .where(
                GitHubConnectState.state_hash == _hash(data.state),
                GitHubConnectState.user_id == access.user_id,
                GitHubConnectState.used_at.is_(None),
                GitHubConnectState.expires_at > func.now(),
            )
            .with_for_update()
        )
        if state is None:
            raise ApiError(
                400, "invalid_state", "This GitHub connection link expired or was already used."
            )
        state.used_at = func.now()
        try:
            installation = await github.verify_user_installation(data.code, data.installation_id)
        except GitHubNotConfiguredError as exc:
            raise ApiError(
                503, "github_not_configured", "The GitHub App is not configured."
            ) from exc
        except GitHubError as exc:
            raise ApiError(403, "installation_not_verified", str(exc)) from exc
        account = installation.get("account") or {}
        existing = await access.session.scalar(
            select(GitHubInstallation).where(
                GitHubInstallation.installation_id == data.installation_id
            )
        )
        if existing is None:
            existing = GitHubInstallation(
                id=uuid.uuid7(),
                tenant_id=access.tenant_id,
                installation_id=data.installation_id,
                account_login=str(account.get("login") or account.get("slug") or "unknown"),
                account_type=str(account.get("type") or "Organization"),
                connected_by=access.user_id,
            )
            access.session.add(existing)
        existing.status, existing.last_sync_status, existing.last_sync_error = (
            "active",
            "queued",
            None,
        )
        await access.session.flush()
        await directory_sync.upsert_route(access.session, access.tenant_id, data.installation_id)
        await outbox.emit(
            access.session,
            jobs,
            tenant_id=access.tenant_id,
            event_type=SYNC_EVENT,
            payload={"installation_ref": str(existing.id)},
        )
        _record(
            access,
            "integration.github_connected",
            "github_installation",
            existing.id,
            account=existing.account_login,
        )
    return workspace_id


async def disconnect(access: WorkspaceAccess, installation_ref: uuid.UUID) -> IntegrationView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    installation = await _installation(access, installation_ref)
    installation.status = "disconnected"
    await directory_sync.remove_route(access.session, installation.installation_id)
    repo_ids = select(GitHubRepository.id).where(
        GitHubRepository.installation_ref == installation_ref
    )
    await access.session.execute(
        update(OwnershipSuggestion)
        .where(
            OwnershipSuggestion.repository_id.in_(repo_ids),
            OwnershipSuggestion.status.in_(("open", "deferred")),
        )
        .values(status="withdrawn", updated_at=func.now())
    )
    _record(access, "integration.github_disconnected", "github_installation", installation.id)
    return await get_integration(access, configured=True)


async def request_sync(
    access: WorkspaceAccess, installation_ref: uuid.UUID, jobs: procrastinate.App
) -> IntegrationView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    installation = await _installation(access, installation_ref)
    if installation.status == "disconnected":
        raise ApiError(409, "disconnected", "Reconnect GitHub to sync.")
    installation.last_sync_status = "queued"
    await outbox.emit(
        access.session,
        jobs,
        tenant_id=access.tenant_id,
        event_type=SYNC_EVENT,
        payload={"installation_ref": str(installation_ref)},
    )
    _record(access, "integration.github_sync_requested", "github_installation", installation.id)
    return await get_integration(access, configured=True)


async def get_integration(access: WorkspaceAccess, *, configured: bool) -> IntegrationView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    installations = list(
        await access.session.scalars(
            select(GitHubInstallation)
            .where(visible(access, Permission.INTEGRATION_MANAGE, GitHubInstallation.tenant_id))
            .order_by(GitHubInstallation.created_at)
        )
    )
    repositories = list(
        await access.session.scalars(
            select(GitHubRepository)
            .where(visible(access, Permission.INTEGRATION_MANAGE, GitHubRepository.tenant_id))
            .order_by(GitHubRepository.full_name)
        )
    )
    open_count = await access.session.scalar(
        select(func.count())
        .select_from(OwnershipSuggestion)
        .where(
            visible(access, Permission.INTEGRATION_MANAGE, OwnershipSuggestion.tenant_id),
            OwnershipSuggestion.status == "open",
        )
    )
    return IntegrationView(
        configured=configured,
        installations=[_installation_view(i) for i in installations],
        repositories=[_repository_view(r) for r in repositories],
        open_suggestions=open_count or 0,
    )


async def set_repository_selected(
    access: WorkspaceAccess, repository_id: uuid.UUID, data: RepositoryUpdate
) -> RepositoryView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    repo = await access.session.get(GitHubRepository, repository_id, with_for_update=True)
    if repo is None:
        raise ApiError(404, "repository_not_found", "Repository not found.")
    repo.selected = data.selected
    if not data.selected:
        await access.session.execute(
            update(OwnershipSuggestion)
            .where(
                OwnershipSuggestion.repository_id == repo.id,
                OwnershipSuggestion.status.in_(("open", "deferred")),
            )
            .values(status="withdrawn", updated_at=func.now())
        )
    _record(
        access,
        "integration.github_repository_updated",
        "github_repository",
        repo.id,
        selected=str(data.selected),
    )
    return _repository_view(repo)


# ---------------------------------------------------------------- sync (background job)


def _proposals(
    evidence: list[OwnerEvidence],
) -> dict[str, tuple[str, str, str, list[dict[str, Any]]]]:
    """handle -> (handle_type, role, reason, evidence). One repo-wide primary at most."""
    by_handle: dict[str, list[OwnerEvidence]] = defaultdict(list)
    for e in evidence:
        by_handle[e.handle].append(e)
    maintainers = {e.handle for e in evidence if e.source == "maintainer"}
    primary = (
        next((e.handle for e in evidence if e.source == "catalog_info"), None)
        or next((e.handle for e in evidence if e.source == "codeowners" and e.repo_wide), None)
        # No declared owner: a sole maintainer is the only defensible primary.
        or (next(iter(maintainers)) if len(maintainers) == 1 and len(by_handle) == 1 else None)
    )
    result: dict[str, tuple[str, str, str, list[dict[str, Any]]]] = {}
    for handle, items in by_handle.items():
        sources = {i.source for i in items}
        if handle == primary:
            role = "primary"
        elif "codeowners" in sources and any(i.repo_wide for i in items):
            role = "co_owner"
        else:
            role = "backup"
        reasons = {
            "catalog_info": "Declared as owner in the Backstage catalog descriptor",
            "codeowners": "Listed in CODEOWNERS",
            "maintainer": "Has maintain/admin access to the repository",
            "activity": "Recently active in the repository",
        }
        result[handle] = (
            items[0].handle_type,
            role,
            "; ".join(reasons[s] for s in sorted(sources)),
            [{"source": i.source, "detail": i.detail, "url": i.url} for i in items],
        )
    return result


ACTIVITY_THRESHOLD = 3  # authored pull requests in the window to count as evidence


def activity_evidence(items: list[WorkItem], days: int) -> list[OwnerEvidence]:
    """People who authored several pull requests recently (deterministic, no scoring)."""
    authored: dict[str, list[WorkItem]] = defaultdict(list)
    for item in items:
        if item.kind == "pull_request" and item.author is not None:
            authored[item.author.login].append(item)
    return [
        OwnerEvidence(
            f"@{login}",
            "user",
            "activity",
            f"Authored {len(prs)} pull requests in the last {days} days",
            False,
            url=prs[0].html_url,
        )
        for login, prs in sorted(authored.items())
        if len(prs) >= ACTIVITY_THRESHOLD
    ]


async def _fetch_evidence(
    github: GitHubClient, token: str, full_name: str
) -> tuple[list[OwnerEvidence], list[User]]:
    """HTTP only (no session), so repositories can be fetched concurrently."""
    paths = (*CODEOWNERS_PATHS, *CATALOG_PATHS)
    contents, maintainers = await asyncio.gather(
        asyncio.gather(*(github.file(token, full_name, path) for path in paths)),
        github.maintainer_users(token, full_name),
    )
    found = dict(zip(paths, contents, strict=True))
    evidence: list[OwnerEvidence] = []
    for path in CODEOWNERS_PATHS:  # first match wins, in GitHub's precedence order
        if (content := found[path]) is not None:
            evidence += parse_codeowners(content, path)
            break
    for path in CATALOG_PATHS:
        if (content := found[path]) is not None:
            evidence += parse_catalog_info(content)
            break
    evidence += [
        OwnerEvidence(f"@{user.login}", "user", "maintainer", f"collaborator role: {role}", False)
        for user, role in maintainers
    ]
    return evidence, [user for user, _ in maintainers]


async def _apply_evidence(
    session: AsyncSession, repo: GitHubRepository, fetched: list[OwnerEvidence] | GitHubError
) -> bool:
    if isinstance(fetched, GitHubError):
        repo.sync_error = f"Could not read ownership files: {fetched}"[:300]
        return False
    evidence = fetched
    repo.sync_error, repo.last_synced_at = None, func.now()
    proposals = _proposals(evidence)
    existing = {
        s.handle: s
        for s in await session.scalars(
            select(OwnershipSuggestion).where(OwnershipSuggestion.repository_id == repo.id)
        )
    }
    for handle, (handle_type, role, reason, items) in proposals.items():
        digest = _hash(json.dumps(items, sort_keys=True))
        current = existing.get(handle)
        if current is None:
            session.add(
                OwnershipSuggestion(
                    tenant_id=repo.tenant_id,
                    repository_id=repo.id,
                    handle=handle,
                    handle_type=handle_type,
                    proposed_role=role,
                    reason=reason,
                    evidence=items,
                    evidence_hash=digest,
                )
            )
            continue
        changed = current.evidence_hash != digest
        current.proposed_role, current.reason, current.evidence, current.evidence_hash = (
            role,
            reason,
            items,
            digest,
        )
        if current.status == "withdrawn" or (
            changed and current.status in ("dismissed", "deferred")
        ):
            current.status = "open"  # new evidence earns a fresh review
        current.updated_at = func.now()
    for handle, stale in existing.items():
        if handle not in proposals and stale.status in ("open", "deferred"):
            stale.status, stale.updated_at = "withdrawn", func.now()
    return True


async def handle_sync(session: AsyncSession, event: OutboxEvent, ctx: outbox.JobContext) -> None:
    """Idempotent: re-running converges on the same repositories and suggestions."""
    if ctx.http is None or ctx.settings is None:
        raise RuntimeError("GitHub sync needs an HTTP client and settings")
    github = GitHubClient(ctx.settings, ctx.http)
    installation = await session.get(
        GitHubInstallation, uuid.UUID(str(event.payload["installation_ref"])), with_for_update=True
    )
    if installation is None or installation.status == "disconnected":
        return
    try:
        token = await github.installation_token(installation.installation_id)
        repositories = await github.repositories(token)
        await directory_sync.upsert_route(
            session, installation.tenant_id, installation.installation_id
        )
    except GitHubError as exc:
        if exc.status in (0,) or exc.status >= 500:
            raise  # transient: let the job retry
        installation.status = "revoked"
        installation.last_sync_status = "error"
        installation.last_sync_error = (
            "GitHub access was revoked or the app was uninstalled. Reconnect GitHub."
        )
        return
    except GitHubNotConfiguredError:
        installation.last_sync_status, installation.last_sync_error = (
            "error",
            "GitHub App is not configured.",
        )
        return
    known = {
        r.github_repo_id: r
        for r in await session.scalars(
            select(GitHubRepository).where(GitHubRepository.installation_ref == installation.id)
        )
    }
    seen: set[int] = set()
    for remote in repositories:
        seen.add(remote.github_id)
        repo = known.get(remote.github_id)
        if repo is None:
            repo = GitHubRepository(
                tenant_id=installation.tenant_id,
                installation_ref=installation.id,
                github_repo_id=remote.github_id,
                full_name=remote.full_name,
                html_url=remote.html_url,
                default_branch=remote.default_branch,
                private=remote.private,
                archived=remote.archived,
            )
            session.add(repo)
            await session.flush()
        repo.full_name, repo.html_url, repo.default_branch = (
            remote.full_name,
            remote.html_url,
            remote.default_branch,
        )
        repo.private, repo.archived, repo.accessible = remote.private, remote.archived, True
        repo.pushed_at = remote.pushed_at
    for github_id, repo in known.items():
        if github_id not in seen:
            repo.accessible, repo.sync_error = False, "No longer accessible to the GitHub App."
            await session.execute(
                update(OwnershipSuggestion)
                .where(
                    OwnershipSuggestion.repository_id == repo.id,
                    OwnershipSuggestion.status.in_(("open", "deferred")),
                )
                .values(status="withdrawn", updated_at=func.now())
            )
    ok = True
    targets = list(
        await session.scalars(
            select(GitHubRepository).where(
                GitHubRepository.installation_ref == installation.id,
                GitHubRepository.selected.is_(True),
                GitHubRepository.accessible.is_(True),
                GitHubRepository.archived.is_(False),
            )
        )
    )
    limit = asyncio.Semaphore(FETCH_CONCURRENCY)

    days = ctx.settings.github_activity_days
    since = datetime.now(UTC) - timedelta(days=days)
    notes: list[str] = []

    async def fetch(
        full_name: str,
    ) -> tuple[list[OwnerEvidence] | GitHubError, list[User], list[WorkItem] | GitHubError]:
        async with limit:
            users: list[User] = []
            try:
                evidence: list[OwnerEvidence] | GitHubError
                evidence, users = await _fetch_evidence(github, token, full_name)
            except GitHubError as exc:
                evidence = exc
            try:
                items: list[WorkItem] | GitHubError = await github.work_items(
                    token, full_name, since
                )
            except GitHubError as exc:
                items = exc
            return evidence, users, items

    # Reads run concurrently; writes stay sequential on the job's single session.
    fetched = await asyncio.gather(*(fetch(repo.full_name) for repo in targets))
    for repo, (evidence, users, items) in zip(targets, fetched, strict=True):
        if isinstance(items, GitHubError):
            if items.status in (401, 403):
                notes.append(
                    "Pull request and issue activity not synced: grant the app "
                    "'Pull requests: Read-only' and 'Issues: Read-only'."
                )
            elif items.status != 404:
                ok = False
        else:
            await directory_sync.upsert_work_items(session, repo, items)
            if not isinstance(evidence, GitHubError):
                evidence = evidence + activity_evidence(items, days)
        await directory_sync.upsert_identities(session, installation.tenant_id, users)
        ok = await _apply_evidence(session, repo, evidence) and ok
    team_note = await directory_sync.sync_teams(session, installation, github, token)
    if team_note:
        notes.append(team_note)
    await directory_sync.enrich_profiles(session, github, token)
    if not ok:
        notes.insert(0, "Some repositories could not be read; see each repository.")
    installation.status = "active"
    installation.last_synced_at = func.now()
    installation.last_sync_status = "ok" if ok and not notes else "partial"
    installation.last_sync_error = " ".join(dict.fromkeys(notes)) or None


outbox.register(SYNC_EVENT, handle_sync)


# ---------------------------------------------------------------- suggestions


async def _matches(access: WorkspaceAccess) -> tuple[dict[str, MatchView], dict[str, MatchView]]:
    people = {
        p.github_login.lower(): MatchView(type="person", id=p.id, name=p.display_name)
        for p in await access.session.scalars(
            select(Person).where(
                visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
                Person.github_login.is_not(None),
                Person.status == "active",
            )
        )
        if p.github_login
    }
    teams = {
        t.github_slug.lower(): MatchView(type="team", id=t.id, name=t.name)
        for t in await access.session.scalars(
            select(Team).where(
                visible(access, Permission.DIRECTORY_READ, Team.tenant_id),
                Team.github_slug.is_not(None),
                Team.status == "active",
            )
        )
        if t.github_slug
    }
    return people, teams


def _team_by_slug(teams: dict[str, MatchView], slug: str) -> MatchView | None:
    """Exact `org/team` match, else the team whose slug segment matches (only if unique)."""
    if slug in teams:
        return teams[slug]
    short = slug.rsplit("/", 1)[-1]
    candidates = [m for key, m in teams.items() if key.rsplit("/", 1)[-1] == short]
    return candidates[0] if len(candidates) == 1 else None


def _match(
    s: OwnershipSuggestion, people: dict[str, MatchView], teams: dict[str, MatchView]
) -> MatchView | None:
    if s.handle_type == "user":
        return people.get(s.handle.lstrip("@"))
    if s.handle_type == "team":
        return _team_by_slug(teams, s.handle.lstrip("@"))
    slug = catalog_owner_slug(s.handle)
    return _team_by_slug(teams, slug) or people.get(slug)


async def list_suggestions(
    access: WorkspaceAccess, *, status: str = "open"
) -> list[SuggestionView]:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    rows = (
        await access.session.execute(
            select(OwnershipSuggestion, GitHubRepository)
            .join(GitHubRepository, GitHubRepository.id == OwnershipSuggestion.repository_id)
            .where(
                visible(access, Permission.RESPONSIBILITY_MANAGE, OwnershipSuggestion.tenant_id),
                OwnershipSuggestion.status == status,
            )
            .order_by(
                GitHubRepository.full_name,
                OwnershipSuggestion.proposed_role,
                OwnershipSuggestion.handle,
            )
        )
    ).all()
    people, teams = await _matches(access)
    return [
        SuggestionView(
            id=s.id,
            repository_id=r.id,
            repository=r.full_name,
            repository_url=r.html_url,
            handle=s.handle,
            handle_type=s.handle_type,
            proposed_role=s.proposed_role,
            reason=s.reason,
            evidence=s.evidence,
            status=s.status,
            match=_match(s, people, teams),
            responsibility_id=r.responsibility_id,
        )
        for s, r in rows
    ]


_DECISIONS = {
    "approve": (("open", "deferred"), "approved"),
    "dismiss": (("open", "deferred"), "dismissed"),
    "defer": (("open",), "deferred"),
    "reopen": (("dismissed", "deferred"), "open"),
}


async def decide_suggestion(
    access: WorkspaceAccess, suggestion_id: uuid.UUID, data: SuggestionDecisionIn
) -> DecisionView:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    suggestion = await access.session.scalar(
        select(OwnershipSuggestion).where(OwnershipSuggestion.id == suggestion_id).with_for_update()
    )
    if suggestion is None:
        raise ApiError(404, "suggestion_not_found", "Suggestion not found.")
    allowed_from, outcome = _DECISIONS[data.action]
    if suggestion.status not in allowed_from:
        raise ApiError(
            409, "invalid_state", f"Can't {data.action} a {suggestion.status} suggestion."
        )
    if data.action == "approve":
        await _approve(access, suggestion, data)
    suggestion.status = outcome
    suggestion.decided_by, suggestion.decided_at, suggestion.updated_at = (
        access.user_id,
        func.now(),
        func.now(),
    )
    _record(
        access,
        f"suggestion.{outcome if outcome != 'open' else 'reopened'}",
        "ownership_suggestion",
        suggestion.id,
        handle=suggestion.handle,
        note=data.note,
    )
    return DecisionView(id=suggestion.id, status=outcome, assignment_id=suggestion.assignment_id)


async def _approve(
    access: WorkspaceAccess, suggestion: OwnershipSuggestion, data: SuggestionDecisionIn
) -> None:
    repo = await access.session.get_one(
        GitHubRepository, suggestion.repository_id, with_for_update=True
    )
    if (data.person_id is None) == (data.team_id is None):
        people, teams = await _matches(access)
        match = _match(suggestion, people, teams)
        if match is None:
            raise ApiError(
                422, "assignee_required", "Choose the person or team this GitHub handle belongs to."
            )
        data = data.model_copy(
            update={"person_id": match.id} if match.type == "person" else {"team_id": match.id}
        )
    if repo.responsibility_id is None:
        created = await catalog.create_responsibility(
            access,
            catalog.ResponsibilityIn(name=f"Maintain {repo.full_name}", category="Repository"),
        )
        repo.responsibility_id = created.id
    role: Literal["primary", "co_owner", "backup"] = data.role or suggestion.proposed_role  # type: ignore[assignment]
    detail = await catalog.assign_owner(
        access,
        repo.responsibility_id,
        catalog.AssignmentIn(
            role=role,
            person_id=data.person_id,
            team_id=data.team_id,
            reason=f"GitHub evidence for {repo.full_name}: {suggestion.reason}"[:4000],
        ),
    )
    holder = data.person_id or data.team_id
    assignment = next(
        a
        for a in detail.assignments
        if a.assignee.id == holder and a.role == role and a.state == "current"
    )
    suggestion.assignment_id = assignment.id
