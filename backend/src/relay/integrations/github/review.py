"""Admin review of GitHub evidence: identities, teams, ownership signals, bulk decisions.

Everything here is visible only with `integration.manage` (owners and admins): GitHub
evidence can describe private repositories that ordinary members cannot see on GitHub.
Decisions are explicit, audited actions; nothing changes ownership by itself. Linking an
identity records the person's GitHub login (one identity per person, enforced in SQL).
"""

import uuid
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from relay.audit import service as audit
from relay.catalog.models import OwnershipAssignment, Responsibility
from relay.catalog.service import active_at
from relay.directory import service as directory
from relay.directory.models import Person, Team
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.github import service as github_service
from relay.integrations.github.models import (
    GitHubIdentity,
    GitHubRepository,
    GitHubTeam,
    GitHubTeamMember,
    GitHubWorkItem,
)
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

UNMAINTAINED_DAYS = 180
_IDENTITY_VERB = {
    "link": "linked",
    "create_person": "linked",
    "unlink": "unlinked",
    "dismiss": "dismissed",
}
_TEAM_VERB = {"link": "linked", "create": "created", "unlink": "unlinked"}
CONTRIBUTOR_THRESHOLD = 3


class PersonRef(BaseModel):
    id: uuid.UUID
    name: str


class IdentityView(BaseModel):
    id: uuid.UUID
    login: str
    name: str | None
    public_email: str | None
    link_status: str
    person: PersonRef | None
    suggested_person: PersonRef | None
    match_reason: str | None
    teams: list[str]
    recent_items: int
    profile_url: str


class IdentityDecisionIn(StrictInput):
    action: Literal["link", "unlink", "dismiss", "create_person"]
    person_id: uuid.UUID | None = None


class TeamMemberRef(BaseModel):
    login: str
    person: PersonRef | None


class GitHubTeamView(BaseModel):
    id: uuid.UUID
    org: str
    slug: str
    name: str
    removed: bool
    linked_team: PersonRef | None
    members: list[TeamMemberRef]


class TeamLinkIn(StrictInput):
    action: Literal["link", "create", "unlink"]
    team_id: uuid.UUID | None = None
    import_members: bool = True


class EvidenceLink(BaseModel):
    label: str
    url: str


class SignalView(BaseModel):
    key: str
    kind: Literal["owner_inactive", "active_non_owner", "unmaintained", "unowned_active"]
    severity: Literal["high", "medium", "low"]
    title: str
    explanation: str
    repository: str
    repository_url: str
    responsibility: PersonRef | None
    evidence: list[EvidenceLink]


class BulkDecisionIn(StrictInput):
    ids: Annotated[list[uuid.UUID], Field(min_length=1, max_length=100)]
    action: Literal["approve", "dismiss", "defer"]


class BulkResultView(BaseModel):
    id: uuid.UUID
    ok: bool
    status: str | None
    error: str | None


def _now() -> datetime:
    return datetime.now(UTC)


async def _people(access: WorkspaceAccess) -> dict[uuid.UUID, Person]:
    return {
        p.id: p
        for p in await access.session.scalars(
            select(Person).where(visible(access, Permission.DIRECTORY_READ, Person.tenant_id))
        )
    }


def _ref(person: Person | None) -> PersonRef | None:
    return PersonRef(id=person.id, name=person.display_name) if person else None


def _record(
    access: WorkspaceAccess,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    **details: str | None,
) -> None:
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=action,
        actor_user_id=access.user_id,
        target_type=target_type,
        target_id=target_id,
        details=dict(details),
    )


# ---------------------------------------------------------------- identities


async def list_identities(
    access: WorkspaceAccess, *, status: str | None = None
) -> list[IdentityView]:
    authorize(access, Permission.INTEGRATION_MANAGE)
    stmt = select(GitHubIdentity).where(
        visible(access, Permission.INTEGRATION_MANAGE, GitHubIdentity.tenant_id)
    )
    if status == "review":
        stmt = stmt.where(GitHubIdentity.link_status.in_(("suggested", "unmatched")))
    elif status:
        stmt = stmt.where(GitHubIdentity.link_status == status)
    identities = list(await access.session.scalars(stmt.order_by(GitHubIdentity.login).limit(500)))
    people = await _people(access)
    teams: dict[uuid.UUID, list[str]] = defaultdict(list)
    for identity_ref, org, slug in await access.session.execute(
        select(GitHubTeamMember.identity_ref, GitHubTeam.org_login, GitHubTeam.slug)
        .join(GitHubTeam, GitHubTeam.id == GitHubTeamMember.github_team_ref)
        .where(GitHubTeam.removed.is_(False))
    ):
        teams[identity_ref].append(f"{org}/{slug}")
    since = _now() - timedelta(days=90)
    activity: Counter[str] = Counter(
        login or ""
        for (login,) in await access.session.execute(
            select(GitHubWorkItem.author_login).where(
                visible(access, Permission.INTEGRATION_MANAGE, GitHubWorkItem.tenant_id),
                GitHubWorkItem.gh_updated_at >= since,
                GitHubWorkItem.author_login.is_not(None),
            )
        )
    )
    order = {"suggested": 0, "unmatched": 1, "linked": 2, "dismissed": 3}
    return sorted(
        (
            IdentityView(
                id=i.id,
                login=i.login,
                name=i.name or None,
                public_email=i.public_email,
                link_status=i.link_status,
                person=_ref(people.get(i.person_id)) if i.person_id else None,
                suggested_person=_ref(people.get(i.suggested_person_id))
                if i.suggested_person_id
                else None,
                match_reason=i.match_reason,
                teams=sorted(teams.get(i.id, [])),
                recent_items=activity.get(i.login, 0),
                profile_url=f"https://github.com/{i.login}",
            )
            for i in identities
        ),
        key=lambda v: (order[v.link_status], -v.recent_items, v.login),
    )


