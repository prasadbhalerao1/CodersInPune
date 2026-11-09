"""Global search: grouped, permission-aware, tenant-isolated."""

from collections.abc import AsyncIterator

import pytest

from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.fakes import FakeExternal

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(FakeExternal()) as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


async def kinds(ws: Ws, q: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for hit in (await ws.call("GET", "/search", params={"q": q}))["hits"]:
        found.setdefault(hit["kind"], []).append(hit["title"])
    return found


async def test_search_groups_records_across_modules(ws: Ws) -> None:
    rid = await ws.responsibility("Payroll run", "critical")
    await ws.person("Paula Payne")
    await ws.call("POST", "/teams", 201, json={"name": "Payments"})
    await ws.call("POST", "/departments", 201, json={"name": "Payables"})
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={"kind": "procedure", "title": "Monthly close", "body": "Approve the payroll file"},
    )
    await ws.call("GET", "/risks")  # materialise detected risks
    found = await kinds(ws, "pay")
    assert found["responsibility"] == ["Payroll run"]
    assert found["person"] == ["Paula Payne"]
    assert found["team"] == ["Payments"]
    assert found["department"] == ["Payables"]
    assert any("Payroll run" in t for t in found["risk"])
    assert (await kinds(ws, "payroll file"))["knowledge"] == ["Monthly close"]  # full text
    assert await kinds(ws, "p") == {}  # too short
    assert await kinds(ws, "%") == {}  # wildcards are literal


async def test_search_respects_visibility_and_tenants(api: Api, ws: Ws) -> None:
    rid = await ws.responsibility("Treasury", "high")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={"kind": "note", "title": "Bank tokens", "body": "x", "visibility": "managers"},
    )
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    assert "knowledge" not in await kinds(member, "bank")  # managers-only stays hidden
    assert (await kinds(ws, "bank"))["knowledge"] == ["Bank tokens"]
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    assert await kinds(other, "treasury") == {}
