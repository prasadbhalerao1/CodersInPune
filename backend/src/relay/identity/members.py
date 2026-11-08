"""Workspace members and invitations. Relay owns membership; WorkOS only verifies identity.

Invitation binding: an invitation names one normalised email. Accepting it requires the
caller's WorkOS-verified email (fetched server-side with the API key) to match exactly, so
an invitation link alone can never admit anyone else. The new membership is created in the
invitation's own workspace, never one named by the client.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.audit import service as audit
from relay.identity.models import ACTIVE, Invitation, Membership, UserAccount
from relay.identity.tokens import VerifiedIdentity
from relay.identity.workos_api import WorkOSClient, WorkOSUnavailableError
from relay.identity.workspace_access import WorkspaceAccess
from relay.platform.models import Tenant
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import Email, StrictInput
from relay.shared.db.session import unit_of_work
from relay.shared.errors import ApiError

WorkspaceRole = Literal["owner", "admin", "member", "guest", "auditor"]


class InvitationIn(StrictInput):
    email: Email
    role: WorkspaceRole = "member"


class MemberUpdate(StrictInput):
    role: WorkspaceRole | None = None
    status: Literal["active", "suspended", "removed"] | None = None


class WorkspaceMemberView(BaseModel):
    user_id: uuid.UUID
    name: str
    email: str | None
    role: str
    status: str
    joined_at: datetime


class InvitationView(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    status: str
    expired: bool
    email_sent: bool
    created_at: datetime
    expires_at: datetime


class MyInvitationView(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    workspace_name: str
    role: str
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(UTC)


def _member_view(m: Membership) -> WorkspaceMemberView:
    return WorkspaceMemberView(
        user_id=m.user_id,
        name=m.display_name or m.email or "Member",
        email=m.email,
        role=m.role,
        status=m.status,
        joined_at=m.created_at,
    )


def _invitation_view(i: Invitation) -> InvitationView:
    return InvitationView(
        id=i.id,
        email=i.email,
        role=i.role,
        status=i.status,
        expired=i.status == "pending" and i.expires_at <= _now(),
        email_sent=i.workos_invitation_id is not None,
        created_at=i.created_at,
        expires_at=i.expires_at,
    )


def _record(
    access: WorkspaceAccess,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    **details: str | int | bool | None,
) -> None:
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=action,
        actor_user_id=access.user_id,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )


# ---------------------------------------------------------------- members


async def list_members(
    access: WorkspaceAccess, *, include_inactive: bool = False
) -> list[WorkspaceMemberView]:
    authorize(access, Permission.MEMBER_READ)
    stmt = select(Membership).where(visible(access, Permission.MEMBER_READ, Membership.tenant_id))
    if not include_inactive:
        stmt = stmt.where(Membership.status == ACTIVE)
    rows = await access.session.scalars(
        stmt.order_by(Membership.display_name, Membership.created_at)
    )
    return [_member_view(m) for m in rows]


async def update_member(
    access: WorkspaceAccess, user_id: uuid.UUID, data: MemberUpdate
) -> WorkspaceMemberView:
    authorize(access, Permission.MEMBER_MANAGE)
    if user_id == access.user_id:
        raise ApiError(409, "cannot_change_self", "You can't change your own membership.")
    member = await access.session.scalar(
        select(Membership).where(Membership.user_id == user_id).with_for_update()
    )
    if member is None:
        raise ApiError(404, "member_not_found", "Member not found.")
    touches_owner = member.role == "owner" or data.role == "owner"
    if touches_owner and access.role != "owner":
        raise ApiError(403, "owner_required", "Only owners can grant or change the owner role.")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    demotes_owner = member.role == "owner" and (
        changes.get("role", "owner") != "owner" or changes.get("status", ACTIVE) != ACTIVE
    )
    if demotes_owner:
        owners = await access.session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.role == "owner", Membership.status == ACTIVE)
        )
        if (owners or 0) <= 1:
            raise ApiError(409, "last_owner", "A workspace needs at least one active owner.")
    for field, value in changes.items():
        setattr(member, field, value)
    member.updated_at = func.now()
    await access.session.flush()
    await access.session.refresh(member)
    _record(
        access,
        "membership.updated",
        "membership",
        member.id,
        **{k: str(v) for k, v in changes.items()},
    )
    return _member_view(member)


# ---------------------------------------------------------------- invitations (admin side)


async def list_invitations(access: WorkspaceAccess) -> list[InvitationView]:
    authorize(access, Permission.MEMBER_MANAGE)
    rows = await access.session.scalars(
        select(Invitation)
        .where(
            visible(access, Permission.MEMBER_MANAGE, Invitation.tenant_id),
            Invitation.status == "pending",
        )
        .order_by(Invitation.created_at.desc())
    )
    return [_invitation_view(i) for i in rows]


async def create_invitation(
    access: WorkspaceAccess, data: InvitationIn, workos: WorkOSClient, ttl_days: int
) -> InvitationView:
    authorize(access, Permission.MEMBER_MANAGE)
    if data.role == "owner" and access.role != "owner":
        raise ApiError(403, "owner_required", "Only owners can invite owners.")
    email = data.email.lower()
    already = await access.session.scalar(
        select(Membership.id).where(
            func.lower(Membership.email) == email, Membership.status == ACTIVE
        )
    )
    if already:
        raise ApiError(409, "already_member", "That person is already a member.")
    workspace = await access.session.get_one(Tenant, access.tenant_id)
    invitation = Invitation(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        email=email,
        role=data.role,
        workspace_name=workspace.name,
        invited_by=access.user_id,
        expires_at=_now() + timedelta(days=ttl_days),
    )
    access.session.add(invitation)
    try:
        await access.session.flush()
    except IntegrityError as exc:  # unique pending invitation per email
        raise ApiError(
            409, "invitation_exists", "There is already a pending invitation for that email."
        ) from exc
    invitation.workos_invitation_id = await workos.send_invitation(email, ttl_days)
    await access.session.flush()
    await access.session.refresh(invitation)
    _record(access, "invitation.created", "invitation", invitation.id, role=data.role)
    return _invitation_view(invitation)


async def revoke_invitation(
    access: WorkspaceAccess, invitation_id: uuid.UUID, workos: WorkOSClient
) -> InvitationView:
    authorize(access, Permission.MEMBER_MANAGE)
    invitation = await access.session.scalar(
        select(Invitation).where(Invitation.id == invitation_id).with_for_update()
    )
    if invitation is None or invitation.status != "pending":
        raise ApiError(404, "invitation_not_found", "No pending invitation found.")
    invitation.status = "revoked"
    invitation.decided_at = func.now()
    if invitation.workos_invitation_id:
        await workos.revoke_invitation(invitation.workos_invitation_id)
    await access.session.flush()
    await access.session.refresh(invitation)
    _record(access, "invitation.revoked", "invitation", invitation.id)
    return _invitation_view(invitation)


# ---------------------------------------------------------------- invitations (invitee side)


async def _verified_email(
    identity: VerifiedIdentity, workos: WorkOSClient
) -> tuple[str, str | None]:
    try:
        user = await workos.get_user(identity.workos_user_id)
    except WorkOSUnavailableError as exc:
        raise ApiError(
            503, "invitations_unavailable", "Invitations can't be verified right now."
        ) from exc
    if not user.email_verified:
        raise ApiError(403, "email_unverified", "Verify your email address to accept invitations.")
    return user.email, user.display_name


async def my_invitations(
    factory: async_sessionmaker[AsyncSession], identity: VerifiedIdentity, workos: WorkOSClient
) -> list[MyInvitationView]:
    email, _ = await _verified_email(identity, workos)
    async with unit_of_work(factory, None, identity.workos_user_id, principal_email=email) as s:
        rows = await s.scalars(
            select(Invitation).where(Invitation.email == email, Invitation.expires_at > func.now())
        )
        return [
            MyInvitationView(
                id=i.id,
                workspace_id=i.tenant_id,
                workspace_name=i.workspace_name,
                role=i.role,
                expires_at=i.expires_at,
            )
            for i in rows
        ]


async def accept_invitation(
    factory: async_sessionmaker[AsyncSession],
    identity: VerifiedIdentity,
    workos: WorkOSClient,
    invitation_id: uuid.UUID,
) -> uuid.UUID:
    """Returns the joined workspace id."""
    email, display_name = await _verified_email(identity, workos)
    sub = identity.workos_user_id
    async with unit_of_work(factory, None, sub, principal_email=email) as s:
        found = await s.scalar(
            select(Invitation.tenant_id).where(
                Invitation.id == invitation_id,
                Invitation.email == email,
                Invitation.expires_at > func.now(),
            )
        )
    if found is None:
        raise ApiError(
            404, "invitation_not_found", "This invitation is not valid for your account."
        )
    # Tenant context comes from the invitation the verified email was matched against.
    async with unit_of_work(factory, found, sub, principal_email=email) as session:
        invitation = await session.scalar(
            select(Invitation).where(Invitation.id == invitation_id).with_for_update()
        )
        if invitation is None or invitation.status != "pending" or invitation.email != email:
            raise ApiError(
                404, "invitation_not_found", "This invitation is not valid for your account."
            )
        user_id = (
            await session.execute(
                insert(UserAccount)
                .values(workos_user_id=sub)
                .on_conflict_do_update(
                    index_elements=[UserAccount.workos_user_id], set_={"workos_user_id": sub}
                )
                .returning(UserAccount.id)
            )
        ).scalar_one()
        member = await session.scalar(
            select(Membership).where(Membership.user_id == user_id).with_for_update()
        )
        if member is not None and member.status == ACTIVE:
            raise ApiError(409, "already_member", "You are already a member of this workspace.")
        if member is None:
            member = Membership(
                tenant_id=found, user_id=user_id, role=invitation.role, status=ACTIVE
            )
            session.add(member)
        else:
            member.role, member.status = invitation.role, ACTIVE
        member.display_name, member.email = display_name, email
        invitation.status, invitation.accepted_by, invitation.decided_at = (
            "accepted",
            user_id,
            func.now(),
        )
        await session.flush()
        audit.record(
            session,
            tenant_id=found,
            action="membership.created",
            actor_user_id=user_id,
            target_type="membership",
            target_id=member.id,
            details={"role": invitation.role, "via": "invitation"},
        )
    return found
