"""Project Memory Replay: how a responsibility's work got to where it is today.

Rebuilt on every request from what Relay already holds and the caller may see: ownership
periods, GitHub pull requests and issues, Linear issues, Notion page edits and recorded
knowledge and decisions. Nothing is stored. Each event is `factual`: its date and source
come straight from the record. The category is labelled with how it was derived (a
source label, words in the title, or the default) so a guess never reads as a fact.
AI narration over these events lives in `relay.intelligence.memory` and is `inferred`.

Events that reference each other (a pull request that says "fixes #12", a title that
names a Linear issue such as ENG-42) are linked; the link is factual, it is in the text.
"""

import re
import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import or_, select

from relay.catalog import service as catalog
from relay.catalog.knowledge import readable as knowledge_readable
from relay.catalog.models import KnowledgeItem, OwnershipAssignment
from relay.continuity.impact import SourceStatus, source_status
from relay.directory.models import Person, Team
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.audience import shared
from relay.integrations.github.models import GitHubRepository, GitHubWorkItem
from relay.integrations.linear.models import LinearIssue, LinearProject
from relay.integrations.notion.models import NotionPage, NotionSource
from relay.policy.permissions import Permission, authorize, visible

Category = Literal[
    "implementation",
    "bug_fix",
    "incident",
    "documentation",
    "technical_change",
    "decision",
    "ownership_change",
]
CATEGORIES: tuple[Category, ...] = (
    "implementation",
    "bug_fix",
    "incident",
    "documentation",
    "technical_change",
    "decision",
    "ownership_change",
)
MAX_EVENTS = 500
ROLE_LABEL = {"primary": "primary owner", "co_owner": "co-owner", "backup": "backup"}

# Checked in order: the first matching rule wins. Matched against labels, then the title.
_RULES: tuple[tuple[Category, re.Pattern[str]], ...] = (
    ("incident", re.compile(r"\b(incident|outage|sev[ -]?[0-4]|postmortem|post-mortem|p0)\b")),
    ("bug_fix", re.compile(r"\b(bug|fix|fixes|fixed|hotfix|regression|crash|broken)\b")),
    ("documentation", re.compile(r"\b(docs?|documentation|readme|runbook|guide)\b")),
    (
        "technical_change",
        re.compile(
            r"\b(refactor|upgrade|bump|migrat\w*|deps?|dependenc\w*|chore|ci|infra|perf|"
            r"performance|cleanup|deprecat\w*|security)\b"
        ),
    ),
)
_ISSUE_REF = re.compile(r"(?:^|[\s(])#(\d+)\b")
_LINEAR_REF = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")


class TimelineEvent(BaseModel):
    id: str  # stable within a responsibility, e.g. "gh:northwind/deploy#12"
    occurred_at: datetime
    category: Category
    category_basis: Literal["label", "title", "record", "default"]
    title: str
    summary: str
    significance: Literal["high", "medium", "low"]
    source_system: Literal["Relay", "GitHub", "Linear", "Notion"]
    source_url: str | None
    actor: str | None
    uncertainty_level: Literal["factual"] = "factual"
    linked_events: list[str] = []


class TimelineView(BaseModel):
    responsibility_id: uuid.UUID
    responsibility_name: str
    events: list[TimelineEvent]
    total: int  # before the category filter and limit
    counts: dict[str, int]  # per category, before the filter
    truncated: bool
    sources: list[SourceStatus]
    first_at: datetime | None
    last_at: datetime | None


def categorise(labels: list[str], title: str) -> tuple[Category, str]:
    for basis, text in (("label", " ".join(labels)), ("title", title)):
        lowered = text.lower().replace("_", " ")
        for category, pattern in _RULES:
            if pattern.search(lowered):
                return category, basis
    return "implementation", "default"


