"""Global search across the workspace, composed from each module's own visibility rules.

One endpoint, several small queries: every group applies the same `authorize`/`visible`
checks (and, for knowledge, the same managers-only filter) as the module's own list
endpoint, so search can never show something the list would hide. A group the caller has
no permission for is simply absent. Matching is case-insensitive substring on names
(PostgreSQL ILIKE) plus full-text search for knowledge content; no extra infrastructure.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import ColumnElement, func, or_, select

from relay.catalog.knowledge import readable as knowledge_readable
from relay.catalog.models import Asset, KnowledgeItem, OwnershipAssignment, Responsibility
from relay.continuity.models import ContinuityCase
from relay.directory.models import Department, Person, Team
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.audience import linear_issue_shared, shared
from relay.integrations.github.models import GitHubRepository, GitHubWorkItem
from relay.integrations.linear.models import LinearIssue, LinearTeam
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.risks.models import RiskRecord

Kind = Literal[
    "responsibility",
    "person",
    "team",
    "department",
    "asset",
    "case",
    "knowledge",
    "risk",
    "github",
    "linear",
]
PER_GROUP = 6  # the command-menu preview
FULL_PAGE = 25  # the search page, per kind


class SearchHit(BaseModel):
    kind: Kind
    id: str
    title: str
    detail: str | None = None
    status: str | None = None
    # External records link out; `updated_at` lets people judge freshness.
    url: str | None = None
    updated_at: datetime | None = None


class SearchView(BaseModel):
    query: str
    hits: list[SearchHit]
    # Hits per kind before any kind filter: the facet counts for this query.
    facets: dict[str, int] = {}


class Reason(BaseModel):
    kind: Literal["owns", "wrote", "worked_on"]
    text: str


class ExpertView(BaseModel):
    """Someone to ask, with the visible evidence why. Not a ranking or a score."""

    person_id: uuid.UUID
    name: str
    reasons: list[Reason]


def _like(column: Any, q: str) -> ColumnElement[bool]:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    result: ColumnElement[bool] = column.ilike(f"%{escaped}%", escape="\\")
    return result


async def search(
    access: WorkspaceAccess, q: str, *, kinds: list[str] | None = None, full: bool = False
) -> SearchView:
    """`full` returns more per kind (the search page); `kinds` narrows the results while the
    facets still count every kind."""
    authorize(access, Permission.WORKSPACE_READ)
    limit = FULL_PAGE if full else PER_GROUP
    q = " ".join(q.split())[:100]
    if len(q) < 2:
        return SearchView(query=q, hits=[])
    session, hits = access.session, []

    if role_allows(access.role, Permission.RESPONSIBILITY_READ):
        for r in await session.scalars(
            select(Responsibility)
            .where(
                visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
                or_(_like(Responsibility.name, q), _like(Responsibility.category, q)),
            )
            .order_by(Responsibility.status, Responsibility.name)
            .limit(limit)
        ):
            hits.append(
                SearchHit(
                    kind="responsibility",
                    id=str(r.id),
                    title=r.name,
                    detail=" · ".join(filter(None, [r.criticality.capitalize(), r.category])),
                    status=r.status,
                )
            )
        for a in await session.scalars(
            select(Asset)
            .where(
                visible(access, Permission.RESPONSIBILITY_READ, Asset.tenant_id),
                or_(_like(Asset.name, q), _like(Asset.url, q)),
            )
            .order_by(Asset.status, Asset.name)
            .limit(limit)
        ):
            hits.append(
                SearchHit(
                    kind="asset",
                    id=str(a.id),
                    title=a.name,
                    detail=a.asset_type.replace("_", " ").capitalize(),
                    status=a.status,
                )
            )
        tsquery = func.websearch_to_tsquery("english", q)
        for k, name in await session.execute(
            select(KnowledgeItem, Responsibility.name)
            .join(Responsibility, Responsibility.id == KnowledgeItem.responsibility_id)
            .where(
                knowledge_readable(access),
                KnowledgeItem.status == "active",
                or_(KnowledgeItem.search.op("@@")(tsquery), _like(KnowledgeItem.title, q)),
            )
            .order_by(func.ts_rank(KnowledgeItem.search, tsquery).desc(), KnowledgeItem.title)
            .limit(limit)
        ):
            hits.append(
                SearchHit(
                    kind="knowledge",
                    id=str(k.responsibility_id),
                    title=k.title,
                    detail=f"{name} · {k.kind.capitalize()}",
                )
            )
        for risk in await session.scalars(
            select(RiskRecord)
            .where(
                visible(access, Permission.RESPONSIBILITY_READ, RiskRecord.tenant_id),
                RiskRecord.status != "resolved",
                or_(_like(RiskRecord.title, q), _like(RiskRecord.subject, q)),
            )
            .order_by(RiskRecord.severity, RiskRecord.title)
            .limit(limit)
        ):
            hits.append(
                SearchHit(
                    kind="risk",
                    id=risk.risk_key,
                    title=f"{risk.title}: {risk.subject}" if risk.subject else risk.title,
                    detail=f"{risk.severity.capitalize()} severity",
                    status=risk.status,
                )
            )

    if role_allows(access.role, Permission.DIRECTORY_READ):
        for p in await session.scalars(
            select(Person)
            .where(
                visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
                or_(
                    _like(Person.display_name, q),
                    _like(Person.email, q),
                    _like(Person.title, q),
                    _like(Person.github_login, q),
                ),
            )
            .order_by(Person.status, Person.display_name)
            .limit(limit)
        ):
            hits.append(
                SearchHit(
                    kind="person",
                    id=str(p.id),
                    title=p.display_name,
                    detail=p.title or p.email,
                    status=p.status,
                )
            )
        for t in await session.scalars(
            select(Team)
            .where(visible(access, Permission.DIRECTORY_READ, Team.tenant_id), _like(Team.name, q))
            .order_by(Team.status, Team.name)
            .limit(limit)
        ):
            hits.append(
                SearchHit(kind="team", id=str(t.id), title=t.name, detail="Team", status=t.status)
            )
        for d in await session.scalars(
            select(Department)
            .where(
                visible(access, Permission.DIRECTORY_READ, Department.tenant_id),
                _like(Department.name, q),
            )
            .order_by(Department.status, Department.name)
            .limit(limit)
        ):
            hits.append(
                SearchHit(
                    kind="department",
                    id=str(d.id),
                    title=d.name,
                    detail="Department",
                    status=d.status,
                )
            )

    if role_allows(access.role, Permission.CASE_READ):
        for c in await session.scalars(
            select(ContinuityCase)
            .where(
                visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
                _like(ContinuityCase.title, q),
            )
            .order_by(ContinuityCase.created_at.desc())
            .limit(limit)
        ):
            hits.append(
                SearchHit(
                    kind="case",
                    id=str(c.id),
                    title=c.title,
                    detail=f"{c.case_type.capitalize()} case",
                    status=c.status,
                )
            )
    if role_allows(access.role, Permission.RESPONSIBILITY_READ):
        hits += await _external(access, q, limit)
    facets: dict[str, int] = {}
    for hit in hits:
        facets[hit.kind] = facets.get(hit.kind, 0) + 1
    if kinds:
        hits = [h for h in hits if h.kind in kinds]
    return SearchView(query=q, hits=hits, facets=facets)


async def _external(access: WorkspaceAccess, q: str, limit: int) -> list[SearchHit]:
    """GitHub and Linear records, only while their source is still connected and readable:
    an unselected, archived or inaccessible repository, or a removed Linear team, hides them."""
    session, hits = access.session, []
    for item, repo in await session.execute(
        select(GitHubWorkItem, GitHubRepository.full_name)
        .join(GitHubRepository, GitHubRepository.id == GitHubWorkItem.repository_id)
        .where(
            visible(access, Permission.RESPONSIBILITY_READ, GitHubWorkItem.tenant_id),
            GitHubRepository.accessible.is_(True),
            GitHubRepository.selected.is_(True),
            shared(access, GitHubRepository.audience),
            _like(GitHubWorkItem.title, q),
        )
        .order_by(GitHubWorkItem.gh_updated_at.desc())
        .limit(limit)
    ):
        hits.append(
            SearchHit(
                kind="github",
                id=str(item.id),
                title=item.title,
                detail=f"{repo} #{item.number} · {'PR' if item.kind == 'pull' else 'issue'}",
                status=item.state,
                url=item.html_url,
                updated_at=item.gh_updated_at,
            )
        )
    removed_teams = select(LinearTeam.linear_id).where(LinearTeam.removed.is_(True))
    for issue in await session.scalars(
        select(LinearIssue)
        .where(
            visible(access, Permission.RESPONSIBILITY_READ, LinearIssue.tenant_id),
            or_(
                LinearIssue.team_linear_id.is_(None),
                LinearIssue.team_linear_id.not_in(removed_teams),
            ),
            linear_issue_shared(access),
            or_(_like(LinearIssue.title, q), _like(LinearIssue.identifier, q)),
        )
        .order_by(LinearIssue.li_updated_at.desc())
        .limit(limit)
    ):
        hits.append(
            SearchHit(
                kind="linear",
                id=str(issue.id),
                title=issue.title,
                detail=f"{issue.identifier} · {issue.state_name or issue.state_type}",
                status=issue.state_type,
                url=issue.url,
                updated_at=issue.li_updated_at,
            )
        )
    return hits


async def experts(access: WorkspaceAccess, q: str) -> list[ExpertView]:
    """Who to ask about a topic, from transparent evidence the caller can already see:
    current ownership of matching responsibilities, knowledge they wrote, and GitHub work
    on matching items. People are listed with every reason; there is no score."""
    authorize(access, Permission.RESPONSIBILITY_READ)
    q = " ".join(q.split())[:100]
    if len(q) < 2:
        return []
    session = access.session
    found: dict[uuid.UUID, ExpertView] = {}
    people = {
        p.id: p
        for p in await session.scalars(
            select(Person).where(
                visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
                Person.status == "active",
            )
        )
    }

    def add(person_id: uuid.UUID | None, kind: str, text: str) -> None:
        person = people.get(person_id) if person_id else None
        if person is None:
            return
        view = found.setdefault(
            person.id, ExpertView(person_id=person.id, name=person.display_name, reasons=[])
        )
        if len(view.reasons) < 6:
            view.reasons.append(Reason(kind=kind, text=text))

    now = datetime.now(UTC)
    for role, name, person_id in await session.execute(
        select(OwnershipAssignment.role, Responsibility.name, OwnershipAssignment.person_id)
        .join(Responsibility, Responsibility.id == OwnershipAssignment.responsibility_id)
        .where(
            visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
            Responsibility.status == "active",
            OwnershipAssignment.person_id.is_not(None),
            OwnershipAssignment.valid_from <= now,
            or_(OwnershipAssignment.valid_to.is_(None), OwnershipAssignment.valid_to > now),
            or_(_like(Responsibility.name, q), _like(Responsibility.description, q)),
        )
        .limit(50)
    ):
        add(person_id, "owns", f"{role.replace('_', '-').capitalize()} of “{name}”")
    by_email = {p.email.lower(): p.id for p in people.values() if p.email}
    tsquery = func.websearch_to_tsquery("english", q)
    for title, email in await session.execute(
        select(KnowledgeItem.title, Membership.email)
        .join(Membership, Membership.user_id == KnowledgeItem.author_user_id)
        .join(Responsibility, Responsibility.id == KnowledgeItem.responsibility_id)
        .where(
            knowledge_readable(access),
            KnowledgeItem.status == "active",
            or_(KnowledgeItem.search.op("@@")(tsquery), _like(KnowledgeItem.title, q)),
        )
        .limit(50)
    ):
        add(by_email.get((email or "").lower()), "wrote", f"Wrote “{title}”")
    by_login = {p.github_login: p.id for p in people.values() if p.github_login}
    for title, number, author, repo in await session.execute(
        select(
            GitHubWorkItem.title,
            GitHubWorkItem.number,
            GitHubWorkItem.author_login,
            GitHubRepository.full_name,
        )
        .join(GitHubRepository, GitHubRepository.id == GitHubWorkItem.repository_id)
        .where(
            visible(access, Permission.RESPONSIBILITY_READ, GitHubWorkItem.tenant_id),
            GitHubRepository.accessible.is_(True),
            shared(access, GitHubRepository.audience),
            _like(GitHubWorkItem.title, q),
        )
        .order_by(GitHubWorkItem.gh_updated_at.desc())
        .limit(50)
    ):
        add(
            by_login.get((author or "").lower()),
            "worked_on",
            f"Opened {repo}#{number} “{title}”",
        )
    # Most evidence first; ties alphabetical. Order is for reading, not a judgement.
    return sorted(found.values(), key=lambda e: (-len(e.reasons), e.name))
