"""Notion integration: connect, fail-closed mapping, import, change detection, withdrawal."""

import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import psycopg
import pytest
from cryptography.fernet import Fernet

from relay.jobs import outbox
from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import INSPECTOR_URL, count_rows, libpq_url
from tests.fakes import FakeExternal, notion_page, notion_text

pytestmark = pytest.mark.anyio

SETTINGS = {
    "notion_client_id": "notion-client",
    "notion_client_secret": "notion-secret",
    "integration_encryption_key": Fernet.generate_key().decode(),
    "frontend_base_url": "https://relay.test",
}


@pytest.fixture
def ext() -> FakeExternal:
    runbook = notion_page("page-runbook", "Payments runbook")
    database = {
        "object": "database",
        "id": "db-procs",
        "url": "https://www.notion.so/db-procs",
        "last_edited_time": "2026-11-01T10:00:00.000Z",
        "archived": False,
        "parent": {"type": "workspace"},
        "title": [{"plain_text": "Procedures"}],
    }
    return FakeExternal(
        notion_shared=[runbook, database],
        notion_rows={
            "db-procs": [
                notion_page("row-1", "Rotate keys", database="db-procs"),
                notion_page("row-2", "Restore backups", database="db-procs"),
            ]
        },
        notion_blocks={
            "page-runbook": notion_text("Restart the payment worker.", "Page on-call."),
            "row-1": notion_text("Rotate quarterly."),
            "row-2": notion_text("Restore from the nightly snapshot."),
        },
    )


@pytest.fixture
async def api(ext: FakeExternal) -> AsyncIterator[Api]:
    async with make_api(ext, **SETTINGS) as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


async def run(api: Api, workspace: uuid.UUID) -> list[Any]:
    ctx = outbox.JobContext(
        http=api.app.state.http, settings=api.app.state.settings, jobs=api.app.state.jobs
    )
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        events = conn.execute(
            "SELECT id FROM platform.outbox_event WHERE tenant_id = %s AND processed_at IS NULL "
            "AND event_type = 'notion.sync_requested' AND (payload->>'reconcile') IS NULL "
            "ORDER BY id",
            (workspace,),
        ).fetchall()
    results: list[Any] = []
    for (event_id,) in events:
        try:
            results.append(
                await outbox.process(api.app.state.session_factory, workspace, event_id, ctx)
            )
        except Exception as exc:
            results.append(exc)
    return results


async def connect(api: Api, ws: Ws, ext: FakeExternal) -> None:
    started = await ws.call("POST", "/integrations/notion/connect")
    query = parse_qs(urlparse(started["authorize_url"]).query)
    assert (query["owner"], query["redirect_uri"]) == (
        ["user"],
        ["https://relay.test/integrations/notion/callback"],
    )
    ext.notion_codes["code-1"] = "secret_notion_token"
    response = await api.client.post(
        "/integrations/notion/complete",
        json={"state": query["state"][0], "code": "code-1"},
        headers=api.as_user(ws.sub),
    )
    assert response.status_code == 200
    await run(api, ws.id)


async def sources(ws: Ws) -> dict[str, dict[str, Any]]:
    return {s["title"]: s for s in (await ws.call("GET", "/integrations/notion"))["sources"]}


async def responsibility(ws: Ws, name: str = "Payments") -> str:
    created = await ws.call("POST", "/responsibilities", 201, json={"name": name})
    return str(created["id"])


async def map_source(ws: Ws, source: dict[str, Any], rid: str | None, vis: str | None) -> None:
    await ws.call(
        "PUT",
        f"/integrations/notion/sources/{source['id']}/mapping",
        204,
        json={"responsibility_id": rid, "visibility": vis},
    )


