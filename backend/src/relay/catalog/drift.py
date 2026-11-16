"""Code drift: knowledge that may be outdated because the code behind it changed.

A knowledge item belongs to a responsibility; a GitHub repository can be linked to the same
responsibility. When pull requests were merged into that repository after the item was last
reviewed (or written), the item is flagged "code changed since review", with the merged pull
requests as the evidence. It is a prompt to re-check, never an automatic change.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select

from relay.catalog.knowledge import readable as knowledge_readable
from relay.catalog.models import KnowledgeItem, Responsibility
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.audience import shared
from relay.integrations.github.models import GitHubRepository, GitHubWorkItem
from relay.policy.permissions import Permission, authorize, visible

LIMIT = 100


class CodeChange(BaseModel):
    title: str
    number: int
    repository: str
    url: str
    merged_at: datetime


class DriftItem(BaseModel):
    knowledge_id: uuid.UUID
    title: str
    kind: str
    responsibility_id: uuid.UUID
    responsibility_name: str
    checked_at: datetime  # last review, or when it was written
    merged_since: int
    latest: list[CodeChange]


async def code_drift(
    access: WorkspaceAccess, responsibility_id: uuid.UUID | None = None
) -> list[DriftItem]:
    """Knowledge whose responsibility's repositories had pull requests merged after the
    knowledge was last checked. Most changes first."""
    authorize(access, Permission.RESPONSIBILITY_READ)
    session = access.session
    checked = func.coalesce(KnowledgeItem.last_reviewed_at, KnowledgeItem.updated_at)
    query = (
        select(
            KnowledgeItem.id,
            KnowledgeItem.title,
            KnowledgeItem.kind,
            Responsibility.id,
            Responsibility.name,
            checked,
            GitHubWorkItem.title,
            GitHubWorkItem.number,
            GitHubRepository.full_name,
            GitHubWorkItem.html_url,
            GitHubWorkItem.merged_at,
        )
        .join(Responsibility, Responsibility.id == KnowledgeItem.responsibility_id)
        .join(GitHubRepository, GitHubRepository.responsibility_id == Responsibility.id)
        .join(GitHubWorkItem, GitHubWorkItem.repository_id == GitHubRepository.id)
        .where(
            knowledge_readable(access),
            visible(access, Permission.RESPONSIBILITY_READ, GitHubWorkItem.tenant_id),
            KnowledgeItem.status == "active",
            KnowledgeItem.superseded_by_id.is_(None),
            GitHubRepository.accessible.is_(True),
            shared(access, GitHubRepository.audience),
            GitHubWorkItem.merged_at.is_not(None),
            GitHubWorkItem.merged_at > checked,
        )
        .order_by(GitHubWorkItem.merged_at.desc())
        .limit(2000)
    )
    if responsibility_id is not None:
        query = query.where(Responsibility.id == responsibility_id)
    found: dict[uuid.UUID, DriftItem] = {}
    for kid, title, kind, rid, rname, at, pr, number, repo, url, merged in await session.execute(
        query
    ):
        item = found.get(kid)
        if item is None:
            item = found[kid] = DriftItem(
                knowledge_id=kid,
                title=title,
                kind=kind,
                responsibility_id=rid,
                responsibility_name=rname,
                checked_at=at,
                merged_since=0,
                latest=[],
            )
        item.merged_since += 1
        if len(item.latest) < 3:
            item.latest.append(
                CodeChange(title=pr, number=number, repository=repo, url=url, merged_at=merged)
            )
    return sorted(found.values(), key=lambda d: (-d.merged_since, d.title))[:LIMIT]
