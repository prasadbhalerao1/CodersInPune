"""Insights: coverage, knowledge health, continuity operations and Continuity Debt.

Everything is computed live from the source tables, so a number always matches its
drill-down. Insights describe responsibilities and processes, never individual
productivity: people appear only as holders of coverage (e.g. a single-person dependency).

Continuity Debt is a transparent sum. Each component lists its rule, weight, count and
the items behind it; accepted risks are excluded (a person decided to live with them) and
shown separately so the score can't be gamed silently.
"""

import statistics
import uuid
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import or_, select

from relay.catalog.models import KnowledgeItem, OwnershipAssignment, Responsibility
from relay.catalog.service import active_at
from relay.continuity.models import OPEN_STATUSES, CaseTask, ContinuityCase
from relay.directory.models import Department, Person, Team
from relay.governance import service as governance
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible
from relay.risks import service as risks_service
from relay.risks.models import RiskRecord

Criticality = Literal["critical", "high", "standard", "low"]
RISK_WEIGHT = {"high": 5, "medium": 2, "low": 1}
MISSING_WEIGHT = {"critical": 3, "high": 2, "standard": 1, "low": 0}
STALE_WEIGHT = {"critical": 2, "high": 1, "standard": 0, "low": 0}
OVERDUE_TASK_WEIGHT = 1
OVERDUE_CASE_WEIGHT = 2
DRILL_LIMIT = 50


class DebtItem(BaseModel):
    label: str
    detail: str | None = None
    kind: Literal["responsibility", "case", "person"]
    id: uuid.UUID
    points: int


class DebtComponent(BaseModel):
    key: str
    label: str
    rule: str
    count: int
    points: int
    items: list[DebtItem]


class CoverageInsight(BaseModel):
    responsibilities: int
    with_primary: int
    with_backup: int
    critical: int
    critical_with_backup: int
    archived_owner_assignments: int
    single_person_dependencies: int


class KnowledgeInsight(BaseModel):
    responsibilities_with_knowledge: int
    responsibilities_missing_knowledge: int
    responsibilities_only_stale: int
    stale_items: int
    imported_needing_review: int
    review_interval_days: int


class OperationsInsight(BaseModel):
    open_cases: int
    emergency_cases: int
    overdue_tasks: int
    overdue_cases: int
    closed_last_90_days: int
    median_days_to_close: float | None
    risks_resolved_last_30_days: int
    accepted_risks: int


class KeyPerson(BaseModel):
    """Someone whose absence would leave work with nobody: the only active holder of it."""

    person_id: uuid.UUID
    name: str
    sole_critical: int  # critical or high responsibilities only they hold
    sole_total: int
    responsibilities: list[DebtItem]  # the work only they hold, most critical first


class InsightsView(BaseModel):
    generated_at: datetime
    filters: dict[str, str | None]
    departments: list[dict[str, str]]
    coverage: CoverageInsight
    knowledge: KnowledgeInsight
    operations: OperationsInsight
    continuity_debt: int
    debt: list[DebtComponent]
    # Key-person exposure (bus factor of one), ranked; teams count as shared coverage.
    key_people: list[KeyPerson] = []


def _component(key: str, label: str, rule: str, items: list[DebtItem]) -> DebtComponent:
    items = [i for i in items if i.points > 0]
    items.sort(key=lambda i: (-i.points, i.label))
    return DebtComponent(
        key=key,
        label=label,
        rule=rule,
        count=len(items),
        points=sum(i.points for i in items),
        items=items[:DRILL_LIMIT],
    )


async def _scope(
    access: WorkspaceAccess, department_id: uuid.UUID | None, now: datetime
) -> tuple[set[uuid.UUID] | None, set[uuid.UUID] | None]:
    """Responsibility and person ids held by a department's people or teams (None = all)."""
    if department_id is None:
        return None, None
    people = set(
        await access.session.scalars(
            select(Person.id).where(
                visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
                Person.department_id == department_id,
            )
        )
    )
    teams = set(
        await access.session.scalars(
            select(Team.id).where(
                visible(access, Permission.DIRECTORY_READ, Team.tenant_id),
                Team.department_id == department_id,
            )
        )
    )
    held = set(
        await access.session.scalars(
            select(OwnershipAssignment.responsibility_id).where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
                active_at(now),
                or_(
                    OwnershipAssignment.person_id.in_(people),
                    OwnershipAssignment.team_id.in_(teams),
                ),
            )
        )
    )
    return held, people


