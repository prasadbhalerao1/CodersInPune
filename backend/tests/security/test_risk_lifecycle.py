"""Risk lifecycle: open -> acknowledged / accepted until a date -> resolved (automatic)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import OWNER_URL, libpq_url

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


def _later(days: int) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).isoformat()


async def test_acknowledge_accept_expire_resolve_and_recur(ws: Ws) -> None:
    rid = await ws.responsibility("Payments", "high")
    key = f"no_primary_owner:{rid}"
    risks = {r["key"]: r for r in await ws.call("GET", "/risks")}
    assert risks[key]["status"] == "open"
    assert risks[key]["first_detected_at"]

    acked = await ws.call("POST", "/risks/decision", json={"key": key, "action": "acknowledge"})
    assert (acked["status"], acked["decided_by_name"] is not None) == ("acknowledged", True)
    assert key in {r["key"] for r in await ws.call("GET", "/risks")}  # still open work

    await ws.call("POST", "/risks/decision", 422, json={"key": key, "action": "accept"})
    await ws.call(
        "POST",
        "/risks/decision",
        422,
        json={"key": key, "action": "accept", "note": "x", "accepted_until": _later(-1)},
    )
    accepted = await ws.call(
        "POST",
        "/risks/decision",
        json={
            "key": key,
            "action": "accept",
            "note": "Owner hired next month",
            "accepted_until": _later(30),
        },
    )
    assert (accepted["status"], accepted["note"]) == ("accepted", "Owner hired next month")
    assert key not in {r["key"] for r in await ws.call("GET", "/risks")}
    assert key in {r["key"] for r in await ws.call("GET", "/risks", params={"status": "accepted"})}
    overview = await ws.call("GET", "/overview")
    assert overview["accepted_risks"] == 1

    # The acceptance date passes: the risk is open again on the next read.
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(ws.id),))
        conn.execute(
            "UPDATE risks.risk_record SET accepted_until = now() - interval '1 minute' "
            "WHERE risk_key = %s",
            (key,),
        )
    reopened = {r["key"]: r for r in await ws.call("GET", "/risks")}
    assert reopened[key]["status"] == "open"

    # Fixing the catalogue resolves it automatically, with a timestamp.
    ada = await ws.person("Ada")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"person_id": ada, "role": "primary"},
    )
    assert key not in {r["key"] for r in await ws.call("GET", "/risks", params={"status": "all"})}
    resolved = {r["key"]: r for r in await ws.call("GET", "/risks/resolved")}
    assert resolved[key]["resolved_at"]
    assert resolved[key]["subject"] == "Payments"

    # If the condition comes back it is a fresh, open risk.
    detail = await ws.call("GET", f"/responsibilities/{rid}")
    assignment = detail["owners_as_of"][0]["id"]
    await ws.call("POST", f"/responsibilities/{rid}/assignments/{assignment}/end", json={})
    again = {r["key"]: r for r in await ws.call("GET", "/risks")}
    assert (again[key]["status"], again[key]["note"]) == ("open", None)

    actions = [e["action"] for e in await ws.call("GET", "/audit-events", params={"limit": 200})]
    for expected in (
        "risk.acknowledged",
        "risk.accepted",
        "risk.acceptance_expired",
        "risk.resolved",
        "risk.recurred",
    ):
        assert expected in actions


async def test_only_managers_decide_and_unknown_or_cross_workspace_keys_are_rejected(
    api: Api, ws: Ws
) -> None:
    rid = await ws.responsibility("Payments")
    key = f"no_backup:{rid}"
    await ws.call("GET", "/risks")
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    assert key in {r["key"] for r in await member.call("GET", "/risks")}
    await member.call("POST", "/risks/decision", 403, json={"key": key, "action": "acknowledge"})

    await ws.call(
        "POST", "/risks/decision", 404, json={"key": "no_backup:nope", "action": "acknowledge"}
    )
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    await other.call("POST", "/risks/decision", 404, json={"key": key, "action": "acknowledge"})
    await ws.call("POST", "/risks/decision", 409, json={"key": key, "action": "reopen"})


async def test_assign_and_open_case_from_a_risk(api: Api, ws: Ws) -> None:
    rid = await ws.responsibility("Payments", "high")
    key = f"no_primary_owner:{rid}"
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    member_id = next(
        m["user_id"] for m in await ws.call("GET", "/members") if m["role"] == "member"
    )

    await member.call("POST", "/risks/assign", 403, json={"key": key, "user_id": member_id})
    assigned = await ws.call("POST", "/risks/assign", json={"key": key, "user_id": member_id})
    assert (assigned["status"], assigned["assignee_user_id"]) == ("in_remediation", member_id)
    assert assigned["assignee_name"]
    await ws.call("POST", "/risks/assign", 409, json={"key": key, "user_id": member_id})

    opened = await ws.call("POST", "/risks/case", json={"key": key})
    case = await ws.call("GET", f"/cases/{opened['case_id']}")
    assert case["case_type"] == "transfer"
    assert [s["responsibility_id"] for s in case["scope"]] == [rid]
    await ws.call("POST", "/risks/case", 409, json={"key": key})
