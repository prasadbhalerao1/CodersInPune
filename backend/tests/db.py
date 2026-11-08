"""Test database locations and helpers. Tests always use real PostgreSQL."""

import os
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.platform.models import Tenant, TenantProbe
from relay.shared.db import unit_of_work

# Restricted application role: what the code under test connects as.
APP_URL = os.environ.get(
    "RELAY_TEST_DATABASE_URL",
    "postgresql+psycopg://relay_app:relay_app_dev@localhost:5432/relay_test",
)
# Owner role: migrations, truncation and catalog inspection only.
OWNER_URL = os.environ.get(
    "RELAY_TEST_MIGRATION_DATABASE_URL",
    "postgresql+psycopg://relay_owner:relay_owner_dev@localhost:5432/relay_test",
)
APP_ROLE = "relay_app"


def libpq_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


async def create_tenant(
    factory: async_sessionmaker[AsyncSession], name: str, probes: tuple[str, ...] = ()
) -> uuid.UUID:
    """Create a tenant (and optional probes) through the app role, inside its own context."""
    tenant_id = uuid.uuid7()
    async with unit_of_work(factory, tenant_id) as session:
        session.add(Tenant(id=tenant_id, name=name))
        await session.flush()
        session.add_all(TenantProbe(tenant_id=tenant_id, name=p) for p in probes)
    return tenant_id
