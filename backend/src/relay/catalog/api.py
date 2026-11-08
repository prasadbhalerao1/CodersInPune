import uuid
from datetime import datetime

from fastapi import APIRouter, status

from relay.catalog import service as svc
from relay.identity.workspace_access import CurrentWorkspace

router = APIRouter(prefix="/workspaces/{workspace_id}/responsibilities", tags=["catalog"])
Detail = svc.ResponsibilityDetail


@router.get("")
async def list_responsibilities(
    access: CurrentWorkspace,
    q: str | None = None,
    criticality: svc.Criticality | None = None,
    status: svc.ResponsibilityStatus | None = "active",
    category: str | None = None,
) -> list[svc.ResponsibilitySummary]:
    return await svc.list_responsibilities(
        access, q=q, criticality=criticality, status=status, category=category
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(access: CurrentWorkspace, body: svc.ResponsibilityIn) -> Detail:
    return await svc.create_responsibility(access, body)


@router.get("/{responsibility_id}")
async def detail(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, as_of: datetime | None = None
) -> Detail:
    return await svc.get_responsibility(access, responsibility_id, as_of=as_of)


@router.patch("/{responsibility_id}")
async def edit(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, body: svc.ResponsibilityUpdate
) -> Detail:
    return await svc.update_responsibility(access, responsibility_id, body)


@router.post("/{responsibility_id}/archive")
async def archive(access: CurrentWorkspace, responsibility_id: uuid.UUID) -> Detail:
    return await svc.set_responsibility_status(access, responsibility_id, "archived")


@router.post("/{responsibility_id}/restore")
async def restore(access: CurrentWorkspace, responsibility_id: uuid.UUID) -> Detail:
    return await svc.set_responsibility_status(access, responsibility_id, "active")


@router.post("/{responsibility_id}/assignments", status_code=status.HTTP_201_CREATED)
async def assign(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, body: svc.AssignmentIn
) -> Detail:
    return await svc.assign_owner(access, responsibility_id, body)


@router.post("/{responsibility_id}/assignments/{assignment_id}/end")
async def end(
    access: CurrentWorkspace,
    responsibility_id: uuid.UUID,
    assignment_id: uuid.UUID,
    body: svc.EndAssignmentIn,
) -> Detail:
    return await svc.end_assignment(access, responsibility_id, assignment_id, body)


@router.post("/{responsibility_id}/primary")
async def replace_primary(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, body: svc.ReplacePrimaryIn
) -> Detail:
    return await svc.replace_primary(access, responsibility_id, body)


@router.get("/{responsibility_id}/history")
async def history(access: CurrentWorkspace, responsibility_id: uuid.UUID) -> list[svc.ChangeView]:
    return await svc.ownership_history(access, responsibility_id)
