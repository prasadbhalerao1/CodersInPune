"""Case lifecycle: status model, blockers, reopening, declines, duplicates, splits, filters."""

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import psycopg
import pytest

from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import OWNER_URL, libpq_url
from tests.security.test_cases import iso, owned, resolve_readiness

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


def statuses(case: dict[str, Any]) -> list[str]:
    return [c["to_status"] for c in reversed(case["status_history"])]


async def test_onboarding_walks_the_full_status_model(ws: Ws) -> None:
    holder, joiner = await ws.person("Holder"), await ws.person("Joiner")
    rid = await owned(ws, "Billing", holder)
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "onboarding",
            "title": "Joiner onboarding",
            "affected_person_id": joiner,
            "starts_at": iso(),
            "priority": "high",
            "due_at": iso(timedelta(days=14)),
            "time_zone": "Asia/Kolkata",
        },
    )
    cid = case["id"]
    assert case["status"] == "draft"
    assert case["priority"] == "high"
    assert "investigating" in case["transitions"]
    case = await ws.call("POST", f"/cases/{cid}/scope", 201, json={"responsibility_id": rid})
    # The joiner receives; the current holder is the outgoing owner.
    assert case["scope"][0]["recipient"]["name"] == "Joiner"
    assert case["scope"][0]["current_owner_name"] == "Holder"

    jump = await ws.call("POST", f"/cases/{cid}/transition", 409, json={"to": "executing"})
    assert jump["code"] == "invalid_transition"
    await ws.call("POST", f"/cases/{cid}/transition", json={"to": "investigating"})
    await ws.call("POST", f"/cases/{cid}/submit")
    case = await ws.call("POST", f"/cases/{cid}/decisions", 201, json={"decision": "approved"})
    assert case["status"] == "ready_for_transfer"
    # A plan change after approval sends it back to planning; the approval no longer counts.
    case = await ws.call(
        "PATCH", f"/cases/{cid}/scope/{case['scope'][0]['id']}", json={"handover_notes": "x"}
    )
    assert case["status"] == "planning"
    assert not case["approved"]
    await ws.call("POST", f"/cases/{cid}/decisions", 201, json={"decision": "approved"})

    # A blocker stops execution until it is resolved, then the case resumes where it was.
    case = await ws.call(
        "POST", f"/cases/{cid}/blockers", 201, json={"description": "Laptop not issued"}
    )
    assert case["status"] == "blocked"
    assert case["blocked_from"] == "ready_for_transfer"
    assert case["blockers"][0]["escalate_at"]  # high priority: escalates within a day
    await ws.call("POST", f"/cases/{cid}/execute", 409)
    case = await ws.call(
        "POST",
        f"/cases/{cid}/blockers/{case['blockers'][0]['id']}/resolve",
        json={"resolution": "Issued"},
    )
    assert case["status"] == "ready_for_transfer"

    case = await ws.call("POST", f"/cases/{cid}/execute")
    await ws.call("POST", f"/cases/{cid}/transition", json={"to": "verification"})
    await resolve_readiness(ws, case)
    case = await ws.call("POST", f"/cases/{cid}/complete")
    assert case["status"] == "completed"

    # Reopening keeps the closure on record and never undoes applied ownership.
    case = await ws.call("POST", f"/cases/{cid}/reopen", json={"reason": "Missed a repo"})
    assert case["status"] == "reopened"
    assert case["outcome"] is None
    reopen = case["status_history"][0]
    assert reopen["outcome"] == "completed"
    assert reopen["closed_at"]
    assert reopen["reason"]
    assert statuses(case) == [
        "draft",
        "investigating",
        "planning",
        "ready_for_transfer",
        "planning",
        "ready_for_transfer",
        "blocked",
        "ready_for_transfer",
        "executing",
        "verification",
        "completed",
        "reopened",
    ]
    detail = await ws.call("GET", f"/responsibilities/{rid}")
    assert [o["assignee"]["name"] for o in detail["owners_as_of"]] == ["Joiner"]