async def insights(
    access: WorkspaceAccess,
    *,
    department_id: uuid.UUID | None = None,
    criticality: Criticality | None = None,
) -> InsightsView:
    authorize(access, Permission.INSIGHTS_READ)
    session, now = access.session, datetime.now(UTC)
    in_department, department_people = await _scope(access, department_id, now)

    responsibilities = {
        r.id: r
        for r in await session.scalars(
            select(Responsibility).where(
                visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
                Responsibility.status == "active",
            )
        )
        if (in_department is None or r.id in in_department)
        and (criticality is None or r.criticality == criticality)
    }
    ids = set(responsibilities)

    # ------------------------------------------------------------ coverage
    roles: dict[uuid.UUID, set[str]] = defaultdict(set)
    holders: dict[uuid.UUID, set[uuid.UUID | None]] = defaultdict(set)
    for a in await session.scalars(
        select(OwnershipAssignment).where(
            visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
            active_at(now),
            OwnershipAssignment.responsibility_id.in_(ids),
        )
    ):
        roles[a.responsibility_id].add(a.role)
        # A team assignment is shared coverage: record it as a holder that is not one person.
        holders[a.responsibility_id].add(a.person_id if a.team_id is None else None)
    detected = await risks_service.compute_risks(access, statuses=None)

    def in_scope(risk: risks_service.RiskView) -> bool:
        if risk.responsibility is not None:
            return risk.responsibility.id in ids
        if department_people is not None and risk.person_id not in department_people:
            return False
        return any(r.id in ids for r in risk.related)

    scoped_risks = [r for r in detected if in_scope(r)]
    active_risks = [r for r in scoped_risks if r.status in risks_service.ACTIVE]
    critical = [r for r in responsibilities.values() if r.criticality == "critical"]
    coverage = CoverageInsight(
        responsibilities=len(ids),
        with_primary=sum(1 for i in ids if "primary" in roles[i]),
        with_backup=sum(1 for i in ids if "backup" in roles[i]),
        critical=len(critical),
        critical_with_backup=sum(1 for r in critical if "backup" in roles[r.id]),
        archived_owner_assignments=sum(1 for r in active_risks if r.rule == "inactive_owner"),
        single_person_dependencies=sum(
            1 for r in active_risks if r.rule == "single_person_dependency"
        ),
    )

    # ------------------------------------------------------------ knowledge
    review_days = (await governance.current(session)).knowledge_review_days
    cutoff = now - timedelta(days=review_days)
    fresh_by: dict[uuid.UUID, int] = defaultdict(int)
    stale_by: dict[uuid.UUID, int] = defaultdict(int)
    imported_needing_review = 0
    for item in await session.scalars(
        select(KnowledgeItem).where(
            visible(access, Permission.RESPONSIBILITY_READ, KnowledgeItem.tenant_id),
            KnowledgeItem.status == "active",
            KnowledgeItem.responsibility_id.in_(ids),
        )
    ):
        unreviewed_import = item.origin != "person" and item.last_reviewed_at is None
        reviewed = item.last_reviewed_at or item.created_at
        if unreviewed_import or reviewed < cutoff:
            stale_by[item.responsibility_id] += 1
            imported_needing_review += unreviewed_import
        else:
            fresh_by[item.responsibility_id] += 1
    missing = [r for r in responsibilities.values() if not fresh_by[r.id] and not stale_by[r.id]]
    only_stale = [r for r in responsibilities.values() if stale_by[r.id] and not fresh_by[r.id]]
    knowledge = KnowledgeInsight(
        responsibilities_with_knowledge=len(ids) - len(missing),
        responsibilities_missing_knowledge=len(missing),
        responsibilities_only_stale=len(only_stale),
        stale_items=sum(stale_by.values()),
        imported_needing_review=imported_needing_review,
        review_interval_days=review_days,
    )

    # ------------------------------------------------------------ operations
    cases = list(
        await session.scalars(
            select(ContinuityCase).where(
                visible(access, Permission.CASE_READ, ContinuityCase.tenant_id)
            )
        )
    )
    if department_people is not None:
        cases = [c for c in cases if c.affected_person_id in department_people]
    open_cases = [c for c in cases if c.status in OPEN_STATUSES]
    overdue_cases = [c for c in open_cases if c.ends_at is not None and c.ends_at < now]
    closed = [
        c for c in cases if c.closed_at is not None and c.closed_at >= now - timedelta(days=90)
    ]
    durations = [
        (c.closed_at - c.created_at).total_seconds() / 86400 for c in closed if c.closed_at
    ]
    open_ids = {c.id: c for c in open_cases}
    overdue_tasks = [
        t
        for t in await session.scalars(
            select(CaseTask).where(
                visible(access, Permission.CASE_READ, CaseTask.tenant_id),
                CaseTask.status == "open",
                CaseTask.due_at < now,
            )
        )
        if t.case_id in open_ids
    ]
    resolved_keys = {r.key for r in scoped_risks}
    resolved_recently = [
        key
        for key in await session.scalars(
            select(RiskRecord.risk_key).where(
                visible(access, Permission.RESPONSIBILITY_READ, RiskRecord.tenant_id),
                RiskRecord.status == "resolved",
                RiskRecord.resolved_at >= now - timedelta(days=30),
            )
        )
        if (department_id is None and criticality is None) or key in resolved_keys
    ]
    operations = OperationsInsight(
        open_cases=len(open_cases),
        emergency_cases=sum(1 for c in open_cases if c.emergency),
        overdue_tasks=len(overdue_tasks),
        overdue_cases=len(overdue_cases),
        closed_last_90_days=len(closed),
        median_days_to_close=round(statistics.median(durations), 1) if durations else None,
        risks_resolved_last_30_days=len(resolved_recently),
        accepted_risks=sum(1 for r in scoped_risks if r.status == "accepted"),
    )

    # ------------------------------------------------------------ debt
    def risk_item(r: risks_service.RiskView) -> DebtItem:
        if r.responsibility is not None:
            return DebtItem(
                label=r.responsibility.name,
                detail=r.title,
                kind="responsibility",
                id=r.responsibility.id,
                points=RISK_WEIGHT[r.severity],
            )
        return DebtItem(
            label=r.person_name or "Person",
            detail=r.title,
            kind="person",
            id=r.person_id or uuid.UUID(int=0),
            points=RISK_WEIGHT[r.severity],
        )

    def responsibility_item(r: Responsibility, weights: dict[str, int], detail: str) -> DebtItem:
        return DebtItem(
            label=r.name,
            detail=detail,
            kind="responsibility",
            id=r.id,
            points=weights[r.criticality],
        )

    debt = [
        _component(
            "ownership_risks",
            "Open ownership risks",
            "Each open or acknowledged risk: high 5, medium 2, low 1. Accepted risks don't count.",
            [risk_item(r) for r in active_risks],
        ),
        _component(
            "missing_knowledge",
            "Responsibilities without knowledge",
            "Each by criticality: critical 3, high 2, standard 1, low 0.",
            [
                responsibility_item(
                    r, MISSING_WEIGHT, f"{r.criticality.capitalize()}, no knowledge"
                )
                for r in missing
            ],
        ),
        _component(
            "stale_knowledge",
            "Knowledge overdue for review",
            f"Each responsibility whose knowledge is all older than {review_days} days or "
            "unreviewed imports: critical 2, high 1.",
            [
                responsibility_item(r, STALE_WEIGHT, f"{stale_by[r.id]} items need review")
                for r in only_stale
            ],
        ),
        _component(
            "overdue_work",
            "Overdue continuity work",
            f"Each overdue open task {OVERDUE_TASK_WEIGHT}; each case past its end date "
            f"{OVERDUE_CASE_WEIGHT}.",
            [
                DebtItem(
                    label=c.title,
                    detail="Past its end date",
                    kind="case",
                    id=c.id,
                    points=OVERDUE_CASE_WEIGHT,
                )
                for c in overdue_cases
            ]
            + [
                DebtItem(
                    label=open_ids[t.case_id].title,
                    detail=f"Task overdue: {t.title}",
                    kind="case",
                    id=t.case_id,
                    points=OVERDUE_TASK_WEIGHT,
                )
                for t in overdue_tasks
            ],
        ),
    ]
    departments = [
        {"id": str(d.id), "name": d.name}
        for d in await session.scalars(
            select(Department)
            .where(
                visible(access, Permission.DIRECTORY_READ, Department.tenant_id),
                Department.status == "active",
            )
            .order_by(Department.name)
        )
    ]
    return InsightsView(
        generated_at=now,
        filters={
            "department_id": str(department_id) if department_id else None,
            "criticality": criticality,
        },
        departments=departments,
        coverage=coverage,
        knowledge=knowledge,
        operations=operations,
        continuity_debt=sum(c.points for c in debt),
        debt=debt,
        key_people=await _key_people(access, responsibilities, holders),
    )


