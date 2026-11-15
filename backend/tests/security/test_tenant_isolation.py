"""Mandatory tenant-isolation tests (Register D11, Q-F). Real PostgreSQL, app role only."""

import uuid
from collections.abc import Sequence

import anyio
import anyio.lowlevel
import psycopg
import pytest
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.platform.models import Tenant, TenantProbe, TenantProbeItem
from relay.shared.db import create_engine, create_session_factory, unit_of_work
from tests.conftest import make_settings
from tests.db import APP_ROLE, create_tenant

pytestmark = pytest.mark.anyio

TENANT_TABLES = (Tenant, TenantProbe, TenantProbeItem)


async def probe_names(session: AsyncSession) -> list[str]:
    result = await session.scalars(select(TenantProbe.name).order_by(TenantProbe.name))
    return list(result)


async def row_counts(session: AsyncSession) -> Sequence[int]:
    return [
        await session.scalar(select(func.count()).select_from(model)) or 0
        for model in TENANT_TABLES
    ]


async def probe_id(factory: async_sessionmaker[AsyncSession], tenant: uuid.UUID) -> uuid.UUID:
    async with unit_of_work(factory, tenant) as session:
        return (await session.scalars(select(TenantProbe.id).limit(1))).one()


def assert_rls_violation(error: DBAPIError) -> None:
    assert isinstance(error.orig, psycopg.errors.InsufficientPrivilege)
    assert "row-level security" in str(error.orig)