async def decide_identity(
    access: WorkspaceAccess, identity_id: uuid.UUID, data: IdentityDecisionIn
) -> IdentityView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    identity = await access.session.scalar(
        select(GitHubIdentity)
        .where(
            GitHubIdentity.id == identity_id,
            visible(access, Permission.INTEGRATION_MANAGE, GitHubIdentity.tenant_id),
        )
        .with_for_update()
    )
    if identity is None:
        raise ApiError(404, "identity_not_found", "GitHub identity not found.")
    previous = identity.person_id
    if data.action in ("link", "create_person"):
        if identity.link_status == "linked":
            raise ApiError(409, "already_linked", "Unlink this identity first.")
        if data.action == "create_person":
            created = await directory.create_person(
                access,
                directory.PersonIn(
                    display_name=identity.name or identity.login, github_login=identity.login
                ),
            )
            person_id = created.id
        else:
            if data.person_id is None:
                raise ApiError(422, "person_required", "Choose the person to link.")
            person = (await _people(access)).get(data.person_id)
            if person is None or person.status != "active":
                raise ApiError(422, "person_not_found", "That person does not exist.")
            if person.github_login and person.github_login != identity.login:
                raise ApiError(
                    409,
                    "person_has_other_login",
                    f"{person.display_name} is already linked to @{person.github_login}.",
                )
            person_id = person.id
            if person.github_login != identity.login:
                await directory.update_person(
                    access, person_id, directory.PersonUpdate(github_login=identity.login)
                )
        identity.link_status, identity.person_id = "linked", person_id
        identity.suggested_person_id = None
    elif data.action == "unlink":
        if identity.person_id is None:
            raise ApiError(409, "not_linked", "This identity is not linked.")
        await directory.update_person(
            access, identity.person_id, directory.PersonUpdate(github_login=None)
        )
        identity.link_status, identity.person_id = "unmatched", None
    else:
        if identity.person_id is not None:
            raise ApiError(409, "linked", "Unlink before dismissing.")
        identity.link_status, identity.suggested_person_id = "dismissed", None
    identity.decided_by, identity.decided_at, identity.updated_at = access.user_id, _now(), _now()
    try:
        async with access.session.begin_nested():
            await access.session.flush()
    except IntegrityError as exc:
        raise ApiError(
            409, "person_already_linked", "That person is already linked to another GitHub user."
        ) from exc
    _record(
        access,
        f"integration.github_identity_{_IDENTITY_VERB[data.action]}",
        "github_identity",
        identity.id,
        person_id=str(identity.person_id or previous) if (identity.person_id or previous) else None,
    )
    return next(v for v in await list_identities(access) if v.id == identity.id)


# ---------------------------------------------------------------- teams


async def list_github_teams(access: WorkspaceAccess) -> list[GitHubTeamView]:
    authorize(access, Permission.INTEGRATION_MANAGE)
    teams = list(
        await access.session.scalars(
            select(GitHubTeam)
            .where(visible(access, Permission.INTEGRATION_MANAGE, GitHubTeam.tenant_id))
            .order_by(GitHubTeam.removed, GitHubTeam.org_login, GitHubTeam.slug)
        )
    )
    relay_teams = {
        t.id: t
        for t in await access.session.scalars(
            select(Team).where(visible(access, Permission.DIRECTORY_READ, Team.tenant_id))
        )
    }
    people = await _people(access)
    members: dict[uuid.UUID, list[TeamMemberRef]] = defaultdict(list)
    for team_ref, identity in await access.session.execute(
        select(GitHubTeamMember.github_team_ref, GitHubIdentity)
        .join(GitHubIdentity, GitHubIdentity.id == GitHubTeamMember.identity_ref)
        .order_by(GitHubIdentity.login)
    ):
        members[team_ref].append(
            TeamMemberRef(
                login=identity.login,
                person=_ref(people.get(identity.person_id)) if identity.person_id else None,
            )
        )
    return [
        GitHubTeamView(
            id=t.id,
            org=t.org_login,
            slug=t.slug,
            name=t.name,
            removed=t.removed,
            linked_team=PersonRef(id=t.team_id, name=relay_teams[t.team_id].name)
            if t.team_id and t.team_id in relay_teams
            else None,
            members=members.get(t.id, []),
        )
        for t in teams
    ]


