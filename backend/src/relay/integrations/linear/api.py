import uuid

from fastapi import APIRouter, Request

from relay.identity.auth import Identity
from relay.identity.workspace_access import CurrentWorkspace
from relay.integrations.linear import service as svc
from relay.jobs.outbox import Jobs
from relay.shared.rate_limit import rate_limit

router = APIRouter(prefix="/workspaces/{workspace_id}/integrations/linear", tags=["linear"])
callback = APIRouter(prefix="/integrations/linear", tags=["linear"])


@router.get("")
async def overview(access: CurrentWorkspace, request: Request) -> svc.LinearIntegrationView:
    return await svc.get_integration(access, configured=request.app.state.linear.configured)


@router.post("/connect", dependencies=[rate_limit("oauth", 20, 600)])
async def connect(access: CurrentWorkspace, request: Request) -> svc.ConnectView:
    return await svc.start_connect(access, request.app.state.linear)


@router.post("/connections/{ref}/sync", status_code=202, dependencies=[rate_limit("sync", 30, 600)])
async def sync(access: CurrentWorkspace, ref: uuid.UUID, jobs: Jobs) -> None:
    await svc.request_sync(access, ref, jobs)


@router.post("/connections/{ref}/disconnect", status_code=204)
async def disconnect(access: CurrentWorkspace, ref: uuid.UUID) -> None:
    await svc.disconnect(access, ref)


@router.post("/projects/{project_id}/link", status_code=204)
async def link_project(
    access: CurrentWorkspace, project_id: uuid.UUID, body: svc.ProjectLinkIn
) -> None:
    await svc.link_project(access, project_id, body)


@router.get("/identities")
async def identities(
    access: CurrentWorkspace, review: bool = False
) -> list[svc.LinearIdentityView]:
    return await svc.list_identities(access, review_only=review)


@router.post("/identities/{identity_id}/decision")
async def decide(
    access: CurrentWorkspace, identity_id: uuid.UUID, body: svc.IdentityDecisionIn
) -> svc.LinearIdentityView:
    return await svc.decide_identity(access, identity_id, body)


@router.get("/signals")
async def signals(access: CurrentWorkspace) -> list[svc.SignalView]:
    return await svc.signals(access)


@callback.post("/complete", dependencies=[rate_limit("oauth", 20, 600)])
async def complete(
    body: svc.CompleteConnectIn, identity: Identity, request: Request, jobs: Jobs
) -> dict[str, uuid.UUID]:
    state = request.app.state
    workspace_id = await svc.complete_connect(
        state.session_factory, identity, state.linear, jobs, body
    )
    return {"workspace_id": workspace_id}