async def test_duplicates_project_handover_split_and_filters(ws: Ws) -> None:
    lead, other = await ws.person("Lead"), await ws.person("Other")
    api_rid = await owned(ws, "Payments API", lead)
    web_rid = await owned(ws, "Checkout web", lead)
    project = await ws.call(
        "POST", "/assets", 201, json={"name": "Payments", "asset_type": "repository"}
    )
    await ws.call(
        "POST", f"/responsibilities/{api_rid}/assets", 204, json={"asset_id": project["id"]}
    )

    handover = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "project_handover",
            "title": "Payments handover",
            "project_asset_id": project["id"],
            "starts_at": iso(),
        },
    )
    assert [s["responsibility_name"] for s in handover["scope"]] == ["Payments API"]
    assert handover["project_asset_name"] == "Payments"

    departure = {
        "case_type": "departure",
        "title": "Lead leaves",
        "affected_person_id": lead,
        "starts_at": iso(),
        "priority": "urgent",
        "due_at": iso(timedelta(days=-1)),
    }
    first = await ws.call("POST", "/cases", 201, json=departure)
    duplicate = await ws.call("POST", "/cases", 409, json=departure)
    assert duplicate["code"] == "duplicate_case"
    second = await ws.call(
        "POST", "/cases", 201, json={**departure, "duplicate_override_reason": "Second contract"}
    )
    assert second["duplicates"][0]["id"] == first["id"]

    # Split a departure: each responsibility becomes a child transfer with its tasks.
    web_item = next(s for s in first["scope"] if s["responsibility_id"] == web_rid)
    await ws.call(
        "POST",
        f"/cases/{first['id']}/tasks",
        201,
        json={"title": "Walk through deploys", "scope_item_id": web_item["id"]},
    )
    parent = await ws.call("POST", f"/cases/{first['id']}/split", json=[web_item["id"]])
    assert [s["responsibility_id"] for s in parent["scope"]] == [api_rid]
    child = await ws.call("GET", f"/cases/{parent['children'][0]['id']}")
    assert child["parent"]["id"] == first["id"]
    assert child["case_type"] == "transfer"
    assert [t["title"] for t in child["tasks"]] == ["Walk through deploys"]
    assert child["status_history"][0]["reason"].startswith("Split from")

    urgent = await ws.call("GET", "/cases", params={"priority": "urgent", "overdue": "true"})
    # The split-off child inherits priority and due date.
    assert {c["id"] for c in urgent} == {first["id"], second["id"], child["id"]}
    by_person = await ws.call("GET", "/cases", params={"affected_person_id": other})
    assert by_person == []

    views = await ws.call(
        "POST",
        "/saved-views",
        201,
        json={"page": "cases", "name": "Urgent overdue", "query": "?priority=urgent&overdue=true"},
    )
    assert views[0]["query"] == "priority=urgent&overdue=true"


async def test_incoming_owner_declines_and_delegate_approves(api: Api, ws: Ws) -> None:
    await add_member(api, ws.id, "user_member", "member")
    old = await ws.person("Old")
    new = await ws.call(
        "POST", "/people", 201, json={"display_name": "New", "email": "new@acme.test"}
    )
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(ws.id),))
        conn.execute(
            "UPDATE identity.membership SET email = 'new@acme.test' "
            "WHERE tenant_id = %s AND role = 'member'",
            (ws.id,),
        )
    member = Ws(api, ws.id, "user_member")
    member_id = next(
        m["user_id"] for m in await ws.call("GET", "/members") if m["role"] == "member"
    )
    rid = await owned(ws, "Payroll", old)
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "transfer",
            "title": "Payroll",
            "starts_at": iso(),
            "delegate_approver_user_id": member_id,
        },
    )
    cid = case["id"]
    case = await ws.call("POST", f"/cases/{cid}/scope", 201, json={"responsibility_id": rid})
    item = case["scope"][0]["id"]
    await ws.call("PATCH", f"/cases/{cid}/scope/{item}", json={"recipient_person_id": new["id"]})
    await ws.call("POST", f"/cases/{cid}/submit")
    await ws.call("POST", f"/cases/{cid}/decisions", 201, json={"decision": "approved"})

    seen = await member.call("GET", f"/cases/{cid}")
    assert seen["scope"][0]["can_decline"]
    await ws.call("POST", f"/cases/{cid}/scope/{item}/decline", 403, json={"reason": "x"})
    case = await member.call(
        "POST", f"/cases/{cid}/scope/{item}/decline", json={"reason": "On parental leave"}
    )
    assert case["status"] == "planning"
    assert case["scope"][0]["recipient"] is None
    assert case["scope"][0]["decline_reason"] == "On parental leave"

    # The delegated approver (a plain member) may decide this case, and only this case.
    await ws.call("PATCH", f"/cases/{cid}/scope/{item}", json={"recipient_person_id": old})
    decided = await member.call(
        "POST", f"/cases/{cid}/decisions", 201, json={"decision": "approved"}
    )
    assert decided["status"] == "ready_for_transfer"
    people = await ws.call("GET", f"/cases/{cid}/participants")
    roles = {p["name"]: p["roles"] for p in people}
    assert "approver" in roles[decided["delegate_approver_name"]]


