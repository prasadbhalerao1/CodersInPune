"""People, teams and departments directory: list, create, update, archive."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from relay.audit import service as audit
from relay.directory.models import Department, DirectoryHistory, Person, Team, TeamMember
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible
from relay.shared import pagination
from relay.shared.api_types import Email, LongText, Name, ShortText, StrictInput, blank_to_none
from relay.shared.errors import ApiError

Status = Literal["active", "archived"]


GitHubLogin = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9-]{1,39}$")
]
GitHubTeamSlug = Annotated[
    str,
    StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$"),
]


class DepartmentIn(StrictInput):
    name: Name
    description: LongText | None = None


class DepartmentUpdate(StrictInput):
    name: Name | None = None
    description: LongText | None = None
    status: Status | None = None


class DepartmentView(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    status: str
    people_count: int
    team_count: int
    created_at: datetime


class PersonIn(StrictInput):
    display_name: Name
    email: Email | None = None
    title: ShortText | None = None
    github_login: GitHubLogin | None = None
    department_id: uuid.UUID | None = None
    manager_person_id: uuid.UUID | None = None


class PersonUpdate(StrictInput):
    display_name: Name | None = None
    email: Email | None = None
    title: ShortText | None = None
    github_login: GitHubLogin | None = None
    department_id: uuid.UUID | None = None
    status: Status | None = None
    manager_person_id: uuid.UUID | None = None


class PersonView(BaseModel):
    id: uuid.UUID
    display_name: str
    email: str | None
    title: str | None
    github_login: str | None
    department_id: uuid.UUID | None
    department_name: str | None
    status: str
    created_at: datetime
    manager_person_id: uuid.UUID | None = None


class TeamIn(StrictInput):
    name: Name
    description: LongText | None = None
    github_slug: GitHubTeamSlug | None = None
    department_id: uuid.UUID | None = None


class TeamUpdate(StrictInput):
    name: Name | None = None
    description: LongText | None = None
    github_slug: GitHubTeamSlug | None = None
    department_id: uuid.UUID | None = None
    status: Status | None = None


class TeamMemberView(BaseModel):
    person_id: uuid.UUID
    display_name: str


class TeamView(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    github_slug: str | None
    department_id: uuid.UUID | None
    department_name: str | None
    status: str
    created_at: datetime
    members: list[TeamMemberView] = []


def _person_view(p: Person, departments: dict[uuid.UUID, str]) -> PersonView:
    return PersonView(
        id=p.id,
        display_name=p.display_name,
        email=p.email,
        title=p.title,
        github_login=p.github_login,
        department_id=p.department_id,
        department_name=departments.get(p.department_id) if p.department_id else None,
        status=p.status,
        created_at=p.created_at,
        manager_person_id=p.manager_person_id,
    )


def history(
    access: WorkspaceAccess,
    person_id: uuid.UUID,
    change: str,
    *,
    team_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
) -> None:
    access.session.add(
        DirectoryHistory(
            tenant_id=access.tenant_id,
            person_id=person_id,
            team_id=team_id,
            department_id=department_id,
            change=change,
            actor_user_id=access.user_id,
        )
    )


async def _require_manager(
    access: WorkspaceAccess, person_id: uuid.UUID | None, manager_id: uuid.UUID | None
) -> None:
    """The manager exists, and the reporting line doesn't loop back to the person."""
    if manager_id is None:
        return
    seen: set[uuid.UUID] = set()
    current: uuid.UUID | None = manager_id
    while current is not None:
        if current == person_id or current in seen:
            raise ApiError(422, "reporting_loop", "That would make a reporting loop.")
        seen.add(current)
        row = await access.session.get(Person, current)
        if row is None:
            raise ApiError(422, "person_not_found", "The manager must be a person in Relay.")
        current = row.manager_person_id


def _team_view(t: Team, departments: dict[uuid.UUID, str]) -> TeamView:
    return TeamView(
        id=t.id,
        name=t.name,
        description=t.description,
        github_slug=t.github_slug,
        department_id=t.department_id,
        department_name=departments.get(t.department_id) if t.department_id else None,
        status=t.status,
        created_at=t.created_at,
    )


