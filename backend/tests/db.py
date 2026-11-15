"""Test database locations and helpers. Tests always use real PostgreSQL."""

import os
import uuid

import psycopg
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
# Bootstrap superuser: used ONLY by assertions that must count rows regardless of RLS
# (e.g. "nothing was half-written"). Never used by code under test.
INSPECTOR_URL = os.environ.get(
    "RELAY_TEST_INSPECTOR_DATABASE_URL",
    "postgresql://postgres:postgres_dev@localhost:5432/relay_test",
)
APP_ROLE = "relay_app"


def libpq_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def count_rows(table: str, where: str = "true", params: tuple[object, ...] = ()) -> int:
    """Count rows bypassing RLS. `table` and `where` are test-authored literals."""
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        row = conn.execute(f"SELECT count(*) FROM {table} WHERE {where}", params).fetchone()  # noqa: S608
    assert row is not None
    return int(row[0])


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
