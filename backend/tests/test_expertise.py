"""Expertise map: who holds each responsibility and who has written down how it works."""

from collections.abc import AsyncIterator

import pytest

from tests.api import Api, make_api
from tests.intelligence.test_analysis import case_with_knowledge

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


async def test_fragile_work_comes_first_and_backups_are_named_or_capable(api: Api) -> None:
    ws, member, _cid = await case_with_knowledge(api)
    safe = await ws.responsibility("Team lunch", "low")
    alice, bob = await ws.person("Alice"), await ws.person("Bob")
    for role, person in (("primary", alice), ("backup", bob)):
        await ws.call(
            "POST",
            f"/responsibilities/{safe}/assignments",
            201,
            json={"role": role, "person_id": person},
        )
    view = await member.call("GET", "/search/expertise")
    rows = {r["name"]: r for r in view["rows"]}
    assert rows["Payments on-call"]["bus_factor"] == 1
    assert rows["Payments on-call"]["named_backup"] is False
    assert rows["Team lunch"]["bus_factor"] == 2
    assert rows["Team lunch"]["named_backup"] is True
    assert rows["Team lunch"]["capable_backup"] is False  # Bob never wrote anything down
    assert rows["Team lunch"]["cells"][bob] == ["backup"]
    order = [r["name"] for r in view["rows"]]
    assert order.index("Payments on-call") < order.index("Team lunch")
    assert {p["name"] for p in view["people"]} >= {"Alice", "Bob", "Old Owner"}