def _pattern(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def department_names(access: WorkspaceAccess) -> dict[uuid.UUID, str]:
    rows = await access.session.execute(
        select(Department.id, Department.name).where(
            visible(access, Permission.DIRECTORY_READ, Department.tenant_id)
        )
    )
    return {key: value for key, value in rows}


async def _require_department(access: WorkspaceAccess, department_id: uuid.UUID | None) -> None:
    if department_id is None:
        return
    status = await access.session.scalar(
        select(Department.status).where(
            Department.id == department_id,
            visible(access, Permission.DIRECTORY_READ, Department.tenant_id),
        )
    )
    if status is None:
        raise ApiError(422, "department_not_found", "That department does not exist.")
    if status != "active":
        raise ApiError(422, "department_archived", "Archived departments cannot be assigned.")


# ---------------------------------------------------------------- people


async def list_people(
    access: WorkspaceAccess,
    *,
    q: str | None = None,
    include_archived: bool = False,
    department_id: uuid.UUID | None = None,
    after: str | None = None,
    limit: int = pagination.MAX_PAGE,
) -> tuple[list[PersonView], str | None]:
    stmt = select(Person).where(visible(access, Permission.DIRECTORY_READ, Person.tenant_id))
    keyset = pagination.after_key((Person.display_name, Person.id), after, (str, uuid.UUID))
    if keyset is not None:
        stmt = stmt.where(keyset)
    if department_id:
        stmt = stmt.where(Person.department_id == department_id)
    if not include_archived:
        stmt = stmt.where(Person.status == "active")
    if q:
        stmt = stmt.where(
            or_(Person.display_name.ilike(_pattern(q)), Person.email.ilike(_pattern(q)))
        )
    rows, next_cursor = pagination.split(
        list(
            await access.session.scalars(
                stmt.order_by(Person.display_name, Person.id).limit(limit + 1)
            )
        ),
        limit,
        lambda p: (p.display_name, p.id),
    )
    departments = await department_names(access)
    return [_person_view(p, departments) for p in rows], next_cursor


async def create_person(access: WorkspaceAccess, data: PersonIn) -> PersonView:
    authorize(access, Permission.DIRECTORY_MANAGE)
    await _require_department(access, data.department_id)
    await _require_manager(access, None, data.manager_person_id)
    person = Person(
        tenant_id=access.tenant_id,
        department_id=data.department_id,
        manager_person_id=data.manager_person_id,
        display_name=data.display_name,
        email=blank_to_none(data.email),
        title=blank_to_none(data.title),
        github_login=(data.github_login or "").lower() or None,
    )
    access.session.add(person)
    await access.session.flush()
    await access.session.refresh(person)
    if person.department_id:
        history(access, person.id, "joined_department", department_id=person.department_id)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="person.created",
        actor_user_id=access.user_id,
        target_type="person",
        target_id=person.id,
    )
    return _person_view(person, await department_names(access))


async def update_person(
    access: WorkspaceAccess, person_id: uuid.UUID, data: PersonUpdate
) -> PersonView:
    authorize(access, Permission.DIRECTORY_MANAGE)
    person = await access.session.get(Person, person_id, with_for_update=True)
    if person is None:
        raise ApiError(404, "person_not_found", "Person not found.")
    changed = data.model_dump(exclude_unset=True)
    await _require_department(access, changed.get("department_id"))
    if "manager_person_id" in changed:
        await _require_manager(access, person.id, changed["manager_person_id"])
    if "department_id" in changed and changed["department_id"] != person.department_id:
        if person.department_id:
            history(access, person.id, "left_department", department_id=person.department_id)
        if changed["department_id"]:
            history(access, person.id, "joined_department", department_id=changed["department_id"])
    for field, value in changed.items():
        if field == "github_login":
            value = value.lower() if value else None
        setattr(person, field, blank_to_none(value) if field in {"email", "title"} else value)
    person.updated_at = func.now()
    await access.session.flush()
    await access.session.refresh(person)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="person.updated",
        actor_user_id=access.user_id,
        target_type="person",
        target_id=person.id,
        details={"fields": ",".join(sorted(changed))},
    )
    return _person_view(person, await department_names(access))


