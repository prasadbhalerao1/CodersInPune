"""Insights: coverage, knowledge health, operations and a transparent Continuity Debt."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.fakes import FakeExternal

pytestmark = pytest.mark.anyio


def iso(delta: timedelta = timedelta()) -> str:
    return (datetime.now(UTC) + delta).isoformat()


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(FakeExternal()) as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


async def assign(ws: Ws, rid: str, role: str, person: str) -> None:
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": role, "person_id": person},
    )


async def test_debt_is_the_sum_of_its_explained_components(ws: Ws) -> None:
    ada, bo = await ws.person("Ada"), await ws.person("Bo")
    payroll = await ws.responsibility("Payroll", "critical")
    await assign(ws, payroll, "primary", ada)
    await assign(ws, payroll, "backup", bo)
    await ws.call(
        "POST",
        f"/responsibilities/{payroll}/knowledge",
        201,
        json={"kind": "procedure", "title": "Run payroll", "body": "Steps"},
    )
    await ws.responsibility("Vendor portal", "high")  # no owner, no backup, no knowledge

    view = await ws.call("GET", "/insights")
    cov = view["coverage"]
    assert (cov["responsibilities"], cov["with_primary"], cov["with_backup"]) == (2, 1, 1)
    assert (cov["critical"], cov["critical_with_backup"]) == (1, 1)
    assert view["knowledge"]["responsibilities_missing_knowledge"] == 1

    debt = {c["key"]: c for c in view["debt"]}
    assert view["continuity_debt"] == sum(c["points"] for c in view["debt"])
    for component in view["debt"]:
        assert component["points"] == sum(i["points"] for i in component["items"])
        assert component["rule"]
    risks = debt["ownership_risks"]["items"]
    assert {i["label"] for i in risks} == {"Vendor portal"}
    assert {i["detail"] for i in risks} == {"No primary owner", "No backup"}
    assert debt["missing_knowledge"]["items"] == [
        {
            "label": "Vendor portal",
            "detail": "High, no knowledge",
            "kind": "responsibility",
            "id": risks[0]["id"],
            "points": 2,
        }
    ]
    # Fixing the gap lowers the debt by exactly the item's points.
    before = view["continuity_debt"]
    await ws.call(
        "POST",
        f"/responsibilities/{risks[0]['id']}/knowledge",
        201,
        json={"kind": "link", "title": "Portal", "url": "https://vendor.test"},
    )
    assert (await ws.call("GET", "/insights"))["continuity_debt"] == before - 2


async def test_accepted_risks_are_excluded_but_reported(ws: Ws) -> None:
    rid = await ws.responsibility("Office keys", "low")
    before = await ws.call("GET", "/insights")
    [risk] = [r for r in await ws.call("GET", "/risks") if r["rule"] == "no_backup"]
    await ws.call(
        "POST",
        "/risks/decision",
        json={
            "key": risk["key"],
            "action": "accept",
            "note": "Fine",
            "accepted_until": iso(timedelta(days=30)),
        },
    )
    after = await ws.call("GET", "/insights")
    assert after["operations"]["accepted_risks"] == 1
    assert after["continuity_debt"] == before["continuity_debt"] - 1
    assert rid


async def test_operations_and_filters(ws: Ws) -> None:
    eng = await ws.call("POST", "/departments", 201, json={"name": "Engineering"})
    ada = (
        await ws.call(
            "POST", "/people", 201, json={"display_name": "Ada", "department_id": eng["id"]}
        )
    )["id"]
    infra = await ws.responsibility("Infra", "critical")
    await assign(ws, infra, "primary", ada)
    await ws.responsibility("Catering", "low")
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "coverage",
            "title": "Ada on leave",
            "affected_person_id": ada,
            "starts_at": iso(timedelta(days=-3)),
            "ends_at": iso(timedelta(days=-1)),
        },
    )
    await ws.call(
        "POST", f"/cases/{case['id']}/emergency", json={"emergency": True, "reason": "Sudden"}
    )
    await ws.call(
        "POST",
        f"/cases/{case['id']}/tasks",
        201,
        json={"title": "Hand over infra", "due_at": iso(timedelta(days=-1))},
    )

    view = await ws.call("GET", "/insights")
    ops = view["operations"]
    assert (ops["open_cases"], ops["emergency_cases"]) == (1, 1)
    assert (ops["overdue_cases"], ops["overdue_tasks"]) == (1, 1)
    assert {d["name"] for d in view["departments"]} == {"Engineering"}
    overdue = next(c for c in view["debt"] if c["key"] == "overdue_work")
    assert overdue["points"] == 3

    scoped = await ws.call("GET", "/insights", params={"department_id": eng["id"]})
    assert scoped["coverage"]["responsibilities"] == 1  # only what Engineering holds
    assert scoped["filters"]["department_id"] == eng["id"]
    low = await ws.call("GET", "/insights", params={"criticality": "low"})
    assert low["coverage"]["responsibilities"] == 1
    assert low["coverage"]["critical"] == 0


async def test_insights_are_for_managers_and_auditors_only(api: Api, ws: Ws) -> None:
    await add_member(api, ws.id, "user_auditor", "auditor")
    await add_member(api, ws.id, "user_member", "member")
    await Ws(api, ws.id, "user_auditor").call("GET", "/insights")
    await Ws(api, ws.id, "user_member").call("GET", "/insights", 403)
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    await ws.responsibility("Mine", "critical")
    assert (await other.call("GET", "/insights"))["coverage"]["responsibilities"] == 0


async def test_trend_metrics_show_definitions_and_denominators(ws: Ws) -> None:
    view = await ws.call("GET", "/insights/metrics", params={"days": 30})
    keys = [m["key"] for m in view["metrics"]]
    assert keys == [
        "handover_cycle_time",
        "readiness_completion",
        "knowledge_gap_resolution",
        "integration_failure_rate",
        "agent_acceptance",
    ]
    for m in view["metrics"]:
        assert m["definition"]
        assert m["limitations"]
        assert m["coverage"]
        assert m["denominator"] == 0
        assert m["value"] is None
    snap = await ws.call("POST", "/insights/snapshots", 201, params={"days": 30})
    assert [s["id"] for s in await ws.call("GET", "/insights/snapshots")] == [snap["id"]]
    await ws.call("GET", "/insights/metrics", 422, params={"days": 2})
