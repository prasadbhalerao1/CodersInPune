import uuid

from fastapi import APIRouter, Request, status

from relay.identity.workspace_access import CurrentWorkspace
from relay.jobs.outbox import Jobs
from relay.notifications import email
from relay.notifications import service as svc
from relay.shared.rate_limit import rate_limit

router = APIRouter(prefix="/workspaces/{workspace_id}/notifications", tags=["notifications"])
admin = APIRouter(prefix="/workspaces/{workspace_id}/email", tags=["email"])


@router.get("")
async def inbox(access: CurrentWorkspace, unread_only: bool = False) -> svc.InboxView:
    return await svc.inbox(access, unread_only=unread_only)


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(access: CurrentWorkspace, body: svc.MarkReadIn) -> None:
    await svc.mark_read(access, body)


@router.get("/preferences")
async def preferences(access: CurrentWorkspace) -> list[email.PreferenceView]:
    return await email.get_preferences(access)


@router.put("/preferences")
async def update_preferences(
    access: CurrentWorkspace, body: email.PreferencesUpdate
) -> list[email.PreferenceView]:
    return await email.update_preferences(access, body)


@admin.get("/status")
async def email_status(access: CurrentWorkspace, request: Request) -> email.EmailStatusView:
    return await email.email_status(access, request.app.state.settings)


@admin.post("/deliveries/{delivery_id}/retry", dependencies=[rate_limit("email_retry", 30, 600)])
async def retry(access: CurrentWorkspace, delivery_id: uuid.UUID, jobs: Jobs) -> email.DeliveryView:
    return await email.retry_delivery(access, delivery_id, jobs)
