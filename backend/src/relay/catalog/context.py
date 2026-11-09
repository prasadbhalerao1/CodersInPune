"""Continuity context for one responsibility, with every item labelled by what it is.

Users must be able to tell apart:
- risk signals: deterministic gaps Relay detected (open, acknowledged or accepted),
- cases: continuity work in progress that involves this responsibility,
- external evidence: sources an admin linked (GitHub repositories, Linear projects,
  Notion pages) with metadata read from those tools,
- suggestions: relationships Relay inferred from evidence, which change nothing until a
  person accepts them (only shown to people who can review them).
Relay-recorded facts (owners, history, knowledge, assets) come from the existing endpoints.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select

from relay.catalog import service as catalog
from relay.continuity.models import CaseScopeItem, ContinuityCase
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.github.models import GitHubRepository, GitHubWorkItem, OwnershipSuggestion
from relay.integrations.linear.models import LinearIssue, LinearProject
from relay.integrations.notion.models import NotionPage, NotionSource
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.risks.models import RiskRecord

OPEN_CASES = ("draft", "planning", "executing")
RECENT = timedelta(days=30)


class RiskSignal(BaseModel):
    key: str
    title: str
    severity: str
    status: str
    accepted_until: datetime | None


class CaseLink(BaseModel):
    id: uuid.UUID
    title: str
    case_type: str
    status: str
    emergency: bool
    recipient_planned: bool


class Evidence(BaseModel):
    source: Literal["GitHub", "Linear", "Notion"]
    label: str
    url: str
    detail: str | None


class Suggestion(BaseModel):
    source: Literal["GitHub"]
    label: str
    reason: str
    url: str


class ResponsibilityContextView(BaseModel):
    risks: list[RiskSignal]
    cases: list[CaseLink]
    evidence: list[Evidence]
    suggestions: list[Suggestion]


async def responsibility_context(
    access: WorkspaceAccess, responsibility_id: uuid.UUID
) -> ResponsibilityContextView:
    authorize(access, Permission.RESPONSIBILITY_READ)
    await catalog.get_responsibility(access, responsibility_id)  # 404 if not visible
    session, rid = access.session, responsibility_id
    readable = Permission.RESPONSIBILITY_READ

    risks = [
        RiskSignal(
            key=r.risk_key,
            title=r.title,
            severity=r.severity,
            status=r.status,
            accepted_until=r.accepted_until,
        )
        for r in await session.scalars(
            select(RiskRecord)
            .where(
                visible(access, readable, RiskRecord.tenant_id),
                RiskRecord.risk_key.like(f"%:{rid}"),
                RiskRecord.status.in_(("open", "acknowledged", "accepted")),
            )
            .order_by(RiskRecord.severity, RiskRecord.title)
        )
    ]

    cases: list[CaseLink] = []
    if role_allows(access.role, Permission.CASE_READ):
        cases = [
            CaseLink(
                id=c.id,
                title=c.title,
                case_type=c.case_type,
                status=c.status,
                emergency=c.emergency,
                recipient_planned=item.recipient_person_id is not None
                or item.recipient_team_id is not None,
            )
            for c, item in await session.execute(
                select(ContinuityCase, CaseScopeItem)
                .join(CaseScopeItem, CaseScopeItem.case_id == ContinuityCase.id)
                .where(
                    visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
                    CaseScopeItem.responsibility_id == rid,
                    ContinuityCase.status.in_(OPEN_CASES),
                )
                .order_by(ContinuityCase.emergency.desc(), ContinuityCase.updated_at.desc())
            )
        ]

    since = datetime.now(UTC) - RECENT
    evidence: list[Evidence] = []
    repos = list(
        await session.scalars(
            select(GitHubRepository)
            .where(
                visible(access, readable, GitHubRepository.tenant_id),
                GitHubRepository.responsibility_id == rid,
            )
            .order_by(GitHubRepository.full_name)
        )
    )
    recent_work = dict(
        (
            await session.execute(
                select(GitHubWorkItem.repository_id, func.count())
                .where(
                    visible(access, readable, GitHubWorkItem.tenant_id),
                    GitHubWorkItem.repository_id.in_([r.id for r in repos]),
                    GitHubWorkItem.gh_updated_at >= since,
                )
                .group_by(GitHubWorkItem.repository_id)
            )
        ).all()
    )
    for repo in repos:
        bits = [
            "archived" if repo.archived else None,
            "no longer accessible" if not repo.accessible else None,
            f"{recent_work.get(repo.id, 0)} pull requests/issues updated in 30 days",
        ]
        evidence.append(
            Evidence(
                source="GitHub",
                label=repo.full_name,
                url=repo.html_url,
                detail=" · ".join(b for b in bits if b),
            )
        )
    for project in await session.scalars(
        select(LinearProject)
        .where(
            visible(access, readable, LinearProject.tenant_id),
            LinearProject.responsibility_id == rid,
            LinearProject.removed.is_(False),
        )
        .order_by(LinearProject.name)
    ):
        open_issues = await session.scalar(
            select(func.count()).where(
                visible(access, readable, LinearIssue.tenant_id),
                LinearIssue.project_linear_id == project.linear_id,
                LinearIssue.state_type.notin_(("completed", "canceled")),
            )
        )
        evidence.append(
            Evidence(
                source="Linear",
                label=project.name,
                url=project.url,
                detail=" · ".join(filter(None, [project.state, f"{open_issues or 0} open issues"])),
            )
        )
    for source in await session.scalars(
        select(NotionSource)
        .where(
            visible(access, readable, NotionSource.tenant_id),
            NotionSource.responsibility_id == rid,
        )
        .order_by(NotionSource.title)
    ):
        pages = await session.scalar(
            select(func.count()).where(
                visible(access, readable, NotionPage.tenant_id),
                NotionPage.source_ref == source.id,
                NotionPage.status == "active",
            )
        )
        evidence.append(
            Evidence(
                source="Notion",
                label=source.title,
                url=source.url,
                detail="no longer shared with Relay"
                if source.removed
                else f"{pages or 0} pages imported into Knowledge",
            )
        )

    suggestions: list[Suggestion] = []
    if role_allows(access.role, Permission.INTEGRATION_MANAGE) and repos:
        by_repo = {r.id: r for r in repos}
        for s in await session.scalars(
            select(OwnershipSuggestion)
            .where(
                visible(access, Permission.INTEGRATION_MANAGE, OwnershipSuggestion.tenant_id),
                OwnershipSuggestion.repository_id.in_(by_repo),
                OwnershipSuggestion.status == "open",
            )
            .order_by(OwnershipSuggestion.created_at)
        ):
            suggestions.append(
                Suggestion(
                    source="GitHub",
                    label=f"{s.handle} as {s.proposed_role.replace('_', '-')}",
                    reason=s.reason,
                    url=by_repo[s.repository_id].html_url,
                )
            )
    return ResponsibilityContextView(
        risks=risks, cases=cases, evidence=evidence, suggestions=suggestions
    )
