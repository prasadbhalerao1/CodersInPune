"""Global search across the workspace, composed from each module's own visibility rules.

One endpoint, several small queries: every group applies the same `authorize`/`visible`
checks (and, for knowledge, the same managers-only filter) as the module's own list
endpoint, so search can never show something the list would hide. A group the caller has
no permission for is simply absent. Matching is case-insensitive substring on names
(PostgreSQL ILIKE) plus full-text search for knowledge content; no extra infrastructure.
"""

from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import ColumnElement, func, or_, select

from relay.catalog.knowledge import readable as knowledge_readable
from relay.catalog.models import Asset, KnowledgeItem, Responsibility
from relay.continuity.models import ContinuityCase
from relay.directory.models import Department, Person, Team
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.risks.models import RiskRecord

Kind = Literal[
    "responsibility", "person", "team", "department", "asset", "case", "knowledge", "risk"
]
PER_GROUP = 6


class SearchHit(BaseModel):
    kind: Kind
    id: str
    title: str
    detail: str | None = None
    status: str | None = None


class SearchView(BaseModel):
    query: str
    hits: list[SearchHit]


def _like(column: Any, q: str) -> ColumnElement[bool]:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    result: ColumnElement[bool] = column.ilike(f"%{escaped}%", escape="\\")
    return result


async def search(access: WorkspaceAccess, q: str) -> SearchView:
    authorize(access, Permission.WORKSPACE_READ)
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
            .limit(PER_GROUP)
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
            .limit(PER_GROUP)
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
            .limit(PER_GROUP)
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
            .limit(PER_GROUP)
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
            .limit(PER_GROUP)
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
            .limit(PER_GROUP)
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
            .limit(PER_GROUP)
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
            .limit(PER_GROUP)
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
    return SearchView(query=q, hits=hits)