async def test_task_coordination_and_readiness(api: Api, ws: Ws) -> None:
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    member_id = next(
        m["user_id"] for m in await ws.call("GET", "/members") if m["role"] == "member"
    )
    old, new = await ws.person("Old"), await ws.person("New")
    rid = await owned(ws, "Ledger", old)
    case = await ws.call(
        "POST", "/cases", 201, json={"case_type": "transfer", "title": "Ledger", "starts_at": iso()}
    )
    cid = case["id"]
    case = await ws.call(
        "POST", f"/cases/{cid}/tasks", 201, json={"title": "Export runbook", "priority": "high"}
    )
    first = case["tasks"][0]["id"]
    case = await ws.call(
        "POST",
        f"/cases/{cid}/tasks",
        201,
        json={"title": "Review runbook", "depends_on": [first], "assignee_user_id": member_id},
    )
    second = next(t for t in case["tasks"] if t["id"] != first)
    assert second["blocked_by"] == ["Export runbook"]
    blocked = await member.call(
        "PATCH", f"/cases/{cid}/tasks/{second['id']}", 409, json={"status": "done"}
    )
    assert blocked["code"] == "dependencies_open"

    # A clarification waits on the person asked; their reply answers it.
    await ws.call(
        "POST",
        f"/cases/{cid}/tasks/{second['id']}/messages",
        201,
        json={"kind": "clarification", "body": "Which environment?"},
    )
    work = await member.call("GET", "/my-work")
    assert [t["title"] for t in work["needs_input"]] == ["Review runbook"]
    reply = await member.call(
        "POST", f"/cases/{cid}/tasks/{second['id']}/messages", 201, json={"body": "Production"}
    )
    assert reply["task"]["needs_input_from_user_id"] is None
    assert [e["kind"] for e in reply["events"]] == [
        "clarification_requested",
        "clarification_answered",
    ]

    # Reassigning an assigned task needs a reason and is kept in the task history.
    await ws.call(
        "POST", f"/cases/{cid}/tasks/{second['id']}/change", 422, json={"assignee_user_id": None}
    )
    moved = await ws.call(
        "POST",
        f"/cases/{cid}/tasks/{second['id']}/change",
        json={"assignee_user_id": None, "due_at": iso(timedelta(days=2)), "reason": "On leave"},
    )
    assert [e["kind"] for e in moved["events"]][-2:] == ["reassigned", "due_changed"]

    # Bulk completion skips tasks still waiting on others.
    result = await ws.call(
        "POST",
        f"/cases/{cid}/tasks/bulk",
        json={"task_ids": [second["id"]], "action": "complete"},
    )
    assert result["done"] == []
    assert "Export runbook" in result["skipped"][second["id"]]
    await ws.call(
        "PATCH",
        f"/cases/{cid}/tasks/{first}",
        json={
            "status": "done",
            "completion_note": "Exported",
            "completion_url": "https://x.test/r",
        },
    )
    result = await ws.call(
        "POST", f"/cases/{cid}/tasks/bulk", json={"task_ids": [second["id"]], "action": "complete"}
    )
    assert result["done"] == [second["id"]]
    await ws.call("PATCH", f"/cases/{cid}/tasks/{first}", 422, json={"status": "open"})

    # Readiness: uncertain states need a reason; a rehearsal needs every step confirmed.
    case = await ws.call("POST", f"/cases/{cid}/scope", 201, json={"responsibility_id": rid})
    await ws.call(
        "PATCH", f"/cases/{cid}/scope/{case['scope'][0]['id']}", json={"recipient_person_id": new}
    )
    case = await ws.call(
        "POST",
        f"/cases/{cid}/criteria",
        201,
        json={
            "criterion_type": "rehearsal",
            "title": "Month-end close rehearsal",
            "checklist": ["Run reconciliation", "Post journal"],
        },
    )
    rehearsal = next(c for c in case["criteria"] if c["criterion_type"] == "rehearsal")
    await ws.call("PATCH", f"/cases/{cid}/criteria/{rehearsal['id']}", 409, json={"status": "met"})
    await ws.call(
        "PATCH", f"/cases/{cid}/criteria/{rehearsal['id']}", 422, json={"status": "needs_review"}
    )
    case = await ws.call(
        "PATCH",
        f"/cases/{cid}/criteria/{rehearsal['id']}",
        json={"status": "unable_to_assess", "note": "Close only runs monthly"},
    )
    assert any("can't be assessed" in r for r in case["readiness_reasons"])
    for i in range(2):
        case = await ws.call(
            "PATCH", f"/cases/{cid}/criteria/{rehearsal['id']}/steps/{i}", json={"done": True}
        )
    case = await ws.call(
        "PATCH", f"/cases/{cid}/criteria/{rehearsal['id']}", json={"status": "met"}
    )
    step = next(c for c in case["criteria"] if c["id"] == rehearsal["id"])["checklist"][0]
    assert step["done"]
    assert step["done_by"]
