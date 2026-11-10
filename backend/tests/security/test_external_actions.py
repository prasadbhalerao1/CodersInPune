"""Approved external task actions: gated, human-approved, idempotent across timeouts,
recorded with a receipt, and reconciled from the provider."""

import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import psycopg
import pytest

from relay.jobs import outbox
from tests.api import OWNER, Api, Ws, make_api
from tests.db import INSPECTOR_URL, OWNER_URL, libpq_url
from tests.fakes import FakeExternal
from tests.security.test_cases import iso
from tests.security.test_linear import SETTINGS
from tests.security.test_linear import ext as ext

pytestmark = pytest.mark.anyio
WRITES = {**SETTINGS, "linear_issue_writes": True, "linear_oauth_scope": "read,issues:create"}


@pytest.fixture
async def api(ext: FakeExternal) -> AsyncIterator[Api]:
    async with make_api(ext, **WRITES) as a:
        yield a


async def drain(api: Api, workspace: uuid.UUID, event_type: str) -> None:
    """Run every pending event of a type now (scheduled ones included)."""
    ctx = outbox.JobContext(
        http=api.app.state.http, settings=api.app.state.settings, jobs=api.app.state.jobs
    )
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        events = conn.execute(
            "SELECT id FROM platform.outbox_event WHERE tenant_id = %s AND processed_at IS NULL "
            "AND event_type = %s ORDER BY id",
            (workspace, event_type),
        ).fetchall()
    for (event_id,) in events:
        await outbox.process(api.app.state.session_factory, workspace, event_id, ctx)


async def connect_linear(api: Api, ws: Ws, ext: FakeExternal) -> None:
    started = await ws.call("POST", "/integrations/linear/connect")
    query = parse_qs(urlparse(started["authorize_url"]).query)
    assert query["scope"] == ["read,issues:create"]
    ext.linear_codes["code-1"] = "lin_token_1"
    response = await api.client.post(
        "/integrations/linear/complete",
        json={"state": query["state"][0], "code": "code-1"},
        headers=api.as_user(ws.sub),
    )
    assert response.status_code == 200, response.text
    await drain(api, ws.id, "linear.sync_requested")


async def task(ws: Ws) -> tuple[str, str]:
    case = await ws.call(
        "POST", "/cases", 201, json={"case_type": "transfer", "title": "T", "starts_at": iso()}
    )
    case = await ws.call("POST", f"/cases/{case['id']}/tasks", 201, json={"title": "Rotate keys"})
    return case["id"], case["tasks"][0]["id"]


async def test_disabled_until_the_provider_permission_is_configured(ext: FakeExternal) -> None:
    async with make_api(ext, **SETTINGS) as api:
        ws = Ws(api, await api.create_workspace(OWNER, "Acme"))
        targets = await ws.call("GET", "/external-targets")
        assert not targets["linear_enabled"]
        assert "RELAY_LINEAR_ISSUE_WRITES" in targets["linear_blocker"]
        case_id, task_id = await task(ws)
        blocked = await ws.call(
            "POST",
            f"/cases/{case_id}/tasks/{task_id}/external",
            409,
            json={"provider": "linear", "target": "team-1", "title": "Rotate keys"},
        )
        assert blocked["code"] == "writes_disabled"


async def test_timeout_is_recovered_without_a_duplicate(api: Api, ext: FakeExternal) -> None:
    ws = Ws(api, await api.create_workspace(OWNER, "Acme"))
    await connect_linear(api, ws, ext)
    targets = await ws.call("GET", "/external-targets")
    assert [t["label"] for t in targets["targets"]] == ["PAY · Payments"]
    case_id, task_id = await task(ws)
    content = {"provider": "linear", "target": "team-1", "title": "Rotate keys", "body": "Steps"}

    ext.linear_create_timeouts = 1  # Linear accepts the issue but the response is lost
    action = await ws.call("POST", f"/cases/{case_id}/tasks/{task_id}/external", 201, json=content)
    assert action["state"] == "approved"
    await ws.call("POST", f"/cases/{case_id}/tasks/{task_id}/external", 409, json=content)
    await drain(api, ws.id, "external.execute")
    [after_timeout] = await ws.call("GET", f"/cases/{case_id}/tasks/{task_id}/external")
    assert after_timeout["state"] == "uncertain"

    await drain(api, ws.id, "external.execute")  # the scheduled re-check finds it
    [done] = await ws.call("GET", f"/cases/{case_id}/tasks/{task_id}/external")
    assert done["state"] == "succeeded"
    assert done["receipt"]["recovered_existing"] is True
    assert len(ext.linear_created) == 1  # no duplicate
    assert ext.linear_created[0]["description"].startswith("Steps")
    detail: Any = await ws.call("GET", f"/cases/{case_id}/tasks/{task_id}")
    assert detail["task"]["sync_status"] == "synced"
    assert detail["task"]["external_url"] == done["external_url"]

    # Closing it in Linear completes the Relay task when reconciled.
    ext.linear_created[0]["state"] = {"type": "completed"}
    await ws.call("POST", f"/external-actions/{done['id']}/check")
    detail = await ws.call("GET", f"/cases/{case_id}/tasks/{task_id}")
    assert detail["task"]["status"] == "done"


async def test_connector_health_pause_and_run_history(api: Api, ext: FakeExternal) -> None:
    ws = Ws(api, await api.create_workspace(OWNER, "Acme"))
    await connect_linear(api, ws, ext)
    [linear] = await ws.call("GET", "/integrations/health")
    assert linear["health"] == "healthy"
    assert [r["status"] for r in linear["runs"]] == ["ok"]
    assert linear["failure_rate"] == 0

    paused = await ws.call("POST", f"/integrations/linear/{linear['ref']}/pause")
    assert paused[0]["health"] == "paused"
    await ws.call("POST", f"/integrations/linear/connections/{linear['ref']}/sync", 202)
    await drain(api, ws.id, "linear.sync_requested")
    [skipped] = await ws.call("GET", "/integrations/health")
    assert skipped["runs"][0]["status"] == "skipped"

    await ws.call("POST", f"/integrations/linear/{linear['ref']}/resume")
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(ws.id),))
        conn.execute(
            "UPDATE integrations.linear_connection SET status = 'revoked', "
            "last_sync_status = 'error', last_sync_error = 'Linear access was revoked.'"
        )
    [revoked] = await ws.call("GET", "/integrations/health")
    assert revoked["health"] == "revoked"
    assert "Reconnect" in revoked["advice"]
