import uuid

from fastapi import APIRouter, Request

from relay.identity.auth import Identity
from relay.identity.workspace_access import CurrentWorkspace
from relay.integrations.notion import service as svc
from relay.jobs.outbox import Jobs
from relay.shared.rate_limit import rate_limit

router = APIRouter(prefix="/workspaces/{workspace_id}/integrations/notion", tags=["notion"])
callback = APIRouter(prefix="/integrations/notion", tags=["notion"])


@router.get("")
async def overview(access: CurrentWorkspace, request: Request) -> svc.NotionIntegrationView:
    return await svc.get_integration(access, configured=request.app.state.notion.configured)


@router.post("/connect", dependencies=[rate_limit("oauth", 20, 600)])
async def connect(access: CurrentWorkspace, request: Request) -> svc.ConnectView:
    return await svc.start_connect(access, request.app.state.notion)


@router.post("/connections/{ref}/sync", status_code=202, dependencies=[rate_limit("sync", 30, 600)])
async def sync(access: CurrentWorkspace, ref: uuid.UUID, jobs: Jobs) -> None:
    await svc.request_sync(access, ref, jobs)


@router.post("/connections/{ref}/disconnect", status_code=204)
async def disconnect(access: CurrentWorkspace, ref: uuid.UUID) -> None:
    await svc.disconnect(access, ref)


@router.get("/sources/{source_id}/preview", dependencies=[rate_limit("sync", 30, 600)])
async def preview(
    access: CurrentWorkspace, source_id: uuid.UUID, request: Request
) -> svc.SourcePreviewView:
    return await svc.preview_source(access, source_id, request.app.state.notion)


@router.put("/sources/{source_id}/mapping", status_code=204)
async def map_source(
    access: CurrentWorkspace, source_id: uuid.UUID, body: svc.SourceMappingIn, jobs: Jobs
) -> None:
    await svc.map_source(access, source_id, body, jobs)


@callback.post("/complete", dependencies=[rate_limit("oauth", 20, 600)])
async def complete(
    body: svc.CompleteConnectIn, identity: Identity, request: Request, jobs: Jobs
) -> dict[str, uuid.UUID]:
    state = request.app.state
    workspace_id = await svc.complete_connect(
        state.session_factory, identity, state.notion, jobs, body
    )
    return {"workspace_id": workspace_id}