async def link_team(
    access: WorkspaceAccess, github_team_id: uuid.UUID, data: TeamLinkIn
) -> GitHubTeamView:
    authorize(access, Permission.INTEGRATION_MANAGE)
    gh_team = await access.session.scalar(
        select(GitHubTeam)
        .where(
            GitHubTeam.id == github_team_id,
            visible(access, Permission.INTEGRATION_MANAGE, GitHubTeam.tenant_id),
        )
        .with_for_update()
    )
    if gh_team is None:
        raise ApiError(404, "team_not_found", "GitHub team not found.")
    slug = f"{gh_team.org_login}/{gh_team.slug}"
    if data.action == "unlink":
        if gh_team.team_id is None:
            raise ApiError(409, "not_linked", "This team is not linked.")
        await directory.update_team(access, gh_team.team_id, directory.TeamUpdate(github_slug=None))
        gh_team.team_id = None
    else:
        if gh_team.team_id is not None:
            raise ApiError(409, "already_linked", "Unlink this team first.")
        if data.action == "create":
            team_id = (
                await directory.create_team(
                    access, directory.TeamIn(name=gh_team.name, github_slug=slug)
                )
            ).id
        else:
            if data.team_id is None:
                raise ApiError(422, "team_required", "Choose the Relay team to link.")
            await directory.update_team(
                access, data.team_id, directory.TeamUpdate(github_slug=slug)
            )
            team_id = data.team_id
        gh_team.team_id = team_id
        if data.import_members:
            # Adds linked people only; never removes anyone from the Relay team.
            for person_id in await access.session.scalars(
                select(GitHubIdentity.person_id)
                .join(GitHubTeamMember, GitHubTeamMember.identity_ref == GitHubIdentity.id)
                .where(
                    GitHubTeamMember.github_team_ref == gh_team.id,
                    GitHubIdentity.person_id.is_not(None),
                )
            ):
                if person_id is not None:
                    await directory.add_team_member(access, team_id, person_id)
    _record(access, f"integration.github_team_{_TEAM_VERB[data.action]}", "github_team", gh_team.id)
    await access.session.flush()
    return next(t for t in await list_github_teams(access) if t.id == gh_team.id)


# ---------------------------------------------------------------- ownership signals


