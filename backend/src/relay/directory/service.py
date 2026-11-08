"""People and teams directory: list, create, update, archive."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from relay.audit import service as audit
from relay.directory.models import Person, Team, TeamMember
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import Email, LongText, Name, ShortText, StrictInput, blank_to_none
from relay.shared.errors import ApiError

Status = Literal["active", "archived"]


class PersonIn(StrictInput):
    display_name: Name
    email: Email | None = None
    title: ShortText | None = None


class PersonUpdate(StrictInput):
    display_name: Name | None = None
    email: Email | None = None
    title: ShortText | None = None
    status: Status | None = None


class PersonView(BaseModel):
    id: uuid.UUID
    display_name: str
    email: str | None
    title: str | None
    status: str
    created_at: datetime


class TeamIn(StrictInput):
    name: Name
    description: LongText | None = None


class TeamUpdate(StrictInput):
    name: Name | None = None
    description: LongText | None = None
    status: Status | None = None


class MemberView(BaseModel):
    person_id: uuid.UUID
    display_name: str


class TeamView(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    members: list[MemberView] = []


def _person_view(p: Person) -> PersonView:
    return PersonView(
        id=p.id,
        display_name=p.display_name,
        email=p.email,
        title=p.title,
        status=p.status,
        created_at=p.created_at,
    )


def _team_view(t: Team) -> TeamView:
    return TeamView(
        id=t.id, name=t.name, description=t.description, status=t.status, created_at=t.created_at
    )


def _pattern(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def list_people(
    access: WorkspaceAccess, *, q: str | None = None, include_archived: bool = False
) -> list[PersonView]:
    stmt = select(Person).where(visible(access, Permission.DIRECTORY_READ, Person.tenant_id))
    if not include_archived:
        stmt = stmt.where(Person.status == "active")
    if q:
        stmt = stmt.where(
            or_(Person.display_name.ilike(_pattern(q)), Person.email.ilike(_pattern(q)))
        )
    rows = await access.session.scalars(stmt.order_by(Person.display_name, Person.id).limit(500))
    return [_person_view(p) for p in rows]


async def create_person(access: WorkspaceAccess, data: PersonIn) -> PersonView:
    authorize(access, Permission.DIRECTORY_MANAGE)
    person = Person(
        tenant_id=access.tenant_id,
        display_name=data.display_name,
        email=blank_to_none(data.email),
        title=blank_to_none(data.title),
    )
    access.session.add(person)
    await access.session.flush()
    await access.session.refresh(person)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="person.created",
        actor_user_id=access.user_id,
        target_type="person",
        target_id=person.id,
    )
    return _person_view(person)


async def update_person(
    access: WorkspaceAccess, person_id: uuid.UUID, data: PersonUpdate
) -> PersonView:
    authorize(access, Permission.DIRECTORY_MANAGE)
    person = await access.session.get(Person, person_id, with_for_update=True)
    if person is None:
        raise ApiError(404, "person_not_found", "Person not found.")
    changed = data.model_dump(exclude_unset=True)
    for field, value in changed.items():
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
    return _person_view(person)


async def list_teams(
    access: WorkspaceAccess, *, q: str | None = None, include_archived: bool = False
) -> list[TeamView]:
    stmt = select(Team).where(visible(access, Permission.DIRECTORY_READ, Team.tenant_id))
    if not include_archived:
        stmt = stmt.where(Team.status == "active")
    if q:
        stmt = stmt.where(Team.name.ilike(_pattern(q)))
    teams = [
        _team_view(t) for t in await access.session.scalars(stmt.order_by(Team.name).limit(500))
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
    by_team: dict[uuid.UUID, list[MemberView]] = {}
    for team_id, person_id, name in members:
        by_team.setdefault(team_id, []).append(MemberView(person_id=person_id, display_name=name))
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
    team = Team(
        tenant_id=access.tenant_id,
        name=data.name,
        description=blank_to_none(data.description),
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
    return _team_view(team)


async def update_team(access: WorkspaceAccess, team_id: uuid.UUID, data: TeamUpdate) -> TeamView:
    authorize(access, Permission.DIRECTORY_MANAGE)
    team = await access.session.get(Team, team_id, with_for_update=True)
    if team is None:
        raise ApiError(404, "team_not_found", "Team not found.")
    changed = data.model_dump(exclude_unset=True)
    for field, value in changed.items():
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
    return _team_view(team)