SEVERE = ("critical", "high")
_RANK = {"critical": 0, "high": 1, "standard": 2, "low": 3}


async def _key_people(
    access: WorkspaceAccess,
    responsibilities: dict[uuid.UUID, Responsibility],
    holders: dict[uuid.UUID, set[uuid.UUID | None]],
    limit: int = 5,
) -> list[KeyPerson]:
    """People who are the only active holder of a responsibility, most exposed first."""
    sole: dict[uuid.UUID, list[Responsibility]] = defaultdict(list)
    for rid, held in holders.items():
        if len(held) == 1 and (person := next(iter(held))) is not None:
            sole[person].append(responsibilities[rid])
    if not sole:
        return []
    names = dict(
        (
            await access.session.execute(
                select(Person.id, Person.display_name).where(
                    visible(access, Permission.RESPONSIBILITY_READ, Person.tenant_id),
                    Person.id.in_(sole),
                )
            )
        ).all()
    )
    people = [
        KeyPerson(
            person_id=pid,
            name=names.get(pid, "Unknown person"),
            sole_critical=sum(1 for r in held if r.criticality in SEVERE),
            sole_total=len(held),
            responsibilities=[
                DebtItem(
                    label=r.name,
                    detail=r.criticality,
                    kind="responsibility",
                    id=r.id,
                    points=0,
                )
                for r in sorted(held, key=lambda r: (_RANK[r.criticality], r.name))
            ],
        )
        for pid, held in sole.items()
    ]
    people.sort(key=lambda k: (-k.sole_critical, -k.sole_total, k.name))
    return people[:limit]