async def ownership_signals(access: WorkspaceAccess, *, days: int = 90) -> list[SignalView]:
    """Deterministic, evidence-backed observations. They inform people; they never change
    ownership and are recomputed from current data on every read."""
    authorize(access, Permission.INTEGRATION_MANAGE)
    now = _now()
    since = now - timedelta(days=days)
    repos = list(
        await access.session.scalars(
            select(GitHubRepository).where(
                visible(access, Permission.INTEGRATION_MANAGE, GitHubRepository.tenant_id),
                GitHubRepository.selected.is_(True),
                GitHubRepository.accessible.is_(True),
                GitHubRepository.archived.is_(False),
            )
        )
    )
    items = list(
        await access.session.scalars(
            select(GitHubWorkItem).where(
                visible(access, Permission.INTEGRATION_MANAGE, GitHubWorkItem.tenant_id),
                GitHubWorkItem.repository_id.in_([r.id for r in repos]),
                GitHubWorkItem.gh_updated_at >= since,
            )
        )
    )
    responsibilities = {
        r.id: r
        for r in await access.session.scalars(
            select(Responsibility).where(
                visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
                Responsibility.status == "active",
            )
        )
    }
    current = list(
        await access.session.scalars(
            select(OwnershipAssignment).where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
                active_at(now),
            )
        )
    )
    people = await _people(access)
    login_of = {p.id: p.github_login for p in people.values() if p.github_login}
    by_repo: dict[uuid.UUID, list[GitHubWorkItem]] = defaultdict(list)
    for item in items:
        by_repo[item.repository_id].append(item)

    signals: list[SignalView] = []
    for repo in repos:
        mine = sorted(by_repo.get(repo.id, []), key=lambda i: i.gh_updated_at, reverse=True)
        responsibility = (
            responsibilities.get(repo.responsibility_id) if repo.responsibility_id else None
        )
        resp_ref = (
            PersonRef(id=responsibility.id, name=responsibility.name) if responsibility else None
        )
        last = max(
            (d for d in (repo.pushed_at, repo.last_activity_at) if d is not None), default=None
        )
        base = {
            "repository": repo.full_name,
            "repository_url": repo.html_url,
            "responsibility": resp_ref,
        }
        if last is not None and last < now - timedelta(days=UNMAINTAINED_DAYS):
            signals.append(
                SignalView(
                    key=f"unmaintained:{repo.id}",
                    kind="unmaintained",
                    severity="medium" if responsibility else "low",
                    title="Possibly unmaintained",
                    explanation=f"No pushes, pull requests or issues since {last:%d %b %Y}.",
                    evidence=[EvidenceLink(label="Repository", url=repo.html_url)],
                    **base,
                )
            )
        if not mine:
            continue
        if responsibility is None:
            signals.append(
                SignalView(
                    key=f"unowned_active:{repo.id}",
                    kind="unowned_active",
                    severity="medium",
                    title="Active but not covered by a responsibility",
                    explanation=f"{len(mine)} pull requests or issues in the last {days} days, "
                    "but no responsibility looks after this repository.",
                    evidence=[
                        EvidenceLink(label=f"#{i.number} {i.title}", url=i.html_url)
                        for i in mine[:3]
                    ],
                    **base,
                )
            )
            continue
        holders = [a for a in current if a.responsibility_id == responsibility.id and a.person_id]
        holder_logins = {login_of[a.person_id] for a in holders if a.person_id in login_of}
        authored: dict[str, list[GitHubWorkItem]] = defaultdict(list)
        involved: set[str] = set()
        for i in mine:
            if i.author_login:
                authored[i.author_login].append(i)
            involved |= {i.author_login or "", *i.assignee_logins, *i.reviewer_logins}
        primary = next((a for a in holders if a.role == "primary"), None)
        primary_login = login_of.get(primary.person_id) if primary and primary.person_id else None
        others = sum(len(v) for k, v in authored.items() if k != primary_login)
        owner = people.get(primary.person_id) if primary and primary.person_id else None
        owner_name = owner.display_name if owner else "The primary owner"
        if primary_login and primary_login not in involved and others >= CONTRIBUTOR_THRESHOLD:
            signals.append(
                SignalView(
                    key=f"owner_inactive:{repo.id}",
                    kind="owner_inactive",
                    severity="high"
                    if responsibility.criticality in ("critical", "high")
                    else "medium",
                    title="Declared owner not seen in recent activity",
                    explanation=f"{owner_name} (@{primary_login}) is the "
                    f"primary owner but authored, reviewed or was assigned none of the "
                    f"{len(mine)} recent items; others authored {others}.",
                    evidence=[
                        EvidenceLink(label=f"#{i.number} by @{i.author_login}", url=i.html_url)
                        for i in mine[:3]
                    ],
                    **base,
                )
            )
        for login, prs in sorted(authored.items()):
            if len(prs) >= CONTRIBUTOR_THRESHOLD and login not in holder_logins:
                person = next((p for p in people.values() if p.github_login == login), None)
                who = person.display_name if person else f"@{login} (not linked to a person)"
                signals.append(
                    SignalView(
                        key=f"active_non_owner:{repo.id}:{login}",
                        kind="active_non_owner",
                        severity="low",
                        title="Frequent contributor holds no role",
                        explanation=f"{who} authored {len(prs)} items in the last {days} days "
                        f"but has no role on “{responsibility.name}”. Consider them as a backup.",
                        evidence=[
                            EvidenceLink(label=f"#{i.number} {i.title}", url=i.html_url)
                            for i in prs[:3]
                        ],
                        **base,
                    )
                )
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(signals, key=lambda s: (order[s.severity], s.repository, s.key))


# ---------------------------------------------------------------- bulk review


async def bulk_decide(access: WorkspaceAccess, data: BulkDecisionIn) -> list[BulkResultView]:
    """Each suggestion is decided in its own savepoint: one failure (e.g. no matched owner,
    or a primary already set) never blocks or undoes the others."""
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    results: list[BulkResultView] = []
    for suggestion_id in dict.fromkeys(data.ids):
        try:
            async with access.session.begin_nested():
                decided = await github_service.decide_suggestion(
                    access, suggestion_id, github_service.SuggestionDecisionIn(action=data.action)
                )
            results.append(
                BulkResultView(id=suggestion_id, ok=True, status=decided.status, error=None)
            )
        except ApiError as exc:
            results.append(
                BulkResultView(id=suggestion_id, ok=False, status=None, error=exc.detail)
            )
    _record(
        access,
        "integration.github_suggestions_bulk_decided",
        "workspace",
        access.tenant_id,
        decision=data.action,
        succeeded=str(sum(r.ok for r in results)),
    )
    return results
