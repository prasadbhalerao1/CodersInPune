"""Context Builder: the evidence pool a run may use (D2).

Built inside the requester's transaction with *their* access, so a run can only ever see
what that person could see at that moment. Each item gets a short reference (E1, E2…),
its source, revision and audience: knowledge keeps its own visibility ('managers' items
only reach managers); everything else in a case is visible to the whole workspace.

Source text is untrusted. `render` wraps every excerpt in an envelope the instructions
tell the model to treat as data, and strips anything that could close the envelope.
"""

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select

from relay.catalog import knowledge as catalog_knowledge
from relay.catalog.models import KnowledgeItem, OwnershipAssignment, Responsibility
from relay.continuity import service as continuity
from relay.continuity.impact import source_status
from relay.continuity.models import (
    CaseApproval,
    CaseComment,
    CaseReadinessCriterion,
    CaseScopeItem,
    CaseTask,
    ContinuityCase,
)
from relay.directory.models import Person, Team
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.github.models import GitHubRepository, GitHubWorkItem
from relay.integrations.linear.models import LinearIssue, LinearProject
from relay.integrations.notion.models import NotionPage
from relay.policy.permissions import Permission, visible

EXCERPT_LIMIT = 1200
MAX_COMMENTS = 40
MAX_WORK_ITEMS = 40
RECENT = timedelta(days=30)


@dataclass
class PoolItem:
    ref: str
    source_system: str
    source_type: str
    source_id: str
    title: str
    excerpt: str
    audience: str = "workspace"
    url: str | None = None
    revision: str | None = None
    source_ts: datetime | None = None
    # Not persisted: structured hints for the deterministic rules.
    facts: dict[str, object] = field(default_factory=dict)


@dataclass
class Pool:
    case_id: uuid.UUID
    case_title: str
    items: list[PoolItem]
    partial_sources: list[str]

    def get(self, ref: str) -> PoolItem | None:
        return next((i for i in self.items if i.ref == ref), None)

    def for_audience(self, audience: str) -> Pool:
        """The pool as a given audience may see it (managers see everything)."""
        if audience == "managers":
            return self
        items = [i for i in self.items if i.audience == "workspace"]
        return Pool(self.case_id, self.case_title, items, self.partial_sources)

    def input_hash(self) -> str:
        parts = sorted(
            f"{i.source_system}:{i.source_id}:{i.revision}:{i.audience}" for i in self.items
        )
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def _clip(text: str | None) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= EXCERPT_LIMIT else text[: EXCERPT_LIMIT - 1] + "…"


