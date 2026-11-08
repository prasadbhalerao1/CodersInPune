"""Background sync of GitHub identities, teams and PR/issue metadata (no source code).

Identity matching is deterministic and conservative:
- the person already carries this GitHub login (an admin set it)  -> linked;
- exactly one person's email equals the user's *public* GitHub email -> suggested;
- exactly one person's name equals the user's public name            -> suggested;
- anything ambiguous stays unmatched. Suggestions are never applied without review, and
  one identity can belong to at most one person (unique index), so people are never merged.
"""

import contextlib
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from relay.directory.models import Person
from relay.integrations.github.client import GitHubClient, GitHubError, User, WorkItem
from relay.integrations.github.models import (
    GitHubIdentity,
    GitHubInstallation,
    GitHubInstallationRoute,
    GitHubRepository,
    GitHubTeam,
    GitHubTeamMember,
    GitHubWorkItem,
)

MAX_PROFILE_LOOKUPS = 50  # per sync, to stay well inside API rate limits


def _norm(value: str | None) -> str:
    return " ".join((value or "").split()).casefold()


async def upsert_route(session: AsyncSession, tenant_id: uuid.UUID, installation_id: int) -> None:
    await session.execute(
        insert(GitHubInstallationRoute)
        .values(tenant_id=tenant_id, installation_id=installation_id)
        .on_conflict_do_nothing(index_elements=["tenant_id", "installation_id"])
    )


async def remove_route(session: AsyncSession, installation_id: int) -> None:
    await session.execute(
        delete(GitHubInstallationRoute).where(
            GitHubInstallationRoute.installation_id == installation_id
        )
    )


def _match(identity: GitHubIdentity, people: list[Person]) -> None:
    """Set link/suggestion state for an identity that nobody has decided on yet."""
    if identity.link_status in ("linked", "dismissed") or identity.decided_by is not None:
        return
    by_login = [p for p in people if (p.github_login or "").lower() == identity.login]
    if len(by_login) == 1:
        identity.link_status, identity.person_id = "linked", by_login[0].id
        identity.suggested_person_id = None
        identity.match_reason = "GitHub login recorded on the person"
        return
    candidates: list[tuple[list[Person], str]] = [
        (
            [
                p
                for p in people
                if identity.public_email and _norm(p.email) == identity.public_email
            ],
            "Public GitHub email matches the person's email",
        ),
        (
            [p for p in people if identity.name and _norm(p.display_name) == _norm(identity.name)],
            "Public GitHub name matches the person's name",
        ),
    ]
    for found, reason in candidates:
        if len(found) == 1 and not found[0].github_login:
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


async def upsert_identities(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    users: Iterable[User],
) -> dict[int, GitHubIdentity]:
    """Insert unseen users, refresh logins (renames), (re)match undecided identities."""
    unique = {u.github_id: u for u in users}
    if unique:
        await session.execute(
            insert(GitHubIdentity)
            .values(
                [
                    {"tenant_id": tenant_id, "github_user_id": u.github_id, "login": u.login}
                    for u in unique.values()
                ]
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "github_user_id"])
        )
    identities = {
        i.github_user_id: i
        for i in await session.scalars(
            select(GitHubIdentity).where(GitHubIdentity.github_user_id.in_(list(unique)))
        )
    }
    for gid, user in unique.items():
        identity = identities[gid]
        if identity.login != user.login:
            identity.login, identity.updated_at = user.login, func.now()
    people = list(await session.scalars(select(Person).where(Person.status == "active")))
    for identity in identities.values():
        _match(identity, people)
    return identities


