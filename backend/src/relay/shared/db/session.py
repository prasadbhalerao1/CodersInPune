"""Session lifecycle and transaction-local tenant context.

Rules (see CLAUDE.md guardrails):
- One `AsyncSession` per request or job; never shared across concurrent tasks.
- The tenant is fixed when the session is created and applied at the start of
  *every* transaction with `set_config('app.tenant_id', ..., true)`, so it can never
  outlive the transaction or leak through the connection pool.
- No tenant means an explicit empty value, which RLS policies treat as "no rows".
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import Connection, event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, SessionTransaction

TENANT_SETTING = "app.tenant_id"
_TENANT_INFO_KEY = "relay.tenant_id"


class TenantSession(Session):
    """Sync session behind every `AsyncSession`; carries the tenant in `info`."""


@event.listens_for(TenantSession, "after_begin")
def _apply_tenant_context(
    session: Session, _transaction: SessionTransaction, connection: Connection
) -> None:
    tenant_id = session.info.get(_TENANT_INFO_KEY)
    connection.execute(
        text("SELECT pg_catalog.set_config(:name, :value, true)"),
        {"name": TENANT_SETTING, "value": str(tenant_id) if tenant_id is not None else ""},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        sync_session_class=TenantSession,
        expire_on_commit=False,
    )


@asynccontextmanager
async def unit_of_work(
    factory: async_sessionmaker[AsyncSession], tenant_id: uuid.UUID | None
) -> AsyncIterator[AsyncSession]:
    """Open a session bound to `tenant_id` (or no tenant) and run one transaction.

    Commits on success, rolls back on error. Callers must not change the tenant of
    an open session; open a new unit of work instead.
    """
    if tenant_id is not None and not isinstance(tenant_id, uuid.UUID):
        raise TypeError("tenant_id must be a uuid.UUID")
    async with factory(info={_TENANT_INFO_KEY: tenant_id}) as session, session.begin():
        yield session