def _ts(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class _Builder:
    def __init__(self) -> None:
        self.items: list[PoolItem] = []

    def add(self, **kw: object) -> PoolItem:
        item = PoolItem(ref=f"E{len(self.items) + 1}", **kw)  # type: ignore[arg-type]
        item.excerpt = _clip(item.excerpt)
        self.items.append(item)
        return item


async def build_pool(access: WorkspaceAccess, case: ContinuityCase) -> Pool:
    """Everything about the case the requester can read now, as cited evidence."""
    session = access.session
    b = _Builder()
    people = dict((await session.execute(select(Person.id, Person.display_name))).all())
    teams = dict((await session.execute(select(Team.id, Team.name))).all())
    users = await continuity._member_names(access)

    b.add(
        source_system="relay",
        source_type="case",
        source_id=str(case.id),
        title=case.title,
        revision=f"plan-v{case.plan_version}",
        source_ts=case.updated_at,
        excerpt=(
            f"Case type {case.case_type}, status {case.status}"
            f"{', EMERGENCY' if case.emergency else ''}. Affected person: "
            f"{people.get(case.affected_person_id, '?') if case.affected_person_id else 'none'}. "
            f"Starts {_ts(case.starts_at)}; ends {_ts(case.ends_at) or 'open-ended'}. "
            f"Reason: {case.reason or 'not given'}."
        ),
        facts={"kind": "case"},
    )

    scope = list(
        await session.execute(
            select(CaseScopeItem, Responsibility)
            .join(Responsibility, Responsibility.id == CaseScopeItem.responsibility_id)
            .where(CaseScopeItem.case_id == case.id)
            .order_by(Responsibility.name)
        )
    )
    responsibility_ids = [r.id for _, r in scope]
    now = datetime.now(UTC)
    owners = list(
        await session.scalars(
            select(OwnershipAssignment).where(
                OwnershipAssignment.responsibility_id.in_(responsibility_ids),
                OwnershipAssignment.valid_from <= now,
                or_(OwnershipAssignment.valid_to.is_(None), OwnershipAssignment.valid_to > now),
            )
        )
    )
    for item, resp in scope:
        current = [o for o in owners if o.responsibility_id == resp.id]

        def holder(o: OwnershipAssignment) -> str:
            if o.person_id:
                return people.get(o.person_id, "unknown person")
            return f"team {teams.get(o.team_id, 'unknown')}" if o.team_id else "unknown"

        owner_text = "; ".join(f"{o.role}: {holder(o)}" for o in current) or "no current owners"
        recipient = (
            people.get(item.recipient_person_id, "unknown person")
            if item.recipient_person_id
            else (
                f"team {teams.get(item.recipient_team_id, '?')}" if item.recipient_team_id else None
            )
        )
        b.add(
            source_system="relay",
            source_type="responsibility",
            source_id=str(resp.id),
            title=resp.name,
            revision=f"v{resp.version}",
            source_ts=resp.updated_at,
            excerpt=(
                f"Criticality {resp.criticality}. Current owners: {owner_text}. In this case: "
                f"role {item.role}, handover state {item.state}, recipient "
                f"{recipient or 'not planned'}. Handover notes: {item.handover_notes or 'none'}. "
                f"{('Exception: ' + item.exception_reason) if item.exception_reason else ''} "
                f"Description: {resp.description or 'none'}"
            ),
            facts={
                "kind": "responsibility",
                "responsibility_id": str(resp.id),
                "criticality": resp.criticality,
                "roles": sorted({o.role for o in current}),
                "recipient": recipient,
                "scope_role": item.role,
                "exception": bool(item.exception_reason),
            },
        )

    for task in await session.scalars(
        select(CaseTask).where(CaseTask.case_id == case.id).order_by(CaseTask.created_at)
    ):
        b.add(
            source_system="relay",
            source_type="task",
            source_id=str(task.id),
            title=task.title,
            source_ts=task.completed_at or task.created_at,
            revision=task.status,
            excerpt=(
                f"Task status {task.status}; assignee "
                f"{users.get(task.assignee_user_id, '?') if task.assignee_user_id else 'nobody'}; "
                f"due {_ts(task.due_at) or 'no date'}. {task.description or ''}"
            ),
            facts={"kind": "task", "status": task.status, "due_at": task.due_at},
        )

    for c in await session.scalars(
        select(CaseReadinessCriterion)
        .where(CaseReadinessCriterion.case_id == case.id)
        .order_by(CaseReadinessCriterion.created_at)
    ):
        b.add(
            source_system="relay",
            source_type="readiness_criterion",
            source_id=str(c.id),
            title=c.title,
            revision=c.status,
            source_ts=c.resolved_at or c.created_at,
            excerpt=(
                f"Readiness criterion ({'mandatory' if c.mandatory else 'optional'}, "
                f"{c.criterion_type}) status {c.status}. {c.note or ''}"
            ),
            facts={"kind": "criterion", "status": c.status, "mandatory": c.mandatory},
        )

    for a in await session.scalars(
        select(CaseApproval)
        .where(CaseApproval.case_id == case.id)
        .order_by(CaseApproval.decided_at)
    ):
        b.add(
            source_system="relay",
            source_type="approval",
            source_id=str(a.id),
            title=f"Plan v{a.plan_version} {a.decision}",
            source_ts=a.decided_at,
            excerpt=f"Approval '{a.decision}' on plan v{a.plan_version}. {a.comment or ''}",
            facts={"kind": "approval", "decision": a.decision},
        )

    comments = list(
        await session.scalars(
            select(CaseComment)
            .where(CaseComment.case_id == case.id)
            .order_by(CaseComment.created_at.desc())
            .limit(MAX_COMMENTS)
        )
    )
    for cm in reversed(comments):
        b.add(
            source_system="relay",
            source_type="comment",
            source_id=str(cm.id),
            title=f"Comment by {users.get(cm.author_user_id, 'a member')}",
            source_ts=cm.created_at,
            excerpt=cm.body,
            facts={"kind": "comment"},
        )

    cutoff = await catalog_knowledge.review_cutoff(access)
    notion = dict(
        (r.knowledge_item_id, r)
        for r in await session.scalars(
            select(NotionPage).where(
                visible(access, Permission.RESPONSIBILITY_READ, NotionPage.tenant_id)
            )
        )
    )
    for k in await session.scalars(
        select(KnowledgeItem)
        .where(
            catalog_knowledge.readable(access),
            KnowledgeItem.responsibility_id.in_(responsibility_ids),
            KnowledgeItem.status == "active",
        )
        .order_by(KnowledgeItem.updated_at.desc())
    ):
        page = notion.get(k.id)
        reviewed = k.last_reviewed_at or k.created_at
        b.add(
            source_system="notion" if page else "relay",
            source_type="notion_page" if page else "knowledge",
            source_id=page.notion_id if page else str(k.id),
            title=k.title,
            url=page.url if page else k.url,
            revision=page.revision if page else k.updated_at.isoformat(),
            source_ts=page.last_edited_at if page else k.updated_at,
            audience="managers" if k.visibility == "managers" else "workspace",
            excerpt=f"[{k.kind}] {k.body or ''} {k.url or ''}",
            facts={
                "kind": "knowledge",
                "responsibility_id": str(k.responsibility_id),
                "stale": reviewed < cutoff,
                "reviewed": k.last_reviewed_at is not None,
                "origin": k.origin,
            },
        )

    readable = Permission.RESPONSIBILITY_READ
    since = now - RECENT
    repos = {
        r.id: r
        for r in await session.scalars(
            select(GitHubRepository).where(
                visible(access, readable, GitHubRepository.tenant_id),
                GitHubRepository.responsibility_id.in_(responsibility_ids),
            )
        )
    }
    for w in await session.scalars(
        select(GitHubWorkItem)
        .where(
            visible(access, readable, GitHubWorkItem.tenant_id),
            GitHubWorkItem.repository_id.in_(list(repos)),
            or_(GitHubWorkItem.state == "open", GitHubWorkItem.gh_updated_at >= since),
        )
        .order_by(GitHubWorkItem.gh_updated_at.desc())
        .limit(MAX_WORK_ITEMS)
    ):
        repo = repos[w.repository_id]
        b.add(
            source_system="github",
            source_type="pull_request" if w.kind == "pull_request" else "issue",
            source_id=f"{repo.full_name}#{w.number}",
            title=w.title,
            url=w.html_url,
            revision=w.gh_updated_at.isoformat(),
            source_ts=w.gh_updated_at,
            excerpt=(
                f"{repo.full_name}#{w.number} {w.kind} {w.state}"
                f"{' (merged)' if w.merged_at else ''}; author {w.author_login or '?'}; "
                f"assignees {', '.join(w.assignee_logins) or 'none'}; reviewers "
                f"{', '.join(w.reviewer_logins) or 'none'}; labels {', '.join(w.labels) or 'none'}."
            ),
            facts={
                "kind": "work",
                "open": w.state == "open",
                "responsibility_id": str(repo.responsibility_id),
            },
        )

    projects = {
        p.linear_id: p
        for p in await session.scalars(
            select(LinearProject).where(
                visible(access, readable, LinearProject.tenant_id),
                LinearProject.responsibility_id.in_(responsibility_ids),
                LinearProject.removed.is_(False),
            )
        )
    }
    for issue in await session.scalars(
        select(LinearIssue)
        .where(
            visible(access, readable, LinearIssue.tenant_id),
            LinearIssue.project_linear_id.in_(list(projects)),
            or_(
                and_(LinearIssue.completed_at.is_(None), LinearIssue.canceled_at.is_(None)),
                LinearIssue.li_updated_at >= since,
            ),
        )
        .order_by(LinearIssue.li_updated_at.desc())
        .limit(MAX_WORK_ITEMS)
    ):
        project = projects[issue.project_linear_id or ""]
        done = issue.completed_at is not None or issue.canceled_at is not None
        b.add(
            source_system="linear",
            source_type="issue",
            source_id=issue.identifier,
            title=issue.title,
            url=issue.url,
            revision=issue.li_updated_at.isoformat(),
            source_ts=issue.li_updated_at,
            excerpt=(
                f"{issue.identifier} in project {project.name}: "
                f"state {issue.state_name or issue.state_type}, "
                f"priority {issue.priority}, labels {', '.join(issue.labels) or 'none'}."
            ),
            facts={
                "kind": "work",
                "open": not done,
                "responsibility_id": str(project.responsibility_id),
            },
        )

    return Pool(
        case_id=case.id,
        case_title=case.title,
        items=b.items,
        partial_sources=await _partial_sources(access),
    )


async def _partial_sources(access: WorkspaceAccess) -> list[str]:
    """Connected tools whose last sync failed or that lost access: evidence may be missing."""
    return [s.source for s in await source_status(access) if s.state == "partial"]


_ENVELOPE = re.compile(r"</?\s*evidence[^>]*>", re.IGNORECASE)


def render(pool: Pool, audience: str = "managers") -> str:
    """Evidence block for prompts; items above `audience` are left out entirely."""
    lines = []
    for i in pool.items:
        if audience == "workspace" and i.audience != "workspace":
            continue
        text = _ENVELOPE.sub("", i.excerpt)
        lines.append(
            f'<evidence ref="{i.ref}" source="{i.source_system}/{i.source_type}" '
            f'title="{_ENVELOPE.sub("", i.title)[:200]}" at="{_ts(i.source_ts) or "?"}">'
            f"{text}</evidence>"
        )
    return "\n".join(lines)
