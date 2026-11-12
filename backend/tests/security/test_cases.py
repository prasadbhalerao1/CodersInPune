"""Continuity cases: lifecycle, approvals, ownership execution, coverage and departure.

Real FastAPI app + PostgreSQL as relay_app; tokens are real RS256 JWTs (JWKS simulated).
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import anyio
import pytest

from relay.continuity import follow_through
from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import count_rows

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


async def owned(
    ws: Ws, name: str, person: str, role: str = "primary", criticality: str = "standard"
) -> str:
    rid = await ws.responsibility(name, criticality)
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": role, "person_id": person},
    )
    return rid


async def owners(ws: Ws, rid: str, as_of: str | None = None) -> list[tuple[str, str]]:
    params = {"as_of": as_of} if as_of else None
    detail = await ws.call("GET", f"/responsibilities/{rid}", params=params)
    return [(o["role"], o["assignee"]["name"]) for o in detail["owners_as_of"]]


async def resolve_readiness(ws: Ws, case: dict[str, Any]) -> None:
    for c in case["criteria"]:
        await ws.call("PATCH", f"/cases/{case['id']}/criteria/{c['id']}", json={"status": "met"})


async def approve_and_execute(ws: Ws, case_id: str, **decision: Any) -> dict[str, Any]:
    await ws.call(
        "POST", f"/cases/{case_id}/decisions", 201, json={"decision": "approved", **decision}
    )
    return dict(await ws.call("POST", f"/cases/{case_id}/execute"))


# Responsibility transfer


async def test_transfer_of_several_responsibilities_to_different_recipients(ws: Ws) -> None:
    old, bea, cy = await ws.person("Old"), await ws.person("Bea"), await ws.person("Cy")
    deploys, billing = await owned(ws, "Deploys", old), await owned(ws, "Billing", old)

    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "transfer",
            "title": "Old moves teams",
            "starts_at": iso(timedelta(minutes=-1)),
        },
    )
    cid = case["id"]
    for rid in (deploys, billing):
        case = await ws.call("POST", f"/cases/{cid}/scope", 201, json={"responsibility_id": rid})
    recipients = {deploys: bea, billing: cy}
    for item in case["scope"]:
        assert item["current_owner_name"] == "Old"
        await ws.call(
            "PATCH",
            f"/cases/{cid}/scope/{item['id']}",
            json={
                "recipient_person_id": recipients[item["responsibility_id"]],
                "handover_notes": "Runbook in wiki",
            },
        )
    case = await ws.call("POST", f"/cases/{cid}/submit")
    assert case["status"] == "planning"
    assert len(case["criteria"]) == 2
    task = await ws.call("POST", f"/cases/{cid}/tasks", 201, json={"title": "Shadow a deploy"})
    assert task["open_tasks"] == 1

    before_execution = iso()
    case = await approve_and_execute(ws, cid)
    assert case["status"] == "executing"
    assert await owners(ws, deploys) == [("primary", "Bea")]
    assert await owners(ws, billing) == [("primary", "Cy")]
    # History is preserved: the old owner's assignment was ended, not replaced.
    assert await owners(ws, deploys, before_execution) == [("primary", "Old")]

    blocked = await ws.call("POST", f"/cases/{cid}/complete", 409)
    assert blocked["code"] == "readiness_incomplete"
    await resolve_readiness(ws, case)
    done = await ws.call("POST", f"/cases/{cid}/complete")
    assert (done["status"], done["outcome"]) == ("completed", "completed")
    history = [h["action"] for h in await ws.call("GET", f"/cases/{cid}/history")]
    assert {
        "case.created",
        "case.submitted",
        "case.approved",
        "case.executed",
        "case.completed",
    } <= set(history)


async def test_future_dated_transfer_is_scheduled_not_immediate(ws: Ws) -> None:
    old, new = await ws.person("Old"), await ws.person("New")
    rid = await owned(ws, "Payroll", old)
    starts = iso(timedelta(days=7))
    case = await ws.call(
        "POST", "/cases", 201, json={"case_type": "transfer", "title": "Later", "starts_at": starts}
    )
    case = await ws.call("POST", f"/cases/{case['id']}/scope", 201, json={"responsibility_id": rid})
    await ws.call(
        "PATCH",
        f"/cases/{case['id']}/scope/{case['scope'][0]['id']}",
        json={"recipient_person_id": new},
    )
    await ws.call("POST", f"/cases/{case['id']}/submit")
    case = await approve_and_execute(ws, case["id"])
    assert await owners(ws, rid) == [("primary", "Old")]
    assert await owners(ws, rid, iso(timedelta(days=8))) == [("primary", "New")]
    await resolve_readiness(ws, case)
    early = await ws.call("POST", f"/cases/{case['id']}/complete", 409)
    assert early["code"] == "not_yet_effective"


async def test_scope_change_invalidates_approval(ws: Ws) -> None:
    old, a, b = await ws.person("Old"), await ws.person("A"), await ws.person("B")
    rid = await owned(ws, "Support rota", old)
    case = await ws.call(
        "POST", "/cases", 201, json={"case_type": "transfer", "title": "T", "starts_at": iso()}
    )
    cid = case["id"]
    case = await ws.call("POST", f"/cases/{cid}/scope", 201, json={"responsibility_id": rid})
    item = case["scope"][0]["id"]
    await ws.call("PATCH", f"/cases/{cid}/scope/{item}", json={"recipient_person_id": a})
    await ws.call("POST", f"/cases/{cid}/submit")
    approved = await ws.call("POST", f"/cases/{cid}/decisions", 201, json={"decision": "approved"})
    assert approved["approved"] is True

    changed = await ws.call("PATCH", f"/cases/{cid}/scope/{item}", json={"recipient_person_id": b})
    assert changed["approved"] is False
    assert [a["current"] for a in changed["approvals"]] == [False]
    refused = await ws.call("POST", f"/cases/{cid}/execute", 409)
    assert refused["code"] == "approval_required"
    assert await owners(ws, rid) == [("primary", "Old")]


async def test_critical_case_requires_separation_of_duties_or_recorded_exception(ws: Ws) -> None:
    old, new = await ws.person("Old"), await ws.person("New")
    rid = await owned(ws, "Core DB", old, criticality="critical")
    case = await ws.call(
        "POST", "/cases", 201, json={"case_type": "transfer", "title": "T", "starts_at": iso()}
    )
    cid = case["id"]
    case = await ws.call("POST", f"/cases/{cid}/scope", 201, json={"responsibility_id": rid})
    await ws.call(
        "PATCH", f"/cases/{cid}/scope/{case['scope'][0]['id']}", json={"recipient_person_id": new}
    )
    await ws.call("POST", f"/cases/{cid}/submit")
    sod = await ws.call("POST", f"/cases/{cid}/decisions", 409, json={"decision": "approved"})
    assert sod["code"] == "separation_of_duties"

    case = await approve_and_execute(ws, cid, sod_exception_reason="Sole admin during pilot")
    await resolve_readiness(ws, case)
    # The verifier is the initiator and approver too: also needs a recorded exception.
    sod = await ws.call("POST", f"/cases/{cid}/complete", 409)
    assert sod["code"] == "separation_of_duties"
    done = await ws.call(
        "POST", f"/cases/{cid}/complete", json={"sod_exception_reason": "Sole admin"}
    )
    assert done["outcome"] == "completed_with_exceptions"


async def test_execution_is_retry_safe(ws: Ws) -> None:
    old, new = await ws.person("Old"), await ws.person("New")
    rid = await owned(ws, "Backups", old)
    case = await ws.call(
        "POST", "/cases", 201, json={"case_type": "transfer", "title": "T", "starts_at": iso()}
    )
    cid = case["id"]
    case = await ws.call("POST", f"/cases/{cid}/scope", 201, json={"responsibility_id": rid})
    await ws.call(
        "PATCH", f"/cases/{cid}/scope/{case['scope'][0]['id']}", json={"recipient_person_id": new}
    )
    await ws.call("POST", f"/cases/{cid}/submit")
    await ws.call("POST", f"/cases/{cid}/decisions", 201, json={"decision": "approved"})

    statuses: list[int] = []

    async def execute() -> None:
        response = await ws.api.client.post(
            f"/workspaces/{ws.id}/cases/{cid}/execute", headers=ws.api.as_user(OWNER)
        )
        statuses.append(response.status_code)

    async with anyio.create_task_group() as tg:
        for _ in range(3):
            tg.start_soon(execute)
    assert sorted(statuses) == [200, 409, 409]
    assert count_rows("catalog.ownership_assignment", "responsibility_id = %s", (rid,)) == 2


# Temporary coverage


async def test_coverage_restores_original_ownership_and_supports_extension_and_early_return(
    ws: Ws,
) -> None:
    away, cover = await ws.person("Away"), await ws.person("Cover")
    rid = await owned(ws, "Payments on-call", away)
    ends = iso(timedelta(days=2))
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "coverage",
            "title": "Away on leave",
            "affected_person_id": away,
            "starts_at": iso(timedelta(minutes=-1)),
            "ends_at": ends,
        },
    )
    cid = case["id"]
    assert [i["responsibility_id"] for i in case["scope"]] == [rid]  # discovered
    await ws.call(
        "PATCH", f"/cases/{cid}/scope/{case['scope'][0]['id']}", json={"recipient_person_id": cover}
    )
    await ws.call("POST", f"/cases/{cid}/submit")
    case = await approve_and_execute(ws, cid)

    assert await owners(ws, rid) == [("temporary", "Cover"), ("primary", "Away")]
    # After the end date the original owner is the only owner, with no action needed.
    assert await owners(ws, rid, iso(timedelta(days=3))) == [("primary", "Away")]

    extended = await ws.call(
        "POST", f"/cases/{cid}/extend", json={"ends_at": iso(timedelta(days=5))}
    )
    assert extended["ends_at"] > case["ends_at"]
    assert await owners(ws, rid, iso(timedelta(days=4))) == [
        ("temporary", "Cover"),
        ("primary", "Away"),
    ]

    await resolve_readiness(ws, case)
    done = await ws.call("POST", f"/cases/{cid}/complete")  # early return
    assert done["status"] == "completed"
    assert await owners(ws, rid) == [("primary", "Away")]
    changes = {h["change_type"] for h in await ws.call("GET", f"/responsibilities/{rid}/history")}
    assert changes == {"assigned", "extended", "ended"}


async def test_future_coverage_is_scheduled(ws: Ws) -> None:
    away, cover = await ws.person("Away"), await ws.person("Cover")
    rid = await owned(ws, "Payroll", away)
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "coverage",
            "title": "Next month",
            "affected_person_id": away,
            "starts_at": iso(timedelta(days=10)),
            "ends_at": iso(timedelta(days=20)),
        },
    )
    await ws.call(
        "PATCH",
        f"/cases/{case['id']}/scope/{case['scope'][0]['id']}",
        json={"recipient_person_id": cover},
    )
    await ws.call("POST", f"/cases/{case['id']}/submit")
    await approve_and_execute(ws, case["id"])
    assert await owners(ws, rid) == [("primary", "Away")]
    assert await owners(ws, rid, iso(timedelta(days=15))) == [
        ("temporary", "Cover"),
        ("primary", "Away"),
    ]
    assert await owners(ws, rid, iso(timedelta(days=21))) == [("primary", "Away")]


# Light departure


async def test_departure_discovers_responsibilities_and_records_exceptions(ws: Ws) -> None:
    leaver, heir, primary_owner = (
        await ws.person("Leaver"),
        await ws.person("Heir"),
        await ws.person("Main"),
    )
    led = await owned(ws, "Release train", leaver)
    backed = await owned(ws, "Billing", primary_owner)
    await ws.call(
        "POST",
        f"/responsibilities/{backed}/assignments",
        201,
        json={"role": "backup", "person_id": leaver},
    )
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "departure",
            "title": "Leaver departs",
            "affected_person_id": leaver,
            "starts_at": iso(),
        },
    )
    cid = case["id"]
    items = {i["responsibility_id"]: i for i in case["scope"]}
    assert set(items) == {led, backed}
    assert items[backed]["role"] == "backup"
    await ws.call(
        "PATCH", f"/cases/{cid}/scope/{items[led]['id']}", json={"recipient_person_id": heir}
    )
    await ws.call(
        "PATCH",
        f"/cases/{cid}/scope/{items[backed]['id']}",
        json={"exception_reason": "Backup no longer needed"},
    )
    case = await ws.call("POST", f"/cases/{cid}/submit")
    assert len(case["criteria"]) == 1  # excepted items need no readiness check
    case = await approve_and_execute(ws, cid)

    assert await owners(ws, led) == [("primary", "Heir")]
    assert await owners(ws, backed) == [("primary", "Main"), ("backup", "Leaver")]
    await resolve_readiness(ws, case)
    done = await ws.call("POST", f"/cases/{cid}/complete")
    assert done["outcome"] == "completed_with_exceptions"


# Lifecycle, permissions, isolation, My Work


async def test_lifecycle_rules(ws: Ws) -> None:
    case = await ws.call(
        "POST", "/cases", 201, json={"case_type": "transfer", "title": "T", "starts_at": iso()}
    )
    cid = case["id"]
    empty = await ws.call("POST", f"/cases/{cid}/submit", 409)
    assert empty["code"] == "empty_scope"
    rid = await ws.responsibility("Unowned")
    case = await ws.call("POST", f"/cases/{cid}/scope", 201, json={"responsibility_id": rid})
    missing = await ws.call("POST", f"/cases/{cid}/submit", 409)
    assert missing["code"] == "recipients_missing"
    await ws.call("POST", f"/cases/{cid}/execute", 409)
    cancelled = await ws.call("POST", f"/cases/{cid}/cancel")
    assert (cancelled["status"], cancelled["outcome"]) == ("cancelled", "cancelled")
    await ws.call("POST", f"/cases/{cid}/scope", 409, json={"responsibility_id": rid})
    bad = await ws.api.client.post(
        f"/workspaces/{ws.id}/cases",
        json={"case_type": "coverage", "title": "x", "starts_at": iso()},
        headers=ws.api.as_user(OWNER),
    )
    assert bad.status_code == 422


async def test_members_cannot_manage_or_approve_but_can_complete_their_tasks(
    api: Api, ws: Ws
) -> None:
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    members = await ws.call("GET", "/members")
    member_id = next(m["user_id"] for m in members if m["role"] == "member")
    owner_id = next(m["user_id"] for m in members if m["role"] == "owner")

    case = await ws.call(
        "POST", "/cases", 201, json={"case_type": "transfer", "title": "T", "starts_at": iso()}
    )
    cid = case["id"]
    await member.call(
        "POST", "/cases", 403, json={"case_type": "transfer", "title": "x", "starts_at": iso()}
    )
    await member.call("POST", f"/cases/{cid}/cancel", 403)
    case = await ws.call(
        "POST", f"/cases/{cid}/tasks", 201, json={"title": "Mine", "assignee_user_id": member_id}
    )
    case = await ws.call(
        "POST", f"/cases/{cid}/tasks", 201, json={"title": "Not mine", "assignee_user_id": owner_id}
    )
    mine, theirs = case["tasks"][0]["id"], case["tasks"][1]["id"]

    work = await member.call("GET", "/my-work")
    assert [t["title"] for t in work["tasks"]] == ["Mine"]
    await member.call("PATCH", f"/cases/{cid}/tasks/{mine}", json={"status": "done"})
    await member.call("PATCH", f"/cases/{cid}/tasks/{theirs}", 403, json={"status": "done"})
    await member.call("POST", f"/cases/{cid}/decisions", 403, json={"decision": "approved"})


async def test_cases_are_isolated_between_workspaces(api: Api, ws: Ws) -> None:
    case = await ws.call(
        "POST", "/cases", 201, json={"case_type": "transfer", "title": "T", "starts_at": iso()}
    )
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    assert await other.call("GET", "/cases") == []
    await other.call("GET", f"/cases/{case['id']}", 404)
    await other.call("POST", f"/cases/{case['id']}/cancel", 404)
    # A responsibility from another workspace cannot be pulled into scope.
    theirs = await other.responsibility("Theirs")
    await ws.call("POST", f"/cases/{case['id']}/scope", 422, json={"responsibility_id": theirs})


async def test_my_work_lists_pending_approvals(ws: Ws) -> None:
    old, new = await ws.person("Old"), await ws.person("New")
    rid = await owned(ws, "Rota", old)
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={"case_type": "transfer", "title": "Needs approval", "starts_at": iso()},
    )
    case = await ws.call("POST", f"/cases/{case['id']}/scope", 201, json={"responsibility_id": rid})
    await ws.call(
        "PATCH",
        f"/cases/{case['id']}/scope/{case['scope'][0]['id']}",
        json={"recipient_person_id": new},
    )
    await ws.call("POST", f"/cases/{case['id']}/submit")
    work = await ws.call("GET", "/my-work")
    assert [c["title"] for c in work["approvals"]] == ["Needs approval"]


async def test_profile_sync_names_members(api: Api, ws: Ws) -> None:
    response = await api.client.put(
        "/me/profile", json={"display_name": "Priya Owner"}, headers=api.as_user(OWNER)
    )
    assert response.status_code == 204
    assert [m["name"] for m in await ws.call("GET", "/members")] == ["Priya Owner"]
    spoof = await api.client.put(
        "/me/profile",
        json={"display_name": "x", "user_id": str(uuid.uuid4())},
        headers=api.as_user(OWNER),
    )
    assert spoof.status_code == 422


async def test_follow_through_shows_whether_each_transfer_took_hold(
    ws: Ws, monkeypatch: pytest.MonkeyPatch
) -> None:
    old, bea, cy = await ws.person("Old"), await ws.person("Bea"), await ws.person("Cy")
    deploys, billing = await owned(ws, "Deploys", old), await owned(ws, "Billing", old)
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "transfer",
            "title": "Old moves on",
            "starts_at": iso(timedelta(minutes=-1)),
        },
    )
    cid = case["id"]
    for rid in (deploys, billing):
        case = await ws.call("POST", f"/cases/{cid}/scope", 201, json={"responsibility_id": rid})
    recipients = {deploys: bea, billing: cy}
    for item in case["scope"]:
        await ws.call(
            "PATCH",
            f"/cases/{cid}/scope/{item['id']}",
            json={"recipient_person_id": recipients[item["responsibility_id"]]},
        )
    await ws.call("POST", f"/cases/{cid}/submit")
    assert (await ws.call("GET", f"/cases/{cid}/follow-through"))["applies"] is False

    await approve_and_execute(ws, cid)
    fresh = await ws.call("GET", f"/cases/{cid}/follow-through")
    assert {i["state"] for i in fresh["items"]} == {"settling"}  # just handed over

    await ws.call("POST", f"/responsibilities/{deploys}/review", 204, params={"verified": "true"})
    monkeypatch.setattr(follow_through, "CHECK_IN_AFTER", timedelta(0))  # time has passed
    view = await ws.call("GET", f"/cases/{cid}/follow-through")
    states = {i["responsibility_name"]: i for i in view["items"]}
    assert view["applies"]
    assert view["settled"] == 1
    assert view["rule"]
    # Reviewed since the handover: the work is being looked after.
    assert (states["Deploys"]["state"], states["Deploys"]["reviewed_since"]) == ("settled", True)
    # No review and no recorded activity once the check-in period has passed.
    assert states["Billing"]["state"] == "check_in"
    assert (states["Billing"]["recipient_name"], states["Billing"]["activity_since"]) == ("Cy", 0)
