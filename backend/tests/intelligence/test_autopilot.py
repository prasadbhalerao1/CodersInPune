"""Handover Autopilot: the whole analysis in one streamed run, ending in proposals to review."""

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from tests.api import Api, Ws, make_api
from tests.intelligence.test_analysis import Script, case_with_knowledge, ref_of, script
from tests.intelligence.test_handover import member_id

pytestmark = pytest.mark.anyio
__all__ = ["script"]  # fixture re-export


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(llm_providers="fake") as a:
        yield a


async def autopilot(who: Ws, case: str, body: dict[str, Any] | None = None) -> list[Any]:
    response = await who.api.client.post(
        f"/workspaces/{who.id}/cases/{case}/autopilot",
        headers=who.api.as_user(who.sub),
        json=body or {},
    )
    assert response.status_code == 200, response.text
    events = []
    for block in response.text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


async def test_autopilot_streams_each_tool_and_ends_with_pending_proposals(
    api: Api, script: list[Script]
) -> None:
    ws, _member, cid = await case_with_knowledge(api)

    def discovery(refs: dict[str, str]) -> dict[str, Any]:
        rotate = ref_of(refs, "Rotate the webhook secret")
        return {
            "claims": [
                {
                    "kind": "finding",
                    "text": "Webhook rotation is documented.",
                    "evidence": [rotate],
                },
                {"kind": "finding", "text": "Invented.", "evidence": ["E999"]},
            ],
            "proposals": [
                {"type": "task", "title": "Walk Bea through rotation", "evidence": [rotate]}
            ],
        }

    script.append(discovery)
    events = await autopilot(ws, cid, {"recipient_user_id": await member_id(ws)})
    steps = [d for name, d in events if name == "step"]
    keys = [s["key"] for s in steps if s["status"] != "running"]
    assert keys[:3] == ["case", "evidence", "rules"]
    assert "discovery" in keys
    assert keys[-2:] == ["interview", "brief"]
    # Each AI step is announced before it runs, then settled with what it produced.
    assert [s["status"] for s in steps if s["key"] == "discovery"] == ["running", "done"]
    discovery_done = next(s for s in steps if s["key"] == "discovery" and s["status"] == "done")
    assert "1 cited points" in discovery_done["summary"]
    assert "1 uncited dropped" in discovery_done["summary"]
    assert int(steps[1]["summary"].split()[0]) > 0  # evidence gathered
    name, done = events[-1]
    assert name == "done"
    assert [p["title"] for p in done["proposals"]] == ["Walk Bea through rotation"]
    # Nothing was applied: the proposal waits for a person, and the run is finished.
    view = await ws.call("GET", f"/cases/{cid}/analysis")
    assert view["run"]["state"] not in ("queued", "running")
    assert [p["status"] for p in view["proposals"]] == ["pending"]


async def test_autopilot_without_ai_still_reports_the_rule_based_findings(api: Api) -> None:
    ws, _member, cid = await case_with_knowledge(api)
    await ws.call("PATCH", "/ai", 204, json={"enabled": False})
    events = await autopilot(ws, cid)
    steps = {d["key"]: d for name, d in events if name == "step"}
    assert steps["ai"]["status"] == "skipped"
    assert "switched off" in steps["ai"]["summary"]
    assert "brief" not in steps  # no recipient, no brief
    assert events[-1][0] == "done"


async def test_members_cannot_run_autopilot(api: Api) -> None:
    ws, member, cid = await case_with_knowledge(api)
    response = await api.client.post(
        f"/workspaces/{ws.id}/cases/{cid}/autopilot", headers=api.as_user(member.sub), json={}
    )
    assert response.status_code in (403, 404)
