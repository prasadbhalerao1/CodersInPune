import uuid

from fastapi import APIRouter, status

from relay.catalog import assets as svc
from relay.identity.workspace_access import CurrentWorkspace

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["assets"])


@router.get("/assets")
async def list_assets(
    access: CurrentWorkspace,
    q: str | None = None,
    asset_type: svc.AssetType | None = None,
    status: svc.AssetStatus | None = "active",
) -> list[svc.AssetSummary]:
    return await svc.list_assets(access, q=q, asset_type=asset_type, status=status)


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