async def responsibility_timeline(
    access: WorkspaceAccess,
    responsibility_id: uuid.UUID,
    *,
    category: Category | None = None,
    before: datetime | None = None,
    limit: int = 200,
) -> TimelineView:
    authorize(access, Permission.RESPONSIBILITY_READ)
    resp = await catalog.get_responsibility(access, responsibility_id)  # 404 if not visible
    events = [
        *await _ownership(access, responsibility_id, resp.criticality),
        *await _github(access, responsibility_id),
        *await _linear(access, responsibility_id),
        *await _notion(access, responsibility_id),
        *await _knowledge(access, responsibility_id),
    ]
    _link(events)
    events.sort(key=lambda e: (e.occurred_at, e.id), reverse=True)
    counts = {c: 0 for c in CATEGORIES}
    for e in events:
        counts[e.category] += 1
    selected = [
        e
        for e in events
        if (category is None or e.category == category)
        and (before is None or e.occurred_at < before)
    ]
    limit = max(1, min(limit, MAX_EVENTS))
    return TimelineView(
        responsibility_id=responsibility_id,
        responsibility_name=resp.name,
        events=selected[:limit],
        total=len(events),
        counts=counts,
        truncated=len(selected) > limit,
        sources=await source_status(access),
        first_at=events[-1].occurred_at if events else None,
        last_at=events[0].occurred_at if events else None,
    )


async def _ownership(
    access: WorkspaceAccess, rid: uuid.UUID, criticality: str
) -> list[TimelineEvent]:
    session, now = access.session, datetime.now(UTC)
    names = {
        **dict((await session.execute(select(Person.id, Person.display_name))).all()),
        **dict((await session.execute(select(Team.id, Team.name))).all()),
    }
    out = []
    for a in await session.scalars(
        select(OwnershipAssignment).where(
            visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
            OwnershipAssignment.responsibility_id == rid,
            OwnershipAssignment.valid_from <= now,
        )
    ):
        who = names.get(a.person_id or a.team_id, "Someone")  # type: ignore[arg-type]
        role = ROLE_LABEL.get(a.role, a.role.replace("_", " "))
        significance: Literal["high", "medium", "low"] = (
            "high" if a.role == "primary" and criticality in ("critical", "high") else "medium"
        )
        out.append(
            TimelineEvent(
                id=f"own:{a.id}:start",
                occurred_at=a.valid_from,
                category="ownership_change",
                category_basis="record",
                title=f"{who} became {role}",
                summary=a.reason or f"{who} took on the {role} role.",
                significance=significance,
                source_system="Relay",
                source_url=None,
                actor=who,
            )
        )
        if a.valid_to is not None and a.valid_to <= now:
            out.append(
                TimelineEvent(
                    id=f"own:{a.id}:end",
                    occurred_at=a.valid_to,
                    category="ownership_change",
                    category_basis="record",
                    title=f"{who} stopped being {role}",
                    summary=a.reason or f"{who}'s {role} period ended.",
                    significance=significance,
                    source_system="Relay",
                    source_url=None,
                    actor=who,
                )
            )
    return out


async def _github(access: WorkspaceAccess, rid: uuid.UUID) -> list[TimelineEvent]:
    out = []
    for item, repo in await access.session.execute(
        select(GitHubWorkItem, GitHubRepository.full_name)
        .join(GitHubRepository, GitHubRepository.id == GitHubWorkItem.repository_id)
        .where(
            visible(access, Permission.RESPONSIBILITY_READ, GitHubWorkItem.tenant_id),
            GitHubRepository.responsibility_id == rid,
            shared(access, GitHubRepository.audience),
        )
        .order_by(GitHubWorkItem.gh_updated_at.desc())
        .limit(MAX_EVENTS)
    ):
        category, basis = categorise(item.labels, item.title)
        pr = item.kind == "pull_request"
        if item.merged_at:
            when, verb = item.merged_at, "merged"
        elif item.closed_at:
            when, verb = item.closed_at, "closed" if pr else "resolved"
        else:
            when, verb = item.gh_created_at, "opened"
        significance: Literal["high", "medium", "low"] = (
            "high"
            if category == "incident" or (verb == "merged" and category != "documentation")
            else "low"
            if verb == "opened" or category == "documentation"
            else "medium"
        )
        noun = "Pull request" if pr else "Issue"
        labels = f" Labels: {', '.join(item.labels)}." if item.labels else ""
        out.append(
            TimelineEvent(
                id=f"gh:{repo}#{item.number}",
                occurred_at=when,
                category=category,
                category_basis=basis,
                title=item.title,
                summary=f"{noun} #{item.number} in {repo} {verb}"
                + (f" by {item.author_login}" if item.author_login and pr else "")
                + f".{labels}",
                significance=significance,
                source_system="GitHub",
                source_url=item.html_url,
                actor=item.author_login,
            )
        )
    return out


