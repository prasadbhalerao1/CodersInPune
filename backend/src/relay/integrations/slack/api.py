import uuid

from fastapi import APIRouter, Request

from relay.identity.workspace_access import CurrentWorkspace
from relay.integrations.slack import service as svc
from relay.shared.rate_limit import rate_limit

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["slack"])


@router.get("/integrations/slack")
async def slack_status(access: CurrentWorkspace, request: Request) -> svc.SlackStatus:
    return await svc.status(access, request.app.state.settings)


@router.put("/integrations/slack", dependencies=[rate_limit("slack_connect", 10, 600)])
async def connect_slack(
    access: CurrentWorkspace, body: svc.SlackIn, request: Request
) -> svc.SlackStatus:
    return await svc.connect(access, body, request.app.state.settings)


@router.delete("/integrations/slack", status_code=204)
async def disconnect_slack(access: CurrentWorkspace) -> None:
    await svc.disconnect(access)


@router.post("/meetings/{meeting_id}/slack", dependencies=[rate_limit("slack_post", 30, 600)])
async def share_meeting(
    access: CurrentWorkspace, meeting_id: uuid.UUID, request: Request
) -> svc.PostedView:
    return await svc.share_meeting(access, meeting_id, request.app.state.settings)
