import uuid

from fastapi import APIRouter, Response, status

from relay.catalog import assets as svc
from relay.identity.workspace_access import CurrentWorkspace
from relay.shared import pagination

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["assets"])


@router.get("/assets")
async def list_assets(
    access: CurrentWorkspace,
    q: str | None = None,
    asset_type: svc.AssetType | None = None,
    status: svc.AssetStatus | None = "active",
    tag: str | None = None,
    lifecycle: svc.Lifecycle | None = None,
    criticality: svc.Criticality | None = None,
    stewarded: bool | None = None,
    after: pagination.After = None,
    limit: pagination.Limit = pagination.MAX_PAGE,
    *,
    response: Response,
) -> list[svc.AssetSummary]:
    items, next_cursor = await svc.list_assets(
        access,
        q=q,
        asset_type=asset_type,
        status=status,
        tag=tag,
        lifecycle=lifecycle,
        criticality=criticality,
        stewarded=stewarded,
        after=after,
        limit=limit,
    )
    pagination.set_next(response, next_cursor)
    return items


@router.post("/assets", status_code=status.HTTP_201_CREATED)
async def create_asset(access: CurrentWorkspace, body: svc.AssetIn) -> svc.AssetDetail:
    return await svc.create_asset(access, body)


@router.get("/assets/{asset_id}")
async def get_asset(access: CurrentWorkspace, asset_id: uuid.UUID) -> svc.AssetDetail:
    return await svc.get_asset(access, asset_id)


@router.patch("/assets/{asset_id}")
async def update_asset(
    access: CurrentWorkspace, asset_id: uuid.UUID, body: svc.AssetUpdate
) -> svc.AssetDetail:
    return await svc.update_asset(access, asset_id, body)


@router.post("/responsibilities/{responsibility_id}/assets", status_code=status.HTTP_204_NO_CONTENT)
async def link_asset(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, body: svc.AssetLinkIn
) -> None:
    await svc.link_asset(access, responsibility_id, body)


@router.delete(
    "/responsibilities/{responsibility_id}/assets/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def unlink_asset(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, asset_id: uuid.UUID
) -> None:
    await svc.unlink_asset(access, responsibility_id, asset_id)


@router.post("/assets/{asset_id}/links", status_code=status.HTTP_201_CREATED)
async def link_target(
    access: CurrentWorkspace, asset_id: uuid.UUID, body: svc.AssetTargetIn
) -> svc.AssetDetail:
    return await svc.link_target(access, asset_id, body)


@router.delete("/assets/{asset_id}/links/{link_id}")
async def unlink_target(
    access: CurrentWorkspace, asset_id: uuid.UUID, link_id: uuid.UUID
) -> svc.AssetDetail:
    return await svc.unlink_target(access, asset_id, link_id)
