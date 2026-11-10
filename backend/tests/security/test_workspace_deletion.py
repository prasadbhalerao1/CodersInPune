"""Workspace deletion: owner-only scheduling, cancel, and an owner-role purge that
removes the workspace (audit log included) only after the grace period."""

from collections.abc import AsyncIterator

import psycopg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from relay.platform.deletion import purge_due
from relay.shared.db.session import create_session_factory
from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import INSPECTOR_URL, OWNER_URL, count_rows, libpq_url

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


async def _purge() -> list[object]:
    engine = create_async_engine(OWNER_URL, connect_args={"prepare_threshold": None})
    try:
        return list(await purge_due(create_session_factory(engine)))
    finally:
        await engine.dispose()


async def test_schedule_cancel_and_purge_after_grace(api: Api) -> None:
    ws = Ws(api, await api.create_workspace(OWNER, "Acme"))
    keep = Ws(api, await api.create_workspace(OWNER, "Keep"))
    await ws.responsibility("Payroll")
    await keep.responsibility("Billing")
    await add_member(api, ws.id, "user_admin", "admin")
    admin = Ws(api, ws.id, "user_admin")

    await admin.call("POST", "/deletion", 403, json={"confirm_name": "Acme"})
    await ws.call("POST", "/deletion", 422, json={"confirm_name": "acme"})
    scheduled = await ws.call("POST", "/deletion", json={"confirm_name": "Acme"})
    assert scheduled["scheduled_for"] is not None
    await ws.call("POST", "/deletion", 409, json={"confirm_name": "Acme"})
    assert (await ws.call("GET", ""))["deletion_scheduled_for"] == scheduled["scheduled_for"]

    # Within the grace period nothing is purged, and the audit log stays append-only.
    assert await _purge() == []
    with (
        pytest.raises(psycopg.errors.InsufficientPrivilege),
        psycopg.connect(libpq_url(INSPECTOR_URL)) as conn,
    ):
        conn.execute("DELETE FROM audit.audit_event WHERE tenant_id = %s", (ws.id,))

    await ws.call("DELETE", "/deletion")
    assert (await ws.call("GET", ""))["deletion_scheduled_for"] is None
    await ws.call("POST", "/deletion", json={"confirm_name": "Acme"})

    with psycopg.connect(libpq_url(INSPECTOR_URL), autocommit=True) as conn:
        conn.execute(
            "UPDATE platform.tenant SET deletion_requested_at = now() - interval '31 days' "
            "WHERE id = %s",
            (ws.id,),
        )
    assert await _purge() == [ws.id]
    for table in ("platform.tenant", "catalog.responsibility", "audit.audit_event"):
        column = "id" if table == "platform.tenant" else "tenant_id"
        assert count_rows(table, f"{column} = %s", (ws.id,)) == 0
        assert count_rows(table, f"{column} = %s", (keep.id,)) > 0
    await ws.call("GET", "", 404)
