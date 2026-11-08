import uuid

from fastapi import APIRouter, Request, status

from relay.identity import members as svc
from relay.identity.auth import Identity
from relay.identity.workspace_access import CurrentWorkspace
from relay.notifications.email_provider import email_configured

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["members"])
me = APIRouter(prefix="/me", tags=["members"])


@router.get("/members")
async def list_members(
    access: CurrentWorkspace, include_inactive: bool = False
) -> list[svc.WorkspaceMemberView]:
    return await svc.list_members(access, include_inactive=include_inactive)


@router.patch("/members/{user_id}")
async def update_member(
    access: CurrentWorkspace, user_id: uuid.UUID, body: svc.MemberUpdate
) -> svc.WorkspaceMemberView:
    return await svc.update_member(access, user_id, body)


@router.get("/invitations")
async def list_invitations(access: CurrentWorkspace) -> list[svc.InvitationView]:
    return await svc.list_invitations(access)


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
async def invite(
    access: CurrentWorkspace, body: svc.InvitationIn, request: Request
) -> svc.InvitationView:
    state = request.app.state
    return await svc.create_invitation(
        access,
        body,
        state.workos,
        state.settings.invitation_ttl_days,
        email_jobs=state.jobs if email_configured(state.settings) else None,
    )


@router.post("/invitations/{invitation_id}/revoke")
async def revoke(
    access: CurrentWorkspace, invitation_id: uuid.UUID, request: Request
) -> svc.InvitationView:
    return await svc.revoke_invitation(access, invitation_id, request.app.state.workos)


@me.get("/invitations")
async def my_invitations(identity: Identity, request: Request) -> list[svc.MyInvitationView]:
    state = request.app.state
    return await svc.my_invitations(state.session_factory, identity, state.workos)


@me.post("/invitations/{invitation_id}/accept")
async def accept(
    identity: Identity, invitation_id: uuid.UUID, request: Request
) -> dict[str, uuid.UUID]:
    state = request.app.state
    workspace_id = await svc.accept_invitation(
        state.session_factory, identity, state.workos, invitation_id
    )
    return {"workspace_id": workspace_id}