async def sync_teams(
    session: AsyncSession, installation: GitHubInstallation, github: GitHubClient, token: str
) -> str | None:
    """Returns a user-facing note when teams could not be read (missing permission)."""
    if installation.account_type != "Organization":
        return None
    org = installation.account_login
    try:
        teams = await github.teams(token, org)
        members = {t.github_id: await github.team_members(token, org, t.slug) for t in teams}
    except GitHubError as exc:
        if exc.status in (401, 403, 404):
            return "Teams not synced: grant the app 'Organization > Members: Read-only'."
        raise
    identities = await upsert_identities(
        session, installation.tenant_id, (u for us in members.values() for u in us)
    )
    existing = {
        t.github_team_id: t
        for t in await session.scalars(
            select(GitHubTeam).where(GitHubTeam.installation_ref == installation.id)
        )
    }
    for team in teams:
        row = existing.get(team.github_id)
        if row is None:
            row = GitHubTeam(
                tenant_id=installation.tenant_id,
                installation_ref=installation.id,
                github_team_id=team.github_id,
                org_login=org.lower(),
                slug=team.slug,
                name=team.name,
            )
            session.add(row)
            await session.flush()
        row.slug, row.name, row.removed, row.updated_at = team.slug, team.name, False, func.now()
        # Membership is replaced as a set: GitHub is the source of truth for teams.
        await session.execute(
            delete(GitHubTeamMember).where(GitHubTeamMember.github_team_ref == row.id)
        )
        if members[team.github_id]:
            await session.execute(
                insert(GitHubTeamMember).values(
                    [
                        {
                            "tenant_id": installation.tenant_id,
                            "github_team_ref": row.id,
                            "identity_ref": identities[u.github_id].id,
                        }
                        for u in members[team.github_id]
                    ]
                )
            )
    seen = {t.github_id for t in teams}
    for gid, row in existing.items():
        if gid not in seen and not row.removed:
            row.removed, row.updated_at = True, func.now()
    return None


async def upsert_work_items(
    session: AsyncSession, repo: GitHubRepository, items: list[WorkItem]
) -> int:
    """Insert or update metadata; an older snapshot never overwrites a newer one, so
    delayed or out-of-order deliveries are harmless. Returns rows written."""
    written = 0
    for item in items:
        values = {
            "tenant_id": repo.tenant_id,
            "repository_id": repo.id,
            "kind": item.kind,
            "number": item.number,
            "github_id": item.github_id,
            "title": item.title,
            "state": item.state,
            "author_login": item.author.login if item.author else None,
            "assignee_logins": [u.login for u in item.assignees],
            "reviewer_logins": [u.login for u in item.reviewers],
            "labels": list(item.labels),
            "html_url": item.html_url,
            "gh_created_at": item.created_at,
            "gh_updated_at": item.updated_at,
            "closed_at": item.closed_at,
            "merged_at": item.merged_at,
        }
        stmt = insert(GitHubWorkItem).values(values)
        result = await session.execute(
            stmt.on_conflict_do_update(
                index_elements=["tenant_id", "repository_id", "kind", "number"],
                set_={
                    k: stmt.excluded[k] for k in values if k not in ("tenant_id", "repository_id")
                },
                where=GitHubWorkItem.gh_updated_at <= stmt.excluded.gh_updated_at,
            ).returning(GitHubWorkItem.id)
        )
        if result.scalar_one_or_none() is not None:
            written += 1
            if repo.last_activity_at is None or item.updated_at > repo.last_activity_at:
                repo.last_activity_at = item.updated_at
    users = [
        u
        for item in items
        for u in (item.author, *item.assignees, *item.reviewers)
        if u is not None
    ]
    await upsert_identities(session, repo.tenant_id, users)
    return written


def now() -> datetime:
    return datetime.now(UTC)


async def enrich_profiles(session: AsyncSession, github: GitHubClient, token: str) -> None:
    """Fetch public name/email for undecided identities not looked up yet, then re-match.
    An empty name records "looked up, nothing published" so it is not fetched again."""
    pending = list(
        await session.scalars(
            select(GitHubIdentity)
            .where(
                GitHubIdentity.name.is_(None),
                GitHubIdentity.link_status.in_(("unmatched", "suggested")),
            )
            .limit(MAX_PROFILE_LOOKUPS)
        )
    )
    for identity in pending:
        # Profile data only improves matching; never fail a sync over it.
        with contextlib.suppress(GitHubError):
            name, email = await github.profile(token, identity.login)
            identity.name, identity.public_email = name or "", email
    if pending:
        people = list(await session.scalars(select(Person).where(Person.status == "active")))
        for identity in pending:
            _match(identity, people)
