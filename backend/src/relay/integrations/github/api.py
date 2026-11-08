import uuid
from typing import Literal

from fastapi import APIRouter, Request

from relay.identity.auth import Identity
from relay.identity.workspace_access import CurrentWorkspace
from relay.integrations.github import service as svc

router = APIRouter(prefix="/workspaces/{workspace_id}/integrations/github", tags=["github"])
callback = APIRouter(prefix="/integrations/github", tags=["github"])

SuggestionStatus = Literal["open", "deferred", "dismissed", "approved", "withdrawn"]


@router.get("")
async def overview(access: CurrentWorkspace, request: Request) -> svc.IntegrationView:
    return await svc.get_integration(access, configured=request.app.state.github.configured)


@router.post("/connect")
async def connect(access: CurrentWorkspace, request: Request) -> svc.ConnectView:
    return await svc.start_connect(access, request.app.state.github)


@router.post("/installations/{installation_ref}/sync")
async def sync(
    access: CurrentWorkspace, installation_ref: uuid.UUID, request: Request
) -> svc.IntegrationView:
    return await svc.request_sync(access, installation_ref, request.app.state.jobs)


@router.post("/installations/{installation_ref}/disconnect")
async def disconnect(access: CurrentWorkspace, installation_ref: uuid.UUID) -> svc.IntegrationView:
    return await svc.disconnect(access, installation_ref)


@router.patch("/repositories/{repository_id}")
async def update_repository(
    access: CurrentWorkspace, repository_id: uuid.UUID, body: svc.RepositoryUpdate
) -> svc.RepositoryView:
    return await svc.set_repository_selected(access, repository_id, body)


@router.get("/suggestions")
async def suggestions(
    access: CurrentWorkspace, status: SuggestionStatus = "open"
) -> list[svc.SuggestionView]:
    return await svc.list_suggestions(access, status=status)


@router.post("/suggestions/{suggestion_id}/decision")
async def decide(
    access: CurrentWorkspace, suggestion_id: uuid.UUID, body: svc.SuggestionDecisionIn
) -> svc.DecisionView:
    return await svc.decide_suggestion(access, suggestion_id, body)


@callback.post("/complete")
async def complete(
    body: svc.CompleteConnectIn, identity: Identity, request: Request
) -> dict[str, uuid.UUID]:
    state = request.app.state
    workspace_id = await svc.complete_connect(
        state.session_factory, identity, state.github, state.jobs, body
    )
    return {"workspace_id": workspace_id}
