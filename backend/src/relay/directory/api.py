import uuid

from fastapi import APIRouter, status

from relay.directory import service as svc
from relay.identity.workspace_access import CurrentWorkspace

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["directory"])


@router.get("/people")
async def list_people(
    access: CurrentWorkspace, q: str | None = None, include_archived: bool = False
) -> list[svc.PersonView]:
    return await svc.list_people(access, q=q, include_archived=include_archived)


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
    access: CurrentWorkspace, q: str | None = None, include_archived: bool = False
) -> list[svc.TeamView]:
    return await svc.list_teams(access, q=q, include_archived=include_archived)


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
