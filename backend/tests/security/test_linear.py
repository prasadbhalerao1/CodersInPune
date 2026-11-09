"""Linear integration: OAuth connect, encrypted token, sync, identities, signals, safety."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import psycopg
import pytest
from cryptography.fernet import Fernet

from relay.jobs import outbox
from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import INSPECTOR_URL, count_rows, libpq_url
from tests.fakes import FakeExternal, linear_issue

pytestmark = pytest.mark.anyio
RECENT = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")


@pytest.fixture
def ext() -> FakeExternal:
    return FakeExternal(
        linear_data={
            "teams": [{"id": "team-1", "key": "PAY", "name": "Payments"}],
            "projects": [
                {
                    "id": "proj-1",
                    "name": "Checkout v2",
                    "state": "started",
                    "url": "https://linear.app/acme/project/checkout",
                    "lead": {"id": "lu-bea"},
                    "teams": {"nodes": [{"id": "team-1"}]},
                }
            ],
            "users": [
                {
                    "id": "lu-bea",
                    "name": "Bea Ray",
                    "displayName": "bea",
                    "email": "Bea@Acme.test",
                    "active": True,
                },
                {
                    "id": "lu-cy",
                    "name": "Cy",
                    "displayName": "cy",
                    "email": "cy@acme.test",
                    "active": True,
                },
            ],
            "issues": [
                linear_issue("PAY-1", priority=1, updated=RECENT),
                linear_issue("PAY-2", updated=RECENT),
                linear_issue("PAY-3", assignee="lu-cy", updated=RECENT),
                linear_issue("PAY-4", updated="2020-01-01T00:00:00.000Z"),  # outside the window
            ],
        }
    )


SETTINGS = {
    "linear_client_id": "lin-client",
    "linear_client_secret": "lin-secret",
    "integration_encryption_key": Fernet.generate_key().decode(),
    "frontend_base_url": "https://relay.test",
}


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
            "AND event_type = 'linear.sync_requested' AND (payload->>'reconcile') IS NULL "
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


async def connect(api: Api, ws: Ws, ext: FakeExternal, code: str = "code-1") -> Any:
    started = await ws.call("POST", "/integrations/linear/connect")
    url = urlparse(started["authorize_url"])
    query = parse_qs(url.query)
    assert (query["scope"], query["redirect_uri"]) == (
        ["read"],
        ["https://relay.test/integrations/linear/callback"],
    )
    ext.linear_codes[code] = f"lin_token_{code}"
    return await api.client.post(
        "/integrations/linear/complete",
        json={"state": query["state"][0], "code": code},
        headers=api.as_user(ws.sub),
    )


async def test_connect_stores_an_encrypted_token_and_syncs_metadata_only(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    assert (await connect(api, ws, ext)).status_code == 200
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        cipher = conn.execute(
            "SELECT token_ciphertext FROM integrations.linear_connection"
        ).fetchone()[0]  # type: ignore[index]
    assert cipher
    assert "lin_token" not in cipher  # encrypted at rest
    assert await run(api, ws.id) == [True]

    view = await ws.call("GET", "/integrations/linear")
    [connection] = view["connections"]
    assert (connection["organization_name"], connection["last_sync_status"]) == (
        "Acme Linear",
        "ok",
    )
    assert connection["next_reconcile_at"]  # reconciliation scheduled
    assert "token" not in str(view).lower().replace("next_reconcile", "")
    [project] = view["projects"]
    assert (project["name"], project["lead"], project["recent_issues"]) == ("Checkout v2", "bea", 3)
    assert count_rows("integrations.linear_issue") == 3  # only the activity window
    assert not any("description" in q for q in ext.linear_queries)
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        leaked = conn.execute(
            "SELECT count(*) FROM integrations.linear_issue t WHERE t::text LIKE '%%SECRET%%'"
        ).fetchone()[0]  # type: ignore[index]
    assert leaked == 0
    pending = count_rows(
        "platform.outbox_event", "event_type = 'linear.sync_requested' AND processed_at IS NULL"
    )
    assert pending == 1  # one scheduled reconciliation, not one per sync


async def test_state_is_single_use_and_bound_to_the_user(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    started = await ws.call("POST", "/integrations/linear/connect")
    state = parse_qs(urlparse(started["authorize_url"]).query)["state"][0]
    ext.linear_codes["c"] = "lin_token_c"
    await add_member(api, ws.id, "user_admin", "admin")
    stolen = await api.client.post(
        "/integrations/linear/complete",
        json={"state": state, "code": "c"},
        headers=api.as_user("user_admin"),
    )
    assert stolen.status_code == 400
    ok = await api.client.post(
        "/integrations/linear/complete",
        json={"state": state, "code": "c"},
        headers=api.as_user(OWNER),
    )
    assert ok.status_code == 200
    again = await api.client.post(
        "/integrations/linear/complete",
        json={"state": state, "code": "c"},
        headers=api.as_user(OWNER),
    )
    assert again.status_code == 400


async def test_identities_are_suggested_never_linked_automatically(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    bea = await ws.call(
        "POST", "/people", 201, json={"display_name": "Bea Ray", "email": "bea@acme.test"}
    )
    await connect(api, ws, ext)
    await run(api, ws.id)
    identities = {i["name"]: i for i in await ws.call("GET", "/integrations/linear/identities")}
    assert identities["bea"]["link_status"] == "suggested"
    assert identities["bea"]["suggested_person"]["id"] == bea["id"]
    assert identities["bea"]["person"] is None
    assert identities["cy"]["link_status"] == "unmatched"

    path = "/integrations/linear/identities/{}/decision"
    await ws.call(
        "POST",
        path.format(identities["bea"]["id"]),
        json={"action": "link", "person_id": bea["id"]},
    )
    await ws.call(
        "POST",
        path.format(identities["cy"]["id"]),
        409,
        json={"action": "link", "person_id": bea["id"]},
    )
    await run(api, ws.id)  # a re-sync keeps human decisions
    again = {i["name"]: i for i in await ws.call("GET", "/integrations/linear/identities")}
    assert again["bea"]["link_status"] == "linked"


async def test_signals_explain_unowned_important_work_and_change_nothing(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await connect(api, ws, ext)
    await run(api, ws.id)
    [signal] = await ws.call("GET", "/integrations/linear/signals")
    assert signal["kind"] == "unowned_important"
    assert signal["evidence"][0]["url"] == "https://linear.app/acme/issue/PAY-1"

    project = (await ws.call("GET", "/integrations/linear"))["projects"][0]
    await ws.call(
        "POST",
        f"/integrations/linear/projects/{project['id']}/link",
        204,
        json={"action": "create"},
    )
    signals = await ws.call("GET", "/integrations/linear/signals")
    assert [s["kind"] for s in signals] == ["unowned_important"]  # no primary owner yet
    assert "no primary owner" in signals[0]["explanation"]
    responsibilities = await ws.call("GET", "/responsibilities")
    assert [r["primary_owner"] for r in responsibilities] == [None]  # nothing assigned for you


async def test_revoked_failed_and_disconnected(api: Api, ws: Ws, ext: FakeExternal) -> None:
    await connect(api, ws, ext)
    ext.linear_down = True
    [failure] = await run(api, ws.id)
    assert isinstance(failure, Exception)  # transient: the job retries
    ext.linear_down = False
    assert await run(api, ws.id) == [True]  # the retried attempt succeeds

    ext.linear_tokens.clear()  # access revoked in Linear
    connection = (await ws.call("GET", "/integrations/linear"))["connections"][0]
    await ws.call("POST", f"/integrations/linear/connections/{connection['id']}/sync", 202)
    await run(api, ws.id)
    [revoked] = (await ws.call("GET", "/integrations/linear"))["connections"]
    assert (revoked["status"], revoked["last_sync_error"]) == (
        "revoked",
        "Linear access was revoked. Reconnect Linear.",
    )
    await ws.call("POST", f"/integrations/linear/connections/{connection['id']}/sync", 409)

    await ws.call("POST", f"/integrations/linear/connections/{connection['id']}/disconnect", 204)
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        assert conn.execute(
            "SELECT token_ciphertext FROM integrations.linear_connection"
        ).fetchone() == (None,)


async def test_admin_only_and_isolated(api: Api, ws: Ws, ext: FakeExternal) -> None:
    await connect(api, ws, ext)
    await run(api, ws.id)
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    for path in ("", "/identities", "/signals"):
        await member.call("GET", f"/integrations/linear{path}", 403)
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    assert (await other.call("GET", "/integrations/linear"))["projects"] == []
    assert await other.call("GET", "/integrations/linear/identities") == []
    identity = (await ws.call("GET", "/integrations/linear/identities"))[0]["id"]
    await other.call(
        "POST",
        f"/integrations/linear/identities/{identity}/decision",
        404,
        json={"action": "dismiss"},
    )


async def test_not_configured_without_an_encryption_key(ext: FakeExternal) -> None:
    async with make_api(ext, linear_client_id="x", linear_client_secret="y") as unconfigured:
        ws = Ws(unconfigured, await unconfigured.create_workspace(OWNER, "Acme"))
        assert (await ws.call("GET", "/integrations/linear"))["configured"] is False
        await ws.call("POST", "/integrations/linear/connect", 503)
