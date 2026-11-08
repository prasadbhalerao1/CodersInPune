"""Session lifecycle and transaction-local request context.

Rules (see CLAUDE.md guardrails):
- One `AsyncSession` per request or job; never shared across concurrent tasks.
- The tenant and the principal are fixed when the session is created and applied at the
  start of *every* transaction with `set_config(..., true)`, so they can never outlive the
  transaction or leak through the connection pool.
- Unset values are written as an explicit empty string, which policies treat as "none".

`app.tenant_id` selects tenant-scoped rows. `app.principal` is the verified WorkOS user ID
of the caller; identity policies use it so a user can see only their own account and
memberships. HTTP handlers must obtain sessions from the workspace dependency, which sets
the tenant only after verifying an active membership.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import Connection, event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, SessionTransaction

TENANT_SETTING = "app.tenant_id"
PRINCIPAL_SETTING = "app.principal"
_TENANT_INFO_KEY = "relay.tenant_id"
_PRINCIPAL_INFO_KEY = "relay.principal"
_MAX_PRINCIPAL_LENGTH = 255


class TenantSession(Session):
    """Sync session behind every `AsyncSession`; carries request context in `info`."""


@event.listens_for(TenantSession, "after_begin")
def _apply_request_context(
    session: Session, _transaction: SessionTransaction, connection: Connection
) -> None:
    tenant_id = session.info.get(_TENANT_INFO_KEY)
    principal = session.info.get(_PRINCIPAL_INFO_KEY)
    connection.execute(
        text(
            "SELECT pg_catalog.set_config(:tenant_name, :tenant, true), "
            "pg_catalog.set_config(:principal_name, :principal, true)"
        ),
        {
            "tenant_name": TENANT_SETTING,
            "tenant": str(tenant_id) if tenant_id is not None else "",
            "principal_name": PRINCIPAL_SETTING,
            "principal": principal or "",
        },
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        sync_session_class=TenantSession,
        expire_on_commit=False,
    )


async def establish_tenant_context(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Bind a session that started without a tenant to `tenant_id`, once.

    Only for the workspace-access dependency, after it has verified an active
    membership inside the same transaction. Rebinding to another tenant is refused.
    """
    if not isinstance(tenant_id, uuid.UUID):
        raise TypeError("tenant_id must be a uuid.UUID")
    current = session.info.get(_TENANT_INFO_KEY)
    if current is not None:
        if current == tenant_id:
            return
        raise RuntimeError("session is already bound to a different tenant")
    session.info[_TENANT_INFO_KEY] = tenant_id
    await session.execute(
        text("SELECT pg_catalog.set_config(:name, :value, true)"),
        {"name": TENANT_SETTING, "value": str(tenant_id)},
    )


@asynccontextmanager
async def unit_of_work(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID | None,
    principal: str | None = None,
) -> AsyncIterator[AsyncSession]:
    """Open a session bound to `tenant_id`/`principal` and run one transaction.

    Commits on success, rolls back on error. Callers must not change the context of an
    open session; open a new unit of work instead.
    """
    if tenant_id is not None and not isinstance(tenant_id, uuid.UUID):
        raise TypeError("tenant_id must be a uuid.UUID")
    if principal is not None and (
        not isinstance(principal, str) or not 0 < len(principal) <= _MAX_PRINCIPAL_LENGTH
    ):
        raise ValueError("principal must be a non-empty string of at most 255 characters")
    info = {_TENANT_INFO_KEY: tenant_id, _PRINCIPAL_INFO_KEY: principal}
    async with factory(info=info) as session, session.begin():
        yield session