# ---------------------------------------------------------------- teams


async def list_teams(
    access: WorkspaceAccess,
    *,
    q: str | None = None,
    include_archived: bool = False,
    department_id: uuid.UUID | None = None,
) -> list[TeamView]:
    stmt = select(Team).where(visible(access, Permission.DIRECTORY_READ, Team.tenant_id))
    if department_id:
        stmt = stmt.where(Team.department_id == department_id)
    if not include_archived:
        stmt = stmt.where(Team.status == "active")
    if q:
        stmt = stmt.where(Team.name.ilike(_pattern(q)))
    departments = await department_names(access)
    teams = [
        _team_view(t, departments)
        for t in await access.session.scalars(stmt.order_by(Team.name).limit(500))
    ]
    members = await access.session.execute(
        select(TeamMember.team_id, Person.id, Person.display_name)
        .join(Person, Person.id == TeamMember.person_id)
        .where(
            visible(access, Permission.DIRECTORY_READ, TeamMember.tenant_id),
            TeamMember.team_id.in_([t.id for t in teams]),
        )
        .order_by(Person.display_name)
    )
    by_team: dict[uuid.UUID, list[TeamMemberView]] = {}
    for team_id, person_id, name in members:
        by_team.setdefault(team_id, []).append(
            TeamMemberView(person_id=person_id, display_name=name)
        )
    for team in teams:
        team.members = by_team.get(team.id, [])
    return teams


async def add_team_member(
    access: WorkspaceAccess, team_id: uuid.UUID, person_id: uuid.UUID
) -> None:
    authorize(access, Permission.DIRECTORY_MANAGE)
    team = await access.session.get(Team, team_id)
    person = await access.session.get(Person, person_id)
    if team is None or person is None:
        raise ApiError(404, "not_found", "Team or person not found.")
    result = await access.session.execute(
        insert(TeamMember)
        .values(tenant_id=access.tenant_id, team_id=team_id, person_id=person_id)
        .on_conflict_do_nothing()
        .returning(TeamMember.id)
    )
    if result.scalar_one_or_none() is not None:
        history(access, person_id, "joined_team", team_id=team_id)
        audit.record(
            access.session,
            tenant_id=access.tenant_id,
            action="team.member_added",
            actor_user_id=access.user_id,
            target_type="team",
            target_id=team_id,
            details={"person_id": str(person_id)},
        )


async def remove_team_member(
    access: WorkspaceAccess, team_id: uuid.UUID, person_id: uuid.UUID
) -> None:
    authorize(access, Permission.DIRECTORY_MANAGE)
    result = await access.session.execute(
        delete(TeamMember)
        .where(TeamMember.team_id == team_id, TeamMember.person_id == person_id)
        .returning(TeamMember.id)
    )
    if result.scalar_one_or_none() is None:
        raise ApiError(404, "not_found", "That person is not in this team.")
    history(access, person_id, "left_team", team_id=team_id)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="team.member_removed",
        actor_user_id=access.user_id,
        target_type="team",
        target_id=team_id,
        details={"person_id": str(person_id)},
    )


async def create_team(access: WorkspaceAccess, data: TeamIn) -> TeamView:
    authorize(access, Permission.DIRECTORY_MANAGE)
    await _require_department(access, data.department_id)
    team = Team(
        tenant_id=access.tenant_id,
        department_id=data.department_id,
        name=data.name,
        description=blank_to_none(data.description),
        github_slug=(data.github_slug or "").lower() or None,
    )
    access.session.add(team)
    await access.session.flush()
    await access.session.refresh(team)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="team.created",
        actor_user_id=access.user_id,
        target_type="team",
        target_id=team.id,
    )
    return _team_view(team, await department_names(access))