async def test_nothing_is_imported_until_an_admin_maps_a_source(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await connect(api, ws, ext)
    found = await sources(ws)
    assert set(found) == {"Payments runbook", "Procedures"}  # database rows aren't sources
    assert found["Procedures"]["kind"] == "database"
    assert count_rows("catalog.knowledge_item") == 0  # fail closed
    assert not any("/blocks/" in c for c in ext.notion_calls)  # page content never read
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        cipher = conn.execute(
            "SELECT token_ciphertext FROM integrations.notion_connection"
        ).fetchone()[0]  # type: ignore[index]
    assert "secret_notion_token" not in cipher
    assert "secret_notion_token" not in str(await ws.call("GET", "/integrations/notion"))


async def test_mapped_sources_import_as_unreviewed_knowledge_with_source_links(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await connect(api, ws, ext)
    rid = await responsibility(ws)
    found = await sources(ws)
    await map_source(ws, found["Payments runbook"], rid, "workspace")
    await map_source(ws, found["Procedures"], rid, "managers")
    assert await run(api, ws.id) == [True, True]

    items = {k["title"]: k for k in await ws.call("GET", f"/responsibilities/{rid}/knowledge")}
    assert set(items) == {"Payments runbook", "Rotate keys", "Restore backups"}
    runbook = items["Payments runbook"]
    assert (runbook["origin"], runbook["url"], runbook["freshness"]) == (
        "notion",
        "https://www.notion.so/page-runbook",
        "stale",  # imported text is unreviewed until a person confirms it
    )
    assert "Restart the payment worker." in runbook["body"]
    await ws.call("PATCH", f"/knowledge/{runbook['id']}", 409, json={"body": "edited in Relay"})
    reviewed = await ws.call("POST", f"/knowledge/{runbook['id']}/review")
    assert reviewed["freshness"] == "fresh"

    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    visible = {k["title"] for k in await member.call("GET", f"/responsibilities/{rid}/knowledge")}
    assert visible == {"Payments runbook"}  # the database was mapped managers-only
    hits = (await member.call("GET", "/knowledge", params={"q": "snapshot"}))["results"]
    assert hits == []

    summary = (await sources(ws))["Procedures"]
    assert (summary["imported_pages"], summary["responsibility_name"]) == (2, "Payments")


async def test_unchanged_pages_are_not_refetched_or_rewritten(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await connect(api, ws, ext)
    rid = await responsibility(ws)
    await map_source(ws, (await sources(ws))["Payments runbook"], rid, "workspace")
    await run(api, ws.id)
    [item] = await ws.call("GET", f"/responsibilities/{rid}/knowledge")
    await ws.call("POST", f"/knowledge/{item['id']}/review")
    fetches = sum("/blocks/" in c for c in ext.notion_calls)

    connection = (await ws.call("GET", "/integrations/notion"))["connections"][0]["id"]
    await ws.call("POST", f"/integrations/notion/connections/{connection}/sync", 202)
    await run(api, ws.id)
    assert sum("/blocks/" in c for c in ext.notion_calls) == fetches  # not even fetched

    ext.notion_shared[0]["last_edited_time"] = "2026-11-05T10:00:00.000Z"  # touched, same text
    await ws.call("POST", f"/integrations/notion/connections/{connection}/sync", 202)
    await run(api, ws.id)
    [same] = await ws.call("GET", f"/responsibilities/{rid}/knowledge")
    assert (same["updated_at"], same["freshness"]) == (item["updated_at"], "fresh")
    assert count_rows("catalog.knowledge_item") == 1  # no duplicates


async def test_changed_pages_need_review_and_deleted_pages_are_withdrawn(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await connect(api, ws, ext)
    rid = await responsibility(ws)
    found = await sources(ws)
    await map_source(ws, found["Payments runbook"], rid, "workspace")
    await map_source(ws, found["Procedures"], rid, "workspace")
    await run(api, ws.id)
    for k in await ws.call("GET", f"/responsibilities/{rid}/knowledge"):
        await ws.call("POST", f"/knowledge/{k['id']}/review")

    ext.notion_shared[0]["last_edited_time"] = "2026-11-06T10:00:00.000Z"
    ext.notion_blocks["page-runbook"] = notion_text("Restart the payment worker twice.")
    ext.notion_rows["db-procs"].pop()  # "Restore backups" deleted in Notion
    connection = (await ws.call("GET", "/integrations/notion"))["connections"][0]["id"]
    await ws.call("POST", f"/integrations/notion/connections/{connection}/sync", 202)
    await run(api, ws.id)

    items = {k["title"]: k for k in await ws.call("GET", f"/responsibilities/{rid}/knowledge")}
    assert set(items) == {"Payments runbook", "Rotate keys"}
    assert items["Payments runbook"]["freshness"] == "stale"  # changed: needs review again
    assert "twice" in items["Payments runbook"]["body"]
    assert items["Rotate keys"]["freshness"] == "fresh"
    assert count_rows("catalog.knowledge_item", "status = 'withdrawn'") == 1
    assert (await sources(ws))["Procedures"]["withdrawn_pages"] == 1

    ext.notion_shared.pop(0)  # the runbook is unshared from Relay
    await ws.call("POST", f"/integrations/notion/connections/{connection}/sync", 202)
    await run(api, ws.id)
    assert (await sources(ws))["Payments runbook"]["removed"] is True
    titles = [k["title"] for k in await ws.call("GET", f"/responsibilities/{rid}/knowledge")]
    assert titles == ["Rotate keys"]


async def test_unmapping_withdraws_and_remapping_rescopes(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await connect(api, ws, ext)
    payments, billing = await responsibility(ws), await responsibility(ws, "Billing")
    source = (await sources(ws))["Payments runbook"]
    await map_source(ws, source, payments, "workspace")
    await run(api, ws.id)

    await map_source(ws, source, billing, "managers")  # takes effect immediately
    assert await ws.call("GET", f"/responsibilities/{payments}/knowledge") == []
    [moved] = await ws.call("GET", f"/responsibilities/{billing}/knowledge")
    assert moved["visibility"] == "managers"

    await map_source(ws, source, None, None)
    assert await ws.call("GET", f"/responsibilities/{billing}/knowledge") == []
    await ws.call(
        "PUT",
        f"/integrations/notion/sources/{source['id']}/mapping",
        422,
        json={"responsibility_id": payments, "visibility": None},
    )
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        actions = [
            r[0]
            for r in conn.execute(
                "SELECT action FROM audit.audit_event WHERE action LIKE 'integration.notion%%' "
                "ORDER BY occurred_at, id"
            )
        ]
    assert actions.count("integration.notion_source_mapped") == 2
    assert "integration.notion_source_unmapped" in actions


async def test_revoked_failed_disconnected_admin_only_and_isolated(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await connect(api, ws, ext)
    connection = (await ws.call("GET", "/integrations/notion"))["connections"][0]["id"]
    ext.notion_down = True
    await ws.call("POST", f"/integrations/notion/connections/{connection}/sync", 202)
    [failure] = await run(api, ws.id)
    assert isinstance(failure, Exception)  # transient: the job retries
    ext.notion_down = False
    assert await run(api, ws.id) == [True]

    ext.notion_tokens.clear()
    ext.notion_refresh.clear()
    await ws.call("POST", f"/integrations/notion/connections/{connection}/sync", 202)
    await run(api, ws.id)
    [revoked] = (await ws.call("GET", "/integrations/notion"))["connections"]
    assert (revoked["status"], revoked["last_sync_error"]) == (
        "revoked",
        "Notion access was revoked. Reconnect Notion.",
    )
    await ws.call("POST", f"/integrations/notion/connections/{connection}/sync", 409)
    await ws.call("POST", f"/integrations/notion/connections/{connection}/disconnect", 204)
    assert count_rows("integrations.notion_connection", "token_ciphertext IS NOT NULL") == 0

    await add_member(api, ws.id, "user_member", "member")
    await Ws(api, ws.id, "user_member").call("GET", "/integrations/notion", 403)
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    assert (await other.call("GET", "/integrations/notion"))["sources"] == []


async def test_not_configured_without_an_encryption_key(ext: FakeExternal) -> None:
    async with make_api(ext, notion_client_id="x", notion_client_secret="y") as unconfigured:
        ws = Ws(unconfigured, await unconfigured.create_workspace(OWNER, "Acme"))
        assert (await ws.call("GET", "/integrations/notion"))["configured"] is False
        await ws.call("POST", "/integrations/notion/connect", 503)
