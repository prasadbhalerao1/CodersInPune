"""30/60/90 plan: every step comes from the case and says why."""

from collections.abc import AsyncIterator

import pytest

from tests.api import Api, make_api
from tests.intelligence.test_analysis import case_with_knowledge

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


async def test_plan_phases_follow_the_case(api: Api) -> None:
    ws, _member, cid = await case_with_knowledge(api)
    case = await ws.call("GET", f"/cases/{cid}")
    item = case["scope"][0]
    plan = await ws.call("GET", f"/cases/{cid}/plan")
    assert [p["days"] for p in plan["phases"]] == [30, 60, 90]
    first = [s["title"] for s in plan["phases"][0]["steps"]]
    # No recipient yet: the first step is to name one.
    assert f"Name who takes over {item['responsibility_name']}" in first
    last = [s["title"] for s in plan["phases"][2]["steps"]]
    assert last[-1] == "Close the case and record what was learned"

    bea = await ws.person("Bea")
    await ws.call(
        "PATCH",
        f"/cases/{cid}/scope/{item['id']}",
        200,
        json={"recipient_person_id": bea},
    )
    plan = await ws.call("GET", f"/cases/{cid}/plan")
    first = [s["title"] for s in plan["phases"][0]["steps"]]
    lead = [s["title"] for s in plan["phases"][1]["steps"]]
    assert any(t.startswith("Bea shadows Old Owner") for t in first)  # critical work
    assert f"Bea leads {item['responsibility_name']}" in lead
    # It has written knowledge, so no "document it" step.
    assert not any(t.startswith("Document how") for t in lead)
    assert all(s["why"] for p in plan["phases"] for s in p["steps"])
