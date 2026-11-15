"""Workspace deletion: scheduled by the owner, purged after a grace period.

Scheduling keeps the workspace fully usable, so people can export what they need, and the
owner can cancel until the grace period ends. The purge itself is an operator task
(`relay-purge-workspaces`) that runs as the owner role from the migration URL: the
application role can't delete audit events or ownership history, and never will.
"""

import argparse
import asyncio
import logging
import sys
import uuid
from datetime import UTC, datetime, timedelta

from pydantic import AwareDatetime, BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import relay.models  # noqa: F401  (registers every table for the purge order)
from relay.audit import service as audit
from relay.config import MigrationSettings
from relay.identity.workspace_access import WorkspaceAccess
from relay.platform.models import Tenant
from relay.policy.permissions import Permission, authorize
from relay.shared.db.base import Base
from relay.shared.db.session import create_session_factory, unit_of_work
from relay.shared.errors import ApiError

GRACE = timedelta(days=30)  # must match platform.tenant_deletion_due (migration 0034)
logger = logging.getLogger(__name__)


class DeletionView(BaseModel):
    requested_at: AwareDatetime | None
    scheduled_for: AwareDatetime | None


def _view(tenant: Tenant) -> DeletionView:
    at = tenant.deletion_requested_at
    return DeletionView(requested_at=at, scheduled_for=at + GRACE if at else None)


async def _tenant(access: WorkspaceAccess) -> Tenant:
    tenant = await access.session.scalar(
        select(Tenant).where(Tenant.id == access.tenant_id).with_for_update()
    )
    assert tenant is not None  # membership was just resolved for this tenant
    return tenant


async def deletion_status(access: WorkspaceAccess) -> DeletionView:
    authorize(access, Permission.WORKSPACE_READ)
    return _view(await access.session.get_one(Tenant, access.tenant_id))


async def schedule_deletion(access: WorkspaceAccess, confirm_name: str) -> DeletionView:
    authorize(access, Permission.WORKSPACE_DELETE)
    tenant = await _tenant(access)
    if confirm_name != tenant.name:
        raise ApiError(422, "confirmation_mismatch", "Type the workspace name exactly to confirm.")
    if tenant.deletion_requested_at is not None:
        raise ApiError(409, "deletion_already_scheduled", "Deletion is already scheduled.")
    tenant.deletion_requested_at = datetime.now(UTC)
    tenant.deletion_requested_by = access.user_id
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="workspace.deletion_scheduled",
        actor_user_id=access.user_id,
        target_type="workspace",
        target_id=access.tenant_id,
        details={"grace_days": GRACE.days},
    )
    return _view(tenant)


async def cancel_deletion(access: WorkspaceAccess) -> DeletionView:
    authorize(access, Permission.WORKSPACE_DELETE)
    tenant = await _tenant(access)
    if tenant.deletion_requested_at is None:
        raise ApiError(409, "deletion_not_scheduled", "Deletion isn't scheduled.")
    tenant.deletion_requested_at = None
    tenant.deletion_requested_by = None
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="workspace.deletion_cancelled",
        actor_user_id=access.user_id,
        target_type="workspace",
        target_id=access.tenant_id,
    )
    return _view(tenant)


async def purge_due(owner_factory: async_sessionmaker[AsyncSession]) -> list[uuid.UUID]:
    """Delete every workspace whose grace period has ended. Must run as the owner role.

    Each workspace is purged in its own transaction under its own tenant context, children
    before parents, so a failure leaves that workspace whole rather than half-deleted.
    """
    async with unit_of_work(owner_factory, None) as session:
        # Without a tenant context only the `purge_due` policy matches: due workspaces.
        due = list(await session.scalars(select(Tenant.id)))
    tables = [
        t
        for t in reversed(Base.metadata.sorted_tables)
        if "tenant_id" in t.c and t is not Tenant.__table__
    ]
    purged = []
    for tenant_id in due:
        async with unit_of_work(owner_factory, tenant_id) as session:
            locked = await session.scalar(
                select(Tenant.id).where(Tenant.id == tenant_id).with_for_update()
            )
            # Re-checked under the lock: the owner may have cancelled meanwhile.
            if locked is None or not await session.scalar(
                select(func.platform.tenant_deletion_due(tenant_id))
            ):
                continue
            for table in tables:
                await session.execute(delete(table).where(table.c.tenant_id == tenant_id))
            await session.execute(delete(Tenant).where(Tenant.id == tenant_id))
        logger.info("purged workspace %s", tenant_id)
        purged.append(tenant_id)
    return purged


async def _run() -> list[uuid.UUID]:
    engine = create_async_engine(
        MigrationSettings().migration_database_url, connect_args={"prepare_threshold": None}
    )
    try:
        return await purge_due(create_session_factory(engine))
    finally:
        await engine.dispose()


def main() -> None:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    logging.basicConfig(level=logging.INFO)
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    purged = asyncio.run(_run(), loop_factory=loop_factory)
    print(f"Purged {len(purged)} workspace(s).")


if __name__ == "__main__":
    main()
