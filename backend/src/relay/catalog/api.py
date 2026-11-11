import uuid
from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import AwareDatetime

from relay.catalog import context, stewardship, timeline
from relay.catalog import service as svc
from relay.identity.workspace_access import CurrentWorkspace
from relay.shared import pagination

router = APIRouter(prefix="/workspaces/{workspace_id}/responsibilities", tags=["catalog"])
Detail = svc.ResponsibilityDetail


@router.get("")
async def list_responsibilities(
    access: CurrentWorkspace,
    q: str | None = None,
    criticality: svc.Criticality | None = None,
    status: svc.ResponsibilityStatus | None = "active",
    category: str | None = None,
    department_id: uuid.UUID | None = None,
    type_id: uuid.UUID | None = None,
    has_backup: bool | None = None,
    review: Literal["due", "ok"] | None = None,
    needs_verification: bool | None = None,
    after: pagination.After = None,
    limit: pagination.Limit = pagination.MAX_PAGE,
    *,
    response: Response,
) -> list[svc.ResponsibilitySummary]:
    items, next_cursor = await svc.list_responsibilities(
        access,
        q=q,
        criticality=criticality,
        status=status,
        category=category,
        department_id=department_id,
        type_id=type_id,
        has_backup=has_backup,
        review=review,
        needs_verification=needs_verification,
        after=after,
        limit=limit,
    )
    pagination.set_next(response, next_cursor)
    return items


@router.get("/types")
async def list_types(access: CurrentWorkspace) -> list[stewardship.TypeView]:
    return await stewardship.list_types(access)


@router.post("/types", status_code=status.HTTP_201_CREATED)
async def create_type(
    access: CurrentWorkspace, body: stewardship.TypeIn
) -> list[stewardship.TypeView]:
    return await stewardship.create_type(access, body)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create(access: CurrentWorkspace, body: svc.ResponsibilityIn) -> Detail:
    return await svc.create_responsibility(access, body)


@router.get("/{responsibility_id}")
async def detail(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, as_of: AwareDatetime | None = None
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


@router.get("/{responsibility_id}/context")
async def responsibility_context(
    access: CurrentWorkspace, responsibility_id: uuid.UUID
) -> context.ResponsibilityContextView:
    return await context.responsibility_context(access, responsibility_id)


@router.post("/{responsibility_id}/assignments/{assignment_id}/correct")
async def correct(
    access: CurrentWorkspace,
    responsibility_id: uuid.UUID,
    assignment_id: uuid.UUID,
    body: svc.CorrectionIn,
) -> Detail:
    return await svc.correct_assignment(access, responsibility_id, assignment_id, body)


@router.post("/{responsibility_id}/review", status_code=status.HTTP_204_NO_CONTENT)
async def review(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, verified: bool = False
) -> None:
    await stewardship.mark_reviewed(access, responsibility_id, verified=verified)


@router.get("/{responsibility_id}/stewardship")
async def get_stewardship(
    access: CurrentWorkspace, responsibility_id: uuid.UUID
) -> stewardship.StewardshipView:
    return await stewardship.stewardship(access, responsibility_id)


@router.post("/{responsibility_id}/dependencies", status_code=status.HTTP_201_CREATED)
async def add_dependency(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, body: stewardship.DependencyIn
) -> stewardship.StewardshipView:
    return await stewardship.add_dependency(access, responsibility_id, body)


@router.delete("/{responsibility_id}/dependencies/{dependency_id}")
async def remove_dependency(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, dependency_id: uuid.UUID
) -> stewardship.StewardshipView:
    return await stewardship.remove_dependency(access, responsibility_id, dependency_id)


@router.post("/{responsibility_id}/access", status_code=status.HTTP_201_CREATED)
async def grant_access(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, body: stewardship.AccessGrantIn
) -> stewardship.StewardshipView:
    return await stewardship.grant_access(access, responsibility_id, body)


@router.delete("/{responsibility_id}/access/{user_id}")
async def revoke_access(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, user_id: uuid.UUID
) -> stewardship.StewardshipView:
    return await stewardship.revoke_access(access, responsibility_id, user_id)


@router.get("/{responsibility_id}/timeline")
async def responsibility_timeline(
    access: CurrentWorkspace,
    responsibility_id: uuid.UUID,
    category: timeline.Category | None = None,
    before: AwareDatetime | None = None,
    limit: int = 200,
) -> timeline.TimelineView:
    """Project Memory Replay: the responsibility's history, rebuilt from live data."""
    return await timeline.responsibility_timeline(
        access, responsibility_id, category=category, before=before, limit=limit
    )
