"""A retried or double-submitted create returns the first result instead of a duplicate."""

from collections.abc import AsyncIterator

import pytest

from tests.api import OWNER, Api, Ws, make_api
from tests.security.test_cases import iso

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


def _headers(api: Api, key: str) -> dict[str, str]:
    return {**api.as_user(OWNER), "Idempotency-Key": key}


async def test_same_key_creates_once_and_a_different_payload_is_rejected(api: Api, ws: Ws) -> None:
    body = {"case_type": "transfer", "title": "Payments handover", "starts_at": iso()}
    url = f"/workspaces/{ws.id}/cases"
    first = await api.client.post(url, json=body, headers=_headers(api, "key-0001-abcd"))
    again = await api.client.post(url, json=body, headers=_headers(api, "key-0001-abcd"))
    assert (first.status_code, again.status_code) == (201, 201)
    assert first.json()["id"] == again.json()["id"]
    titles = [c["title"] for c in await ws.call("GET", "/cases")]
    assert titles.count("Payments handover") == 1

    changed = await api.client.post(
        url, json={**body, "title": "Something else"}, headers=_headers(api, "key-0001-abcd")
    )
    assert changed.status_code == 422
    assert changed.json()["code"] == "idempotency_key_reused"

    # Tasks: a double-submitted task is added once.
    cid = first.json()["id"]
    task_url = f"{url}/{cid}/tasks"
    for _ in range(2):
        r = await api.client.post(
            task_url, json={"title": "Walk the runbook"}, headers=_headers(api, "task-key-0001")
        )
        assert r.status_code == 201
    assert [t["title"] for t in r.json()["tasks"]] == ["Walk the runbook"]

    # No key: behaves as before (a second create is a separate request).
    plain = await ws.call("POST", "/responsibilities", 201, json={"name": "Ledger"})
    other = await ws.call("POST", "/responsibilities", 201, json={"name": "Ledger 2"})
    assert plain["id"] != other["id"]


async def test_people_assets_and_knowledge_are_created_once(api: Api, ws: Ws) -> None:
    base = f"/workspaces/{ws.id}"
    rid = (await ws.call("POST", "/responsibilities", 201, json={"name": "Payments"}))["id"]
    creates = [
        ("/people", {"display_name": "Asha Rao"}, "person-key-0001"),
        ("/assets", {"name": "payments-api", "asset_type": "repository"}, "asset-key-0001"),
        (
            f"/responsibilities/{rid}/knowledge",
            {"kind": "procedure", "title": "Rotate keys", "body": "Monthly, from the vault."},
            "knowledge-key-0001",
        ),
    ]
    for path, body, key in creates:
        first = await api.client.post(base + path, json=body, headers=_headers(api, key))
        again = await api.client.post(base + path, json=body, headers=_headers(api, key))
        assert (first.status_code, again.status_code) == (201, 201), path
        assert first.json()["id"] == again.json()["id"], path

    people = await ws.call("GET", "/people")
    assert [p["display_name"] for p in people].count("Asha Rao") == 1
    knowledge = await ws.call("GET", f"/responsibilities/{rid}/knowledge")
    assert [k["title"] for k in knowledge] == ["Rotate keys"]
