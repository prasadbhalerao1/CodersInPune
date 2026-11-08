from fastapi import APIRouter, status

from relay.identity.workspace_access import CurrentWorkspace
from relay.notifications import service as svc

router = APIRouter(prefix="/workspaces/{workspace_id}/notifications", tags=["notifications"])


@router.get("")
async def inbox(access: CurrentWorkspace, unread_only: bool = False) -> svc.InboxView:
    return await svc.inbox(access, unread_only=unread_only)


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(access: CurrentWorkspace, body: svc.MarkReadIn) -> None:
    await svc.mark_read(access, body)
