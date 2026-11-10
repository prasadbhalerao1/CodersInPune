import uuid

from fastapi import APIRouter

from relay.identity.workspace_access import CurrentWorkspace
from relay.integrations import connectors

router = APIRouter(prefix="/workspaces/{workspace_id}/integrations", tags=["integrations"])


@router.get("/health")
async def health(access: CurrentWorkspace) -> list[connectors.ConnectorView]:
    return await connectors.health(access)


@router.post("/{provider}/{ref}/pause")
async def pause(
    access: CurrentWorkspace, provider: connectors.Provider, ref: uuid.UUID
) -> list[connectors.ConnectorView]:
    return await connectors.set_paused(access, provider, ref, True)


@router.post("/{provider}/{ref}/resume")
async def resume(
    access: CurrentWorkspace, provider: connectors.Provider, ref: uuid.UUID
) -> list[connectors.ConnectorView]:
    return await connectors.set_paused(access, provider, ref, False)