async def _linear(access: WorkspaceAccess, rid: uuid.UUID) -> list[TimelineEvent]:
    out = []
    for issue, project in await access.session.execute(
        select(LinearIssue, LinearProject.name)
        .join(LinearProject, LinearProject.linear_id == LinearIssue.project_linear_id)
        .where(
            visible(access, Permission.RESPONSIBILITY_READ, LinearIssue.tenant_id),
            LinearProject.responsibility_id == rid,
            LinearProject.removed.is_(False),
            shared(access, LinearProject.audience),
            LinearIssue.state_type != "canceled",
        )
        .order_by(LinearIssue.li_updated_at.desc())
        .limit(MAX_EVENTS)
    ):
        category, basis = categorise(issue.labels, issue.title)
        done = issue.completed_at is not None
        out.append(
            TimelineEvent(
                id=f"li:{issue.identifier}",
                occurred_at=issue.completed_at or issue.li_updated_at,
                category=category,
                category_basis=basis,
                title=f"{issue.identifier} {issue.title}",
                summary=f"Linear issue in {project} "
                + ("completed." if done else f"updated ({issue.state_name or issue.state_type}).")
                + (" Urgent priority." if issue.priority == 1 else ""),
                significance="high"
                if issue.priority == 1 or category == "incident"
                else "medium"
                if done
                else "low",
                source_system="Linear",
                source_url=issue.url,
                actor=None,
            )
        )
    return out


async def _notion(access: WorkspaceAccess, rid: uuid.UUID) -> list[TimelineEvent]:
    return [
        TimelineEvent(
            id=f"no:{page.notion_id}",
            occurred_at=page.last_edited_at,
            category="documentation",
            category_basis="record",
            title=page.title,
            summary=f"Notion page in '{source}' last edited.",
            significance="low",
            source_system="Notion",
            source_url=page.url,
            actor=None,
        )
        for page, source in await access.session.execute(
            select(NotionPage, NotionSource.title)
            .join(NotionSource, NotionSource.id == NotionPage.source_ref)
            .where(
                visible(access, Permission.RESPONSIBILITY_READ, NotionPage.tenant_id),
                NotionSource.responsibility_id == rid,
                shared(access, NotionSource.visibility),
                NotionPage.status == "active",
            )
            .order_by(NotionPage.last_edited_at.desc())
            .limit(MAX_EVENTS)
        )
    ]


async def _knowledge(access: WorkspaceAccess, rid: uuid.UUID) -> list[TimelineEvent]:
    """Decisions at their decision date; other knowledge when it was first recorded.

    Notion imports are skipped here: the Notion page edit is already on the timeline.
    """
    out = []
    for k in await access.session.scalars(
        select(KnowledgeItem).where(
            knowledge_readable(access),
            KnowledgeItem.responsibility_id == rid,
            KnowledgeItem.status == "active",
            or_(KnowledgeItem.origin != "notion", KnowledgeItem.decided_at.is_not(None)),
        )
    ):
        decision = k.kind in ("adr", "decision") or k.decided_at is not None
        rationale = f" Why: {k.decision_rationale}" if k.decision_rationale else ""
        by = f" by {k.decision_approver}" if k.decision_approver else ""
        out.append(
            TimelineEvent(
                id=f"kn:{k.id}",
                occurred_at=k.decided_at or k.created_at,
                category="decision" if decision else "documentation",
                category_basis="record",
                title=k.title,
                summary=(
                    f"Decision recorded{by}."
                    if decision
                    else f"{k.kind.replace('_', ' ').capitalize()} recorded in Relay."
                )
                + rationale[:400],
                significance="high" if decision else "low",
                source_system="Relay",
                source_url=None,
                actor=k.decision_approver if decision else None,
            )
        )
    return out


def _link(events: list[TimelineEvent]) -> None:
    """Link events whose text names another event (#12 in the same repo, or ENG-42)."""
    by_id = {e.id: e for e in events}
    for e in events:
        text = f"{e.title} {e.summary}"
        targets: set[str] = set()
        if e.id.startswith("gh:"):
            repo = e.id[3:].split("#")[0]
            targets |= {f"gh:{repo}#{n}" for n in _ISSUE_REF.findall(f" {e.title}")}
        targets |= {f"li:{key}" for key in _LINEAR_REF.findall(text)}
        for target in targets - {e.id}:
            if target in by_id:
                if target not in e.linked_events:
                    e.linked_events.append(target)
                if e.id not in by_id[target].linked_events:
                    by_id[target].linked_events.append(e.id)
