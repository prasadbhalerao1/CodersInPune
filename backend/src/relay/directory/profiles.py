"""Detail pages for people, teams and departments: organisational and continuity context.

Shows relationships (teams, department, members), current and scheduled ownership roles,
open risks on the responsibilities involved, and active cases. Deliberately no activity
counts, completion rates or rankings: this is continuity context, not performance data.
Every query uses the module's own visibility rules; cases appear only for case readers.
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, or_, select

from relay.catalog.knowledge import readable as knowledge_readable
from relay.catalog.models import KnowledgeItem, OwnershipAssignment, Responsibility
from relay.continuity.models import OPEN_STATUSES, CaseScopeItem, CaseTask, ContinuityCase
from relay.directory.models import Department, DirectoryHistory, Person, Team, TeamMember
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.github.models import GitHubIdentity
from relay.integrations.linear.models import LinearIdentity
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.risks.models import RiskRecord
from relay.shared.errors import ApiError

OPEN_CASES = OPEN_STATUSES


class Ref(BaseModel):
    id: uuid.UUID
    name: str
    detail: str | None = None


class RoleView(BaseModel):
    responsibility_id: uuid.UUID
    responsibility_name: str
    criticality: str
    role: str
    holder: str  # the person or team holding the role
    valid_from: datetime
    valid_to: datetime | None
    state: str  # current | scheduled


class RiskRef(BaseModel):
    key: str
    title: str
    severity: str
    status: str
    subject: str | None


class CaseRef(BaseModel):
    id: uuid.UUID
    title: str
    case_type: str
    status: str
    emergency: bool
    relation: str


class TaskRef(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    case_title: str
    title: str
    due_at: datetime | None


class HistoryRef(BaseModel):
    change: str
    unit: str
    changed_at: datetime


class CoverageView(BaseModel):
    responsibilities: int
    critical: int
    without_backup: int
    single_holder: int


class IdentityRef(BaseModel):
    provider: str
    handle: str


class ProfileView(BaseModel):
    kind: str
    id: uuid.UUID
    name: str
    status: str
    description: str | None
    email: str | None = None
    title: str | None = None
    department: Ref | None = None
    teams: list[Ref] = []
    members: list[Ref] = []
    people: list[Ref] = []
    roles: list[RoleView] = []
    risks: list[RiskRef] = []
    cases: list[CaseRef] = []
    identities: list[IdentityRef] = []
    continuity_debt: int | None = None
    reports_to: Ref | None = None
    direct_reports: list[Ref] = []
    # Open case tasks assigned to this person's member account, and knowledge they wrote.
    tasks: list[TaskRef] = []
    knowledge: list[Ref] = []
    history: list[HistoryRef] = []
    # Teams: how well what the team holds is covered. Departments: risks by severity.
    coverage: CoverageView | None = None
    risk_breakdown: dict[str, int] = {}


async def _roles(
    access: WorkspaceAccess, *, people: set[uuid.UUID], teams: set[uuid.UUID]
) -> list[RoleView]:
    if not people and not teams:
        return []
    now = datetime.now(UTC)
    names = {
        **{
            p.id: p.display_name
            for p in await access.session.scalars(
                select(Person).where(visible(access, Permission.DIRECTORY_READ, Person.tenant_id))
            )
        },
        **{
            t.id: t.name
            for t in await access.session.scalars(
                select(Team).where(visible(access, Permission.DIRECTORY_READ, Team.tenant_id))
            )
        },
    }
    rows = await access.session.execute(
        select(OwnershipAssignment, Responsibility)
        .join(Responsibility, Responsibility.id == OwnershipAssignment.responsibility_id)
        .where(
            visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
            Responsibility.status == "active",
            or_(OwnershipAssignment.valid_to.is_(None), OwnershipAssignment.valid_to > now),
            or_(OwnershipAssignment.person_id.in_(people), OwnershipAssignment.team_id.in_(teams)),
        )
        .order_by(Responsibility.name, OwnershipAssignment.valid_from)
    )
    order = {"primary": 0, "co_owner": 1, "temporary": 2, "backup": 3}
    views = [
        RoleView(
            responsibility_id=r.id,
            responsibility_name=r.name,
            criticality=r.criticality,
            role=a.role,
            holder=names.get(a.person_id or a.team_id, "Unknown"),  # type: ignore[arg-type]
            valid_from=a.valid_from,
            valid_to=a.valid_to,
            state="current" if a.valid_from <= now else "scheduled",
        )
        for a, r in rows
    ]
    return sorted(views, key=lambda v: (v.state, order.get(v.role, 9), v.responsibility_name))


async def _risks(
    access: WorkspaceAccess, responsibilities: set[uuid.UUID], people: set[uuid.UUID]
) -> list[RiskRef]:
    keys = [f"%:{r}" for r in responsibilities] + [f"%:{p}" for p in people]
    if not keys:
        return []
    severity = {"high": 0, "medium": 1, "low": 2}
    risks = [
        RiskRef(
            key=r.risk_key, title=r.title, severity=r.severity, status=r.status, subject=r.subject
        )
        for r in await access.session.scalars(
            select(RiskRecord).where(
                visible(access, Permission.RESPONSIBILITY_READ, RiskRecord.tenant_id),
                RiskRecord.status.in_(("open", "acknowledged", "accepted")),
                or_(*[RiskRecord.risk_key.like(k) for k in keys]),
            )
        )
    ]
    return sorted(risks, key=lambda r: (severity.get(r.severity, 9), r.title))


async def _cases(
    access: WorkspaceAccess, *, people: set[uuid.UUID], responsibilities: set[uuid.UUID]
) -> list[CaseRef]:
    if not role_allows(access.role, Permission.CASE_READ):
        return []
    cases: dict[uuid.UUID, CaseRef] = {}
    mine = visible(access, Permission.CASE_READ, ContinuityCase.tenant_id)
    for c in await access.session.scalars(
        select(ContinuityCase).where(
            mine,
            ContinuityCase.status.in_(OPEN_CASES),
            ContinuityCase.affected_person_id.in_(people),
        )
    ):
        cases[c.id] = CaseRef(
            id=c.id,
            title=c.title,
            case_type=c.case_type,
            status=c.status,
            emergency=c.emergency,
            relation="Affected person",
        )
    rows = await access.session.execute(
        select(ContinuityCase, CaseScopeItem)
        .join(CaseScopeItem, CaseScopeItem.case_id == ContinuityCase.id)
        .where(
            mine,
            ContinuityCase.status.in_(OPEN_CASES),
            or_(
                CaseScopeItem.recipient_person_id.in_(people),
                CaseScopeItem.responsibility_id.in_(responsibilities),
            ),
        )
    )
    for c, item in rows:
        relation = (
            "Recipient" if item.recipient_person_id in people else "Covers a responsibility here"
        )
        cases.setdefault(
            c.id,
            CaseRef(
                id=c.id,
                title=c.title,
                case_type=c.case_type,
                status=c.status,
                emergency=c.emergency,
                relation=relation,
            ),
        )
    return sorted(cases.values(), key=lambda c: (not c.emergency, c.title))


async def _department_ref(access: WorkspaceAccess, department_id: uuid.UUID | None) -> Ref | None:
    if department_id is None:
        return None
    d = await access.session.scalar(
        select(Department).where(
            Department.id == department_id,
            visible(access, Permission.DIRECTORY_READ, Department.tenant_id),
        )
    )
    return Ref(id=d.id, name=d.name) if d else None


def _held(roles: list[RoleView]) -> set[uuid.UUID]:
    return {r.responsibility_id for r in roles}


async def _get(access: WorkspaceAccess, model: Any, item_id: uuid.UUID) -> Any:
    authorize(access, Permission.DIRECTORY_READ)
    row = await access.session.scalar(
        select(model).where(
            model.id == item_id, visible(access, Permission.DIRECTORY_READ, model.tenant_id)
        )
    )
    if row is None:
        raise ApiError(404, "not_found", "Not found.")
    return row


async def person_profile(access: WorkspaceAccess, person_id: uuid.UUID) -> ProfileView:
    person: Person = await _get(access, Person, person_id)
    teams = list(
        await access.session.execute(
            select(Team.id, Team.name)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(
                visible(access, Permission.DIRECTORY_READ, TeamMember.tenant_id),
                TeamMember.person_id == person.id,
            )
            .order_by(Team.name)
        )
    )
    roles = await _roles(access, people={person.id}, teams=set())
    identities: list[IdentityRef] = []
    if role_allows(access.role, Permission.INTEGRATION_MANAGE):
        identities += [
            IdentityRef(provider="GitHub", handle=i.login)
            for i in await access.session.scalars(
                select(GitHubIdentity).where(GitHubIdentity.person_id == person.id)
            )
        ]
        identities += [
            IdentityRef(provider="Linear", handle=i.name)
            for i in await access.session.scalars(
                select(LinearIdentity).where(LinearIdentity.person_id == person.id)
            )
        ]
    if person.github_login and not any(i.provider == "GitHub" for i in identities):
        identities.append(IdentityRef(provider="GitHub", handle=person.github_login))
    manager = (
        await access.session.get(Person, person.manager_person_id)
        if (person.manager_person_id)
        else None
    )
    reports = await access.session.scalars(
        select(Person)
        .where(
            visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
            Person.manager_person_id == person.id,
            Person.status == "active",
        )
        .order_by(Person.display_name)
    )
    return ProfileView(
        kind="person",
        id=person.id,
        name=person.display_name,
        status=person.status,
        description=None,
        email=person.email,
        title=person.title,
        department=await _department_ref(access, person.department_id),
        teams=[Ref(id=t_id, name=name) for t_id, name in teams],
        roles=roles,
        risks=await _risks(access, _held(roles), {person.id}),
        cases=await _cases(access, people={person.id}, responsibilities=set()),
        identities=identities,
        reports_to=Ref(id=manager.id, name=manager.display_name) if manager else None,
        direct_reports=[Ref(id=r.id, name=r.display_name, detail=r.title) for r in reports],
        tasks=await _tasks(access, person),
        knowledge=await _knowledge(access, person),
        history=await _history(access, person.id),
    )


async def team_profile(access: WorkspaceAccess, team_id: uuid.UUID) -> ProfileView:
    team: Team = await _get(access, Team, team_id)
    members = list(
        await access.session.execute(
            select(Person.id, Person.display_name, Person.title)
            .join(TeamMember, TeamMember.person_id == Person.id)
            .where(
                visible(access, Permission.DIRECTORY_READ, TeamMember.tenant_id),
                TeamMember.team_id == team.id,
            )
            .order_by(Person.display_name)
        )
    )
    member_ids = {m[0] for m in members}
    roles = await _roles(access, people=set(), teams={team.id})
    return ProfileView(
        kind="team",
        id=team.id,
        name=team.name,
        status=team.status,
        description=team.description,
        department=await _department_ref(access, team.department_id),
        members=[Ref(id=m_id, name=name, detail=title) for m_id, name, title in members],
        roles=roles,
        risks=await _risks(access, _held(roles), set()),
        cases=await _cases(access, people=member_ids, responsibilities=_held(roles)),
        coverage=await _coverage(access, _held(roles)),
    )


async def department_profile(access: WorkspaceAccess, department_id: uuid.UUID) -> ProfileView:
    department: Department = await _get(access, Department, department_id)
    people = list(
        await access.session.scalars(
            select(Person)
            .where(
                visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
                Person.department_id == department.id,
                Person.status == "active",
            )
            .order_by(Person.display_name)
        )
    )
    teams = list(
        await access.session.scalars(
            select(Team)
            .where(
                visible(access, Permission.DIRECTORY_READ, Team.tenant_id),
                Team.department_id == department.id,
                Team.status == "active",
            )
            .order_by(Team.name)
        )
    )
    people_ids, team_ids = {p.id for p in people}, {t.id for t in teams}
    roles = await _roles(access, people=people_ids, teams=team_ids)
    debt = None
    if role_allows(access.role, Permission.INSIGHTS_READ):
        from relay.insights import service as insights  # local: insights imports directory

        debt = (await insights.insights(access, department_id=department.id)).continuity_debt
    return ProfileView(
        kind="department",
        id=department.id,
        name=department.name,
        status=department.status,
        description=department.description,
        teams=[Ref(id=t.id, name=t.name) for t in teams],
        people=[Ref(id=p.id, name=p.display_name, detail=p.title) for p in people],
        roles=roles,
        risks=await _risks(access, _held(roles), people_ids),
        cases=await _cases(access, people=people_ids, responsibilities=_held(roles)),
        continuity_debt=debt,
        coverage=await _coverage(access, _held(roles)),
        risk_breakdown=_breakdown(await _risks(access, _held(roles), people_ids)),
    )


def _breakdown(risks: list[RiskRef]) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0}
    for r in risks:
        counts[r.severity] = counts.get(r.severity, 0) + 1
    return counts


async def _member_user(access: WorkspaceAccess, person: Person) -> uuid.UUID | None:
    """The member account for a directory person (matched by email)."""
    if not person.email:
        return None
    return await access.session.scalar(
        select(Membership.user_id).where(
            func.lower(Membership.email) == person.email.lower(), Membership.status == "active"
        )
    )


async def _tasks(access: WorkspaceAccess, person: Person) -> list[TaskRef]:
    if not role_allows(access.role, Permission.CASE_READ):
        return []
    user_id = await _member_user(access, person)
    if user_id is None:
        return []
    rows = await access.session.execute(
        select(CaseTask, ContinuityCase.title)
        .join(ContinuityCase, ContinuityCase.id == CaseTask.case_id)
        .where(
            visible(access, Permission.CASE_READ, CaseTask.tenant_id),
            CaseTask.assignee_user_id == user_id,
            CaseTask.status == "open",
            ContinuityCase.status.in_(OPEN_CASES),
        )
        .order_by(CaseTask.due_at.asc().nulls_last())
        .limit(20)
    )
    return [
        TaskRef(id=t.id, case_id=t.case_id, case_title=title, title=t.title, due_at=t.due_at)
        for t, title in rows
    ]


async def _knowledge(access: WorkspaceAccess, person: Person) -> list[Ref]:
    user_id = await _member_user(access, person)
    if user_id is None:
        return []
    rows = await access.session.scalars(
        select(KnowledgeItem)
        .join(Responsibility, Responsibility.id == KnowledgeItem.responsibility_id)
        .where(
            knowledge_readable(access),
            KnowledgeItem.author_user_id == user_id,
            KnowledgeItem.status == "active",
        )
        .order_by(KnowledgeItem.updated_at.desc())
        .limit(20)
    )
    return [Ref(id=k.id, name=k.title, detail=k.kind.replace("_", " ")) for k in rows]


async def _history(access: WorkspaceAccess, person_id: uuid.UUID) -> list[HistoryRef]:
    teams = dict((await access.session.execute(select(Team.id, Team.name))).all())
    departments = dict((await access.session.execute(select(Department.id, Department.name))).all())
    rows = await access.session.scalars(
        select(DirectoryHistory)
        .where(
            visible(access, Permission.DIRECTORY_READ, DirectoryHistory.tenant_id),
            DirectoryHistory.person_id == person_id,
        )
        .order_by(DirectoryHistory.changed_at.desc())
        .limit(30)
    )
    return [
        HistoryRef(
            change=h.change,
            unit=teams.get(h.team_id, "team")
            if h.team_id
            else departments.get(h.department_id, "department"),  # type: ignore[arg-type]
            changed_at=h.changed_at,
        )
        for h in rows
    ]


async def _coverage(access: WorkspaceAccess, held: set[uuid.UUID]) -> CoverageView:
    if not held:
        return CoverageView(responsibilities=0, critical=0, without_backup=0, single_holder=0)
    now = datetime.now(UTC)
    assignments = list(
        await access.session.scalars(
            select(OwnershipAssignment).where(
                OwnershipAssignment.responsibility_id.in_(held),
                OwnershipAssignment.valid_from <= now,
                or_(OwnershipAssignment.valid_to.is_(None), OwnershipAssignment.valid_to > now),
            )
        )
    )
    criticality = dict(
        (
            await access.session.execute(
                select(Responsibility.id, Responsibility.criticality).where(
                    Responsibility.id.in_(held), Responsibility.status == "active"
                )
            )
        ).all()
    )
    by: dict[uuid.UUID, list[OwnershipAssignment]] = {}
    for a in assignments:
        by.setdefault(a.responsibility_id, []).append(a)
    visible_ids = [r for r in held if r in criticality]
    return CoverageView(
        responsibilities=len(visible_ids),
        critical=sum(1 for r in visible_ids if criticality[r] == "critical"),
        without_backup=sum(
            1 for r in visible_ids if not any(a.role == "backup" for a in by.get(r, []))
        ),
        single_holder=sum(
            1 for r in visible_ids if len({a.person_id or a.team_id for a in by.get(r, [])}) <= 1
        ),
    )
