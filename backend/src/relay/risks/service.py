"""Deterministic continuity risks computed from the live catalogue (no scores, no AI).

Rules (severity in brackets; each risk explains itself in plain language):
- no_primary_owner: no current primary [critical/high: high, standard: medium, low: low]
- no_backup: no current backup [critical: high, high: medium, otherwise low]
- insufficient_critical_coverage: critical, covered by fewer than 2 owners [high]
- inactive_owner: a current owner is an archived person/team [critical/high: high, else medium]
- single_person_dependency: one person solely owns >= 2 responsibilities
  [high if any is critical/high, else medium]

Risks are recomputed on every read, so they resolve as soon as the catalogue is fixed.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select

from relay.catalog.models import OwnershipAssignment, OwnershipAssignmentChange, Responsibility
from relay.catalog.service import active_at
from relay.directory.models import Person, Team
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible

Severity = Literal["high", "medium", "low"]
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


class RiskSubject(BaseModel):
    id: uuid.UUID
    name: str
    criticality: str


class RiskView(BaseModel):
    key: str
    rule: str
    severity: Severity
    title: str
    explanation: str
    recommendation: str
    responsibility: RiskSubject | None = None
    person_id: uuid.UUID | None = None
    person_name: str | None = None
    related: list[RiskSubject] = []


class RecentChange(BaseModel):
    changed_at: datetime
    change_type: str
    role: str
    assignee_name: str
    responsibility_id: uuid.UUID
    responsibility_name: str
    reason: str | None


class Overview(BaseModel):
    active_responsibilities: int
    without_primary_owner: int
    critical_without_backup: int
    open_risks: int
    risks_by_severity: dict[str, int]
    top_risks: list[RiskView]
    recent_changes: list[RecentChange]


async def compute_risks(access: WorkspaceAccess) -> list[RiskView]:
    authorize(access, Permission.RESPONSIBILITY_READ)
    session = access.session
    now = datetime.now(UTC)
    responsibilities = list(
        await session.scalars(
            select(Responsibility).where(
                visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
                Responsibility.status == "active",
            )
        )
    )
    assignments = list(
        await session.scalars(
            select(OwnershipAssignment).where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
                active_at(now),
            )
        )
    )
    people = {
        p.id: p
        for p in await session.scalars(
            select(Person).where(visible(access, Permission.DIRECTORY_READ, Person.tenant_id))
        )
    }
    teams = {
        t.id: t
        for t in await session.scalars(
            select(Team).where(visible(access, Permission.DIRECTORY_READ, Team.tenant_id))
        )
    }

    by_responsibility: dict[uuid.UUID, list[OwnershipAssignment]] = defaultdict(list)
    for a in assignments:
        by_responsibility[a.responsibility_id].append(a)

    risks: list[RiskView] = []
    sole_owner_of: dict[uuid.UUID, list[Responsibility]] = defaultdict(list)

    for r in responsibilities:
        subject = RiskSubject(id=r.id, name=r.name, criticality=r.criticality)
        mine = by_responsibility.get(r.id, [])
        roles = {a.role for a in mine}
        holders = {a.person_id or a.team_id for a in mine}

        if "primary" not in roles:
            risks.append(
                RiskView(
                    key=f"no_primary_owner:{r.id}",
                    rule="no_primary_owner",
                    severity="high"
                    if r.criticality in ("critical", "high")
                    else "medium"
                    if r.criticality == "standard"
                    else "low",
                    title="No primary owner",
                    explanation=f"Nobody is currently accountable for “{r.name}”.",
                    recommendation="Assign a primary owner.",
                    responsibility=subject,
                )
            )
        if "backup" not in roles:
            risks.append(
                RiskView(
                    key=f"no_backup:{r.id}",
                    rule="no_backup",
                    severity="high"
                    if r.criticality == "critical"
                    else "medium"
                    if r.criticality == "high"
                    else "low",
                    title="No backup",
                    explanation=f"If the current owner of “{r.name}” is unavailable, "
                    "nobody is designated to cover.",
                    recommendation="Assign a backup owner.",
                    responsibility=subject,
                )
            )
        if r.criticality == "critical" and len(holders) < 2 and "primary" in roles:
            risks.append(
                RiskView(
                    key=f"insufficient_critical_coverage:{r.id}",
                    rule="insufficient_critical_coverage",
                    severity="high",
                    title="Critical responsibility with a single owner",
                    explanation=f"“{r.name}” is critical but only one person or team covers it.",
                    recommendation="Add a backup or co-owner.",
                    responsibility=subject,
                )
            )
        for a in mine:
            holder = people.get(a.person_id) if a.person_id else teams.get(a.team_id)  # type: ignore[arg-type]
            if holder is not None and holder.status == "archived":
                name = holder.display_name if isinstance(holder, Person) else holder.name
                risks.append(
                    RiskView(
                        key=f"inactive_owner:{a.id}",
                        rule="inactive_owner",
                        severity="high" if r.criticality in ("critical", "high") else "medium",
                        title="Owner is archived",
                        explanation=f"{name} is archived but still holds the "
                        f"{a.role.replace('_', '-')} role on “{r.name}”.",
                        recommendation="End the assignment and assign an active owner.",
                        responsibility=subject,
                    )
                )
        if len(holders) == 1 and mine[0].person_id is not None:
            sole_owner_of[mine[0].person_id].append(r)

    for person_id, owned in sole_owner_of.items():
        if len(owned) < 2:
            continue
        person = people.get(person_id)
        name = person.display_name if person else "A person"
        risks.append(
            RiskView(
                key=f"single_person_dependency:{person_id}",
                rule="single_person_dependency",
                severity="high"
                if any(r.criticality in ("critical", "high") for r in owned)
                else "medium",
                title="Single-person dependency",
                explanation=f"{name} is the only owner of {len(owned)} responsibilities; "
                "their absence leaves all of them uncovered.",
                recommendation="Spread coverage by adding backups to these responsibilities.",
                person_id=person_id,
                person_name=name,
                related=[
                    RiskSubject(id=r.id, name=r.name, criticality=r.criticality) for r in owned
                ],
            )
        )

    risks.sort(key=lambda x: (_SEVERITY_ORDER[x.severity], x.title, x.key))
    return risks


async def overview(access: WorkspaceAccess) -> Overview:
    risks = await compute_risks(access)
    session = access.session
    active = list(
        await session.scalars(
            select(Responsibility.id).where(
                visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
                Responsibility.status == "active",
            )
        )
    )
    rows = (
        await session.execute(
            select(OwnershipAssignmentChange, OwnershipAssignment, Responsibility.name)
            .join(
                OwnershipAssignment,
                OwnershipAssignment.id == OwnershipAssignmentChange.assignment_id,
            )
            .join(Responsibility, Responsibility.id == OwnershipAssignmentChange.responsibility_id)
            .where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignmentChange.tenant_id)
            )
            .order_by(
                OwnershipAssignmentChange.changed_at.desc(), OwnershipAssignmentChange.id.desc()
            )
            .limit(8)
        )
    ).all()
    names: dict[uuid.UUID, str] = {}
    person_ids = {a.person_id for _, a, _ in rows if a.person_id}
    team_ids = {a.team_id for _, a, _ in rows if a.team_id}
    if person_ids:
        names |= dict(
            (
                await session.execute(
                    select(Person.id, Person.display_name).where(Person.id.in_(person_ids))
                )
            )
            .tuples()
            .all()
        )
    if team_ids:
        names |= dict(
            (await session.execute(select(Team.id, Team.name).where(Team.id.in_(team_ids))))
            .tuples()
            .all()
        )
    by_severity = {s: sum(1 for r in risks if r.severity == s) for s in ("high", "medium", "low")}
    return Overview(
        active_responsibilities=len(active),
        without_primary_owner=sum(1 for r in risks if r.rule == "no_primary_owner"),
        critical_without_backup=sum(
            1
            for r in risks
            if r.rule == "no_backup"
            and r.responsibility
            and r.responsibility.criticality == "critical"
        ),
        open_risks=len(risks),
        risks_by_severity=by_severity,
        top_risks=risks[:5],
        recent_changes=[
            RecentChange(
                changed_at=c.changed_at,
                change_type=c.change_type,
                role=a.role,
                assignee_name=names.get(a.person_id or a.team_id, "Unknown"),  # type: ignore[arg-type]
                responsibility_id=c.responsibility_id,
                responsibility_name=name,
                reason=c.reason,
            )
            for c, a, name in rows
        ],
    )
