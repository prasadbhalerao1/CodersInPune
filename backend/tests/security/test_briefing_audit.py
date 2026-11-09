"""Return briefing for coverage cases, and the filtered, labelled audit log."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from tests.api import OWNER, Api, Ws, add_member, make_api

pytestmark = pytest.mark.anyio


def iso(delta: timedelta = timedelta()) -> str:
    return (datetime.now(UTC) + delta).isoformat()


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


async def test_return_briefing_reports_cover_changes_work_notes_and_restoration(ws: Ws) -> None:
    arjun, priya = await ws.person("Arjun"), await ws.person("Priya")
    rid = await ws.responsibility("Payments on-call", "high")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "person_id": arjun},
    )
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "coverage",
            "title": "Arjun on leave",
            "affected_person_id": arjun,
            "starts_at": iso(timedelta(minutes=-5)),
            "ends_at": iso(timedelta(days=10)),
        },
    )
    item = case["scope"][0]
    await ws.call(
        "PATCH",
        f"/cases/{case['id']}/scope/{item['id']}",
        json={"recipient_person_id": priya, "handover_notes": "Runbook in the wiki"},
    )
    await ws.call("POST", f"/cases/{case['id']}/submit")
    await ws.call("POST", f"/cases/{case['id']}/decisions", 201, json={"decision": "approved"})
    executed = await ws.call("POST", f"/cases/{case['id']}/execute")

    # Things that happen while Arjun is away.
    await ws.call(
        "POST", f"/cases/{case['id']}/comments", 201, json={"body": "Rotated the API key"}
    )
    await ws.call("POST", f"/cases/{case['id']}/tasks", 201, json={"title": "Review alerts"})
    detail = await ws.call("GET", f"/responsibilities/{rid}")
    await ws.call(
        "PATCH",
        f"/responsibilities/{rid}",
        json={"version": detail["version"], "description": "PCI"},
    )

    runbook = await ws.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={"kind": "procedure", "title": "Pager runbook", "body": "Steps"},
    )
    await ws.call(
        "POST",
        f"/cases/{case['id']}/knowledge",
        201,
        json={
            "responsibility_id": rid,
            "outcome": "handed_over",
            "knowledge_item_id": runbook["id"],
        },
    )
    await ws.call(
        "POST",
        f"/cases/{case['id']}/knowledge",
        201,
        json={"responsibility_id": rid, "outcome": "missing", "note": "No vendor contacts"},
    )
    during = await ws.call("GET", f"/cases/{case['id']}/briefing")
    assert during["person_name"] == "Arjun"
    assert during["returned"] is False
    [entry] = during["items"]
    assert (entry["covered_by"], entry["restoration"], entry["original_owner_active"]) == (
        "Priya",
        "covering",
        True,
    )
    assert entry["handover_notes"] == "Runbook in the wiki"
    assert any(c["role"] == "temporary" for c in during["ownership_changes"])
    assert "responsibility.updated" in [e["action"] for e in during["responsibility_events"]]
    assert [t["title"] for t in during["tasks"]] == ["Review alerts"]
    assert [n["body"] for n in during["notes"]] == ["Rotated the API key"]
    assert [(k["outcome"], k["title"], k["note"]) for k in during["knowledge"]] == [
        ("handed_over", "Pager runbook", None),
        ("missing", None, "No vendor contacts"),
    ]
    assert during["exceptions"] == 0

    for criterion in executed["criteria"]:
        await ws.call(
            "PATCH", f"/cases/{case['id']}/criteria/{criterion['id']}", json={"status": "met"}
        )
    await ws.call("POST", f"/cases/{case['id']}/complete")  # early return
    after = await ws.call("GET", f"/cases/{case['id']}/briefing")
    assert after["returned"] is True
    assert after["items"][0]["restoration"] == "restored"
    assert after["items"][0]["original_owner_active"] is True


async def test_briefing_only_for_coverage_and_isolated(api: Api, ws: Ws) -> None:
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={"case_type": "transfer", "title": "T", "starts_at": iso()},
    )
    await ws.call("GET", f"/cases/{case['id']}/briefing", 422)
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    await other.call("GET", f"/cases/{case['id']}/briefing", 404)


async def test_audit_log_filters_labels_and_permissions(api: Api, ws: Ws) -> None:
    rid = await ws.responsibility("Payments")
    await ws.call("POST", "/assets", 201, json={"name": "payments-api", "asset_type": "repository"})
    events = await ws.call("GET", "/audit-events")
    created = next(e for e in events if e["action"] == "responsibility.created")
    assert (created["target_label"], created["actor_name"]) == ("Payments", created["actor_name"])
    assert created["actor_name"]

    only_assets = await ws.call("GET", "/audit-events", params={"category": "asset"})
    assert {e["action"] for e in only_assets} == {"asset.created"}
    by_target = await ws.call(
        "GET", "/audit-events", params={"target_type": "responsibility", "target_id": rid}
    )
    assert [e["action"] for e in by_target] == ["responsibility.created"]
    older = await ws.call("GET", "/audit-events", params={"before": events[-1]["occurred_at"]})
    assert all(e["occurred_at"] < events[-1]["occurred_at"] for e in older)
    await ws.call("GET", "/audit-events", 422, params={"category": "a' OR 1=1"})

    await add_member(api, ws.id, "user_member", "member")
    await Ws(api, ws.id, "user_member").call("GET", "/audit-events", 403)
    await add_member(api, ws.id, "user_auditor", "auditor")
    assert await Ws(api, ws.id, "user_auditor").call("GET", "/audit-events")
