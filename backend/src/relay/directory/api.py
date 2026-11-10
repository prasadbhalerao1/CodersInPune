import uuid

from fastapi import APIRouter, Response, status

from relay.directory import identities, profiles
from relay.directory import service as svc
from relay.identity.workspace_access import CurrentWorkspace
from relay.shared import pagination

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["directory"])


@router.get("/people")
async def list_people(
    access: CurrentWorkspace,
    q: str | None = None,
    include_archived: bool = False,
    department_id: uuid.UUID | None = None,
    after: pagination.After = None,
    limit: pagination.Limit = pagination.MAX_PAGE,
    *,
    response: Response,
) -> list[svc.PersonView]:
    items, next_cursor = await svc.list_people(
        access,
        q=q,
        include_archived=include_archived,
        department_id=department_id,
        after=after,
        limit=limit,
    )
    pagination.set_next(response, next_cursor)
    return items


@router.post("/people", status_code=status.HTTP_201_CREATED)
async def create_person(access: CurrentWorkspace, body: svc.PersonIn) -> svc.PersonView:
    return await svc.create_person(access, body)


@router.patch("/people/{person_id}")
async def update_person(
    access: CurrentWorkspace, person_id: uuid.UUID, body: svc.PersonUpdate
) -> svc.PersonView:
    return await svc.update_person(access, person_id, body)


@router.get("/teams")
async def list_teams(
    access: CurrentWorkspace,
    q: str | None = None,
    include_archived: bool = False,
    department_id: uuid.UUID | None = None,
) -> list[svc.TeamView]:
    return await svc.list_teams(
        access, q=q, include_archived=include_archived, department_id=department_id
    )


@router.post("/teams", status_code=status.HTTP_201_CREATED)
async def create_team(access: CurrentWorkspace, body: svc.TeamIn) -> svc.TeamView:
    return await svc.create_team(access, body)


@router.patch("/teams/{team_id}")
async def update_team(
    access: CurrentWorkspace, team_id: uuid.UUID, body: svc.TeamUpdate
) -> svc.TeamView:
    return await svc.update_team(access, team_id, body)


@router.put("/teams/{team_id}/members/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def add_member(access: CurrentWorkspace, team_id: uuid.UUID, person_id: uuid.UUID) -> None:
    await svc.add_team_member(access, team_id, person_id)


@router.delete("/teams/{team_id}/members/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(access: CurrentWorkspace, team_id: uuid.UUID, person_id: uuid.UUID) -> None:
    await svc.remove_team_member(access, team_id, person_id)


@router.get("/departments")
async def list_departments(
    access: CurrentWorkspace, include_archived: bool = False
) -> list[svc.DepartmentView]:
    return await svc.list_departments(access, include_archived=include_archived)


@router.post("/departments", status_code=status.HTTP_201_CREATED)
async def create_department(access: CurrentWorkspace, body: svc.DepartmentIn) -> svc.DepartmentView:
    return await svc.create_department(access, body)


@router.patch("/departments/{department_id}")
async def update_department(
    access: CurrentWorkspace, department_id: uuid.UUID, body: svc.DepartmentUpdate
) -> svc.DepartmentView:
    return await svc.update_department(access, department_id, body)


@router.get("/people/{person_id}/profile")
async def person_profile(access: CurrentWorkspace, person_id: uuid.UUID) -> profiles.ProfileView:
    return await profiles.person_profile(access, person_id)


@router.get("/teams/{team_id}/profile")
async def team_profile(access: CurrentWorkspace, team_id: uuid.UUID) -> profiles.ProfileView:
    return await profiles.team_profile(access, team_id)


@router.get("/departments/{department_id}/profile")
async def department_profile(
    access: CurrentWorkspace, department_id: uuid.UUID
) -> profiles.ProfileView:
    return await profiles.department_profile(access, department_id)


@router.get("/identity-conflicts")
async def identity_conflicts(access: CurrentWorkspace) -> list[identities.IdentityConflict]:
    return await identities.identity_conflicts(access)
