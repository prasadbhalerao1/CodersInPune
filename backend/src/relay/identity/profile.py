"""Self-reported display profile, copied onto the caller's own memberships.

The access token carries no name or email, so the frontend sends the signed-in user's
profile (from their WorkOS session) after sign-in. It is display-only: nothing authorizes
on it, and a user can only ever set it for their own memberships.
"""

from fastapi import APIRouter, Request, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.identity.auth import Identity
from relay.identity.models import Membership, UserAccount
from relay.shared.api_types import Email, ShortText, StrictInput
from relay.shared.db.session import unit_of_work

router = APIRouter(prefix="/me", tags=["identity"])


class ProfileIn(StrictInput):
    display_name: ShortText | None = None
    email: Email | None = None


async def sync_profile(
    factory: async_sessionmaker[AsyncSession], workos_user_id: str, data: ProfileIn
) -> int:
    async with unit_of_work(factory, None, workos_user_id) as session:
        rows = (
            await session.execute(
                select(Membership.tenant_id, Membership.user_id)
                .join(UserAccount, UserAccount.id == Membership.user_id)
                .where(UserAccount.workos_user_id == workos_user_id)
            )
        ).all()
    updated = 0
    for tenant_id, user_id in rows:  # one transaction per tenant: RLS scopes each update
        async with unit_of_work(factory, tenant_id, workos_user_id) as session:
            await session.execute(
                update(Membership)
                .where(Membership.user_id == user_id)
                .values(display_name=data.display_name or None, email=data.email or None)
            )
            updated += 1
    return updated


@router.put("/profile", status_code=status.HTTP_204_NO_CONTENT)
async def put_profile(body: ProfileIn, identity: Identity, request: Request) -> None:
    await sync_profile(request.app.state.session_factory, identity.workos_user_id, body)