async def test_tests_run_as_restricted_application_role(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with unit_of_work(session_factory, None) as session:
        row = (
            await session.execute(
                text(
                    "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles "
                    "WHERE rolname = current_user"
                )
            )
        ).one()
        owned = await session.scalar(
            text("SELECT count(*) FROM pg_tables WHERE tableowner = current_user")
        )
    assert tuple(row) == (APP_ROLE, False, False)
    assert owned == 0


async def test_missing_tenant_context_returns_zero_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await create_tenant(session_factory, "A", probes=("a1",))
    await create_tenant(session_factory, "B", probes=("b1",))

    async with unit_of_work(session_factory, None) as session:
        assert await row_counts(session) == [0, 0, 0]
        assert await session.scalar(text("SELECT current_setting('app.tenant_id', true)")) == ""


async def test_missing_tenant_context_cannot_write(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_a = await create_tenant(session_factory, "A")
    with pytest.raises(DBAPIError) as excinfo:
        async with unit_of_work(session_factory, None) as session:
            session.add(TenantProbe(tenant_id=tenant_a, name="orphan"))
    assert_rls_violation(excinfo.value)


async def test_tenant_reads_only_its_own_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_a = await create_tenant(session_factory, "A", probes=("a1", "a2"))
    tenant_b = await create_tenant(session_factory, "B", probes=("b1",))

    async with unit_of_work(session_factory, tenant_a) as session:
        assert await probe_names(session) == ["a1", "a2"]
        assert list(await session.scalars(select(Tenant.id))) == [tenant_a]
        # Direct lookup by another tenant's primary key finds nothing.
        assert await session.get(Tenant, tenant_b) is None


async def test_tenant_cannot_insert_rows_for_another_tenant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_a = await create_tenant(session_factory, "A")
    tenant_b = await create_tenant(session_factory, "B")

    with pytest.raises(DBAPIError) as excinfo:
        async with unit_of_work(session_factory, tenant_a) as session:
            session.add(TenantProbe(tenant_id=tenant_b, name="smuggled"))
    assert_rls_violation(excinfo.value)


async def test_tenant_cannot_update_or_delete_another_tenants_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_a = await create_tenant(session_factory, "A")
    tenant_b = await create_tenant(session_factory, "B", probes=("b1",))
    b_probe = await probe_id(session_factory, tenant_b)

    async with unit_of_work(session_factory, tenant_a) as session:
        updated = await session.execute(
            update(TenantProbe).where(TenantProbe.id == b_probe).values(name="hijacked")
        )
        deleted = await session.execute(delete(TenantProbe).where(TenantProbe.id == b_probe))
        renamed = await session.execute(
            update(Tenant).where(Tenant.id == tenant_b).values(name="hijacked")
        )
    assert (updated.rowcount, deleted.rowcount, renamed.rowcount) == (0, 0, 0)  # type: ignore[attr-defined]

    async with unit_of_work(session_factory, tenant_b) as session:
        assert await probe_names(session) == ["b1"]
        assert (await session.get_one(Tenant, tenant_b)).name == "B"


async def test_tenant_cannot_move_its_row_into_another_tenant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    tenant_a = await create_tenant(session_factory, "A", probes=("a1",))
    tenant_b = await create_tenant(session_factory, "B")
    a_probe = await probe_id(session_factory, tenant_a)

    with pytest.raises(DBAPIError) as excinfo:
        async with unit_of_work(session_factory, tenant_a) as session:
            await session.execute(
                update(TenantProbe).where(TenantProbe.id == a_probe).values(tenant_id=tenant_b)
            )
    assert_rls_violation(excinfo.value)


async def test_cross_tenant_reference_is_rejected_by_composite_foreign_key(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Foreign-key checks bypass RLS, so only the composite (tenant_id, probe_id) key
    # stops tenant A from attaching a row to tenant B's parent.
    tenant_a = await create_tenant(session_factory, "A")
    tenant_b = await create_tenant(session_factory, "B", probes=("b1",))
    b_probe = await probe_id(session_factory, tenant_b)

    with pytest.raises(DBAPIError) as excinfo:
        async with unit_of_work(session_factory, tenant_a) as session:
            session.add(TenantProbeItem(tenant_id=tenant_a, probe_id=b_probe, label="x"))
    assert isinstance(excinfo.value.orig, psycopg.errors.ForeignKeyViolation)


async def test_same_natural_key_is_allowed_in_different_tenants(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Uniqueness is tenant-prefixed: no cross-tenant collisions, so no existence leaks.
    await create_tenant(session_factory, "A", probes=("deploys",))
    await create_tenant(session_factory, "B", probes=("deploys",))


async def test_tenant_context_does_not_leak_between_pooled_connections() -> None:
    engine = create_engine(make_settings(db_pool_size=1, db_max_overflow=0))
    factory = create_session_factory(engine)
    try:
        tenant_a = await create_tenant(factory, "A", probes=("a1",))

        async with unit_of_work(factory, tenant_a) as session:
            pid_a = await session.scalar(text("SELECT pg_backend_pid()"))
            assert await probe_names(session) == ["a1"]
            # Simulate a bug: a session-level (non-local) SET that outlives the transaction.
            await session.execute(text(f"SET app.tenant_id = '{tenant_a}'"))

        async with unit_of_work(factory, None) as session:
            assert await session.scalar(text("SELECT pg_backend_pid()")) == pid_a
            assert await row_counts(session) == [0, 0, 0]
    finally:
        await engine.dispose()


async def test_concurrent_units_of_work_stay_isolated() -> None:
    engine = create_engine(make_settings(db_pool_size=2, db_max_overflow=0))
    factory = create_session_factory(engine)
    try:
        tenants = {
            await create_tenant(factory, "A", probes=("a1",)): ["a1"],
            await create_tenant(factory, "B", probes=("b1",)): ["b1"],
        }

        async def read_repeatedly(tenant: uuid.UUID, expected: list[str]) -> None:
            for _ in range(25):
                async with unit_of_work(factory, tenant) as session:
                    assert await probe_names(session) == expected
                await anyio.lowlevel.checkpoint()

        async with anyio.create_task_group() as tg:
            for tenant, expected in tenants.items():
                tg.start_soon(read_repeatedly, tenant, expected)
    finally:
        await engine.dispose()


async def test_unit_of_work_rejects_non_uuid_tenant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(TypeError):
        async with unit_of_work(session_factory, "not-a-uuid"):  # type: ignore[arg-type]
            pass
