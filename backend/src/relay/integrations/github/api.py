import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Request

from relay.identity.auth import Identity
from relay.identity.workspace_access import CurrentWorkspace
from relay.integrations.github import review, webhooks
from relay.integrations.github import service as svc
from relay.shared.rate_limit import rate_limit

router = APIRouter(prefix="/workspaces/{workspace_id}/integrations/github", tags=["github"])
callback = APIRouter(prefix="/integrations/github", tags=["github"])

SuggestionStatus = Literal["open", "deferred", "dismissed", "approved", "withdrawn"]


@router.get("")
async def overview(access: CurrentWorkspace, request: Request) -> svc.IntegrationView:
    return await svc.get_integration(access, configured=request.app.state.github.configured)


@router.post("/connect", dependencies=[rate_limit("oauth", 20, 600)])
async def connect(access: CurrentWorkspace, request: Request) -> svc.ConnectView:
    return await svc.start_connect(access, request.app.state.github)


@router.post("/installations/{installation_ref}/sync", dependencies=[rate_limit("sync", 30, 600)])
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


@callback.post("/complete", dependencies=[rate_limit("oauth", 20, 600)])
async def complete(
    body: svc.CompleteConnectIn, identity: Identity, request: Request
) -> dict[str, uuid.UUID]:
    state = request.app.state
    workspace_id = await svc.complete_connect(
        state.session_factory, identity, state.github, state.jobs, body
    )
    return {"workspace_id": workspace_id}


# ---- evidence review (owners/admins)


@router.get("/identities")
async def identities(
    access: CurrentWorkspace,
    status: Literal["review", "unmatched", "suggested", "linked", "dismissed"] | None = None,
) -> list[review.IdentityView]:
    return await review.list_identities(access, status=status)


@router.post("/identities/{identity_id}/decision")
async def decide_identity(
    access: CurrentWorkspace, identity_id: uuid.UUID, body: review.IdentityDecisionIn
) -> review.IdentityView:
    return await review.decide_identity(access, identity_id, body)


@router.get("/teams")
async def teams(access: CurrentWorkspace) -> list[review.GitHubTeamView]:
    return await review.list_github_teams(access)


@router.post("/teams/{github_team_id}/link")
async def link_team(
    access: CurrentWorkspace, github_team_id: uuid.UUID, body: review.TeamLinkIn
) -> review.GitHubTeamView:
    return await review.link_team(access, github_team_id, body)


@router.get("/signals")
async def signals(access: CurrentWorkspace, request: Request) -> list[review.SignalView]:
    return await review.ownership_signals(
        access, days=request.app.state.settings.github_activity_days
    )


@router.post("/suggestions/bulk")
async def bulk_decide(
    access: CurrentWorkspace, body: review.BulkDecisionIn
) -> list[review.BulkResultView]:
    return await review.bulk_decide(access, body)


# ---- webhooks (no user session: authenticated by HMAC signature)


@callback.post("/webhook", status_code=202)
async def webhook(
    request: Request,
    x_github_event: Annotated[str, Header()] = "",
    x_github_delivery: Annotated[str, Header()] = "",
    x_hub_signature_256: Annotated[str | None, Header()] = None,
) -> dict[str, int]:
    state = request.app.state
    queued = await webhooks.receive(
        state.session_factory,
        state.settings,
        state.jobs,
        event=x_github_event,
        delivery_id=x_github_delivery,
        signature=x_hub_signature_256,
        body=await request.body(),
    )
    return {"queued": queued}