async def update_team(access: WorkspaceAccess, team_id: uuid.UUID, data: TeamUpdate) -> TeamView:
    authorize(access, Permission.DIRECTORY_MANAGE)
    team = await access.session.get(Team, team_id, with_for_update=True)
    if team is None:
        raise ApiError(404, "team_not_found", "Team not found.")
    changed = data.model_dump(exclude_unset=True)
    await _require_department(access, changed.get("department_id"))
    for field, value in changed.items():
        if field == "github_slug":
            value = value.lower() if value else None
        setattr(team, field, blank_to_none(value) if field == "description" else value)
    team.updated_at = func.now()
    await access.session.flush()
    await access.session.refresh(team)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="team.updated",
        actor_user_id=access.user_id,
        target_type="team",
        target_id=team.id,
        details={"fields": ",".join(sorted(changed))},
    )
    return _team_view(team, await department_names(access))


# ---------------------------------------------------------------- departments


async def list_departments(
    access: WorkspaceAccess, *, include_archived: bool = False
) -> list[DepartmentView]:
    authorize(access, Permission.DIRECTORY_READ)
    stmt = select(Department).where(
        visible(access, Permission.DIRECTORY_READ, Department.tenant_id)
    )
    if not include_archived:
        stmt = stmt.where(Department.status == "active")
    departments = list(await access.session.scalars(stmt.order_by(Department.name)))
    counts: dict[str, dict[uuid.UUID, int]] = {}
    for label, model in (("people", Person), ("teams", Team)):
        rows = await access.session.execute(
            select(model.department_id, func.count())
            .where(
                visible(access, Permission.DIRECTORY_READ, model.tenant_id),
                model.department_id.is_not(None),
                model.status == "active",
            )
            .group_by(model.department_id)
        )
        counts[label] = {dept: n for dept, n in rows if dept is not None}
    return [
        DepartmentView(
            id=d.id,
            name=d.name,
            description=d.description,
            status=d.status,
            people_count=counts["people"].get(d.id, 0),
            team_count=counts["teams"].get(d.id, 0),
            created_at=d.created_at,
        )
        for d in departments
    ]


async def _flush_department(access: WorkspaceAccess) -> None:
    try:
        async with access.session.begin_nested():
            await access.session.flush()
    except IntegrityError as exc:
        raise ApiError(409, "department_exists", "A department with that name exists.") from exc


async def _department_view(access: WorkspaceAccess, department_id: uuid.UUID) -> DepartmentView:
    views = await list_departments(access, include_archived=True)
    return next(d for d in views if d.id == department_id)


async def create_department(access: WorkspaceAccess, data: DepartmentIn) -> DepartmentView:
    authorize(access, Permission.DIRECTORY_MANAGE)
    department = Department(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        name=data.name,
        description=blank_to_none(data.description),
    )
    access.session.add(department)
    await _flush_department(access)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="department.created",
        actor_user_id=access.user_id,
        target_type="department",
        target_id=department.id,
    )
    return await _department_view(access, department.id)


async def update_department(
    access: WorkspaceAccess, department_id: uuid.UUID, data: DepartmentUpdate
) -> DepartmentView:
    authorize(access, Permission.DIRECTORY_MANAGE)
    department = await access.session.scalar(
        select(Department)
        .where(
            Department.id == department_id,
            visible(access, Permission.DIRECTORY_READ, Department.tenant_id),
        )
        .with_for_update()
    )
    if department is None:
        raise ApiError(404, "department_not_found", "Department not found.")
    changed = data.model_dump(exclude_unset=True)
    for field, value in changed.items():
        setattr(department, field, blank_to_none(value) if field == "description" else value)
    department.updated_at = func.now()
    await _flush_department(access)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="department.updated",
        actor_user_id=access.user_id,
        target_type="department",
        target_id=department.id,
        details={"fields": ",".join(sorted(changed))},
    )
    return await _department_view(access, department.id)
