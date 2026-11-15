""" "What if?" simulator: impact of a person becoming unavailable, computed without writes."""

from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.fakes import FakeExternal

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(FakeExternal()) as a:
        yield a


async def assign(ws: Ws, rid: str, role: str, person: str | None = None, team: str | None = None):  # type: ignore[no-untyped-def]
    body: dict[str, Any] = {"role": role}
    body["person_id" if person else "team_id"] = person or team
    await ws.call("POST", f"/responsibilities/{rid}/assignments", 201, json=body)


async def org(api: Api) -> tuple[Ws, dict[str, str]]:
    """Arjun holds deploys alone, on-call with Leo as backup, and is co-owner of billing."""
    ws = Ws(api, await api.create_workspace(OWNER, "Acme"))
    p = {n: await ws.person(n) for n in ("Arjun", "Leo", "Dev", "Maya")}
    r = {
        "deploys": await ws.responsibility("Production deployments", "critical"),
        "oncall": await ws.responsibility("Platform on-call", "critical"),
        "billing": await ws.responsibility("Billing exports", "standard"),
        "other": await ws.responsibility("Office plants", "low"),
    }
    await assign(ws, r["deploys"], "primary", p["Arjun"])
    await assign(ws, r["oncall"], "primary", p["Arjun"])
    await assign(ws, r["oncall"], "backup", p["Leo"])
    await assign(ws, r["billing"], "primary", p["Maya"])
    await assign(ws, r["billing"], "co_owner", p["Arjun"])
    await assign(ws, r["other"], "primary", p["Maya"])
    await ws.call(
        "POST",
        f"/responsibilities/{r['oncall']}/knowledge",
        201,
        json={"kind": "procedure", "title": "Paging", "body": "Use the rota."},
    )
    return ws, {**p, **r}


def simulate(ws: Ws, person: str, backup: str | None = None, expected: int = 200) -> Any:
    query = f"/simulation?person_id={person}" + (f"&backup_id={backup}" if backup else "")
    return ws.call("GET", query, expected)


def by_name(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["name"]: s for s in view["affected_responsibilities"]}


async def test_impact_of_removing_a_person(api: Api) -> None:
    ws, ids = await org(api)
    view = await simulate(ws, ids["Arjun"])
    affected = by_name(view)
    assert set(affected) == {"Production deployments", "Platform on-call", "Billing exports"}
    assert affected["Production deployments"]["cover"] == "uncovered"
    assert affected["Platform on-call"]["cover"] == "covered"
    assert affected["Platform on-call"]["covered_by"]["name"] == "Leo"
    assert view["uncovered_responsibilities"] == [ids["deploys"]]
    assert view["covered_by_backup"] == []
    # Critical responsibilities sort first; uncovered before covered.
    assert view["affected_responsibilities"][0]["name"] == "Production deployments"


async def test_exposed_risks_name_the_new_gaps(api: Api) -> None:
    ws, ids = await org(api)
    view = await simulate(ws, ids["Arjun"])
    kinds = {(e["kind"], e["responsibility_name"]) for e in view["exposed_risks"]}
    assert ("uncovered", "Production deployments") in kinds
    assert ("undocumented", "Production deployments") in kinds
    assert ("single_holder", "Platform on-call") in kinds  # only Leo would be left
    assert ("single_holder", "Billing exports") in kinds
    assert not any(n == "Platform on-call" and k == "undocumented" for k, n in kinds)
    assert view["exposed_risks"][0]["severity"] == "high"


async def test_a_backup_covering_everything_leaves_nothing_uncovered(api: Api) -> None:
    ws, ids = await org(api)
    baseline = await simulate(ws, ids["Arjun"])
    view = await simulate(ws, ids["Arjun"], ids["Dev"])
    assert view["uncovered_responsibilities"] == []
    assert view["covered_by_backup"] == [ids["deploys"]]
    deploys = by_name(view)["Production deployments"]
    assert (deploys["cover"], deploys["covered_by"]["name"]) == ("covered_by_backup", "Dev")
    assert view["backup"]["name"] == "Dev"
    assert view["backup_load"] == {"current_responsibilities": 0, "would_take_over": 1}
    assert view["baseline_score"] == baseline["readiness_score"]
    assert view["readiness_score"] > view["baseline_score"]


async def test_score_is_explained_and_full_for_someone_holding_nothing(api: Api) -> None:
    ws, ids = await org(api)
    view = await simulate(ws, ids["Dev"])
    assert view["affected_responsibilities"] == []
    assert view["readiness_score"] == 100
    assert "60%" in view["score_basis"]
    risky = await simulate(ws, ids["Arjun"])
    assert 0 <= risky["readiness_score"] < 100


async def test_team_held_responsibility_is_affected_only_when_they_are_the_last_member(
    api: Api,
) -> None:
    ws, ids = await org(api)
    team = (await ws.call("POST", "/teams", 201, json={"name": "FinOps"}))["id"]
    await ws.call("PUT", f"/teams/{team}/members/{ids['Maya']}", 204)
    close = await ws.responsibility("Month-end close", "critical")
    await assign(ws, close, "primary", team=team)
    assert "Month-end close" in by_name(await simulate(ws, ids["Maya"]))
    await ws.call("PUT", f"/teams/{team}/members/{ids['Leo']}", 204)
    assert "Month-end close" not in by_name(await simulate(ws, ids["Maya"]))


async def test_only_managers_can_simulate(api: Api) -> None:
    ws, ids = await org(api)
    for role in ("member", "guest", "auditor", "knowledge_steward"):
        await add_member(api, ws.id, f"user_{role}", role)
        await simulate(Ws(api, ws.id, f"user_{role}"), ids["Arjun"], expected=403)
    await add_member(api, ws.id, "user_cm", "continuity_manager")
    await simulate(Ws(api, ws.id, "user_cm"), ids["Arjun"])


async def test_other_workspaces_and_bad_input_are_rejected(api: Api) -> None:
    ws, ids = await org(api)
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    await simulate(other, ids["Arjun"], expected=404)
    await simulate(ws, ids["Arjun"], ids["Arjun"], expected=422)
    await ws.call("GET", "/simulation?person_id=not-a-uuid", 422)
    await ws.call("GET", "/simulation", 422)


@contextmanager
def statements() -> Iterator[list[str]]:
    seen: list[str] = []

    def record(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        seen.append(statement.lstrip().upper())

    event.listen(Engine, "before_cursor_execute", record)
    try:
        yield seen
    finally:
        event.remove(Engine, "before_cursor_execute", record)


async def test_simulation_writes_nothing(api: Api) -> None:
    ws, ids = await org(api)
    before = await ws.call("GET", f"/responsibilities/{ids['deploys']}")
    with statements() as seen:
        await simulate(ws, ids["Arjun"], ids["Dev"])
    assert seen, "the listener saw no statements"
    writes = [s for s in seen if s.startswith(("INSERT", "UPDATE", "DELETE", "MERGE"))]
    assert writes == []
    after = await ws.call("GET", f"/responsibilities/{ids['deploys']}")
    assert {**after, "as_of": None} == {**before, "as_of": None}


async def test_reasons_explain_why_each_responsibility_is_affected(api: Api) -> None:
    ws, ids = await org(api)
    deploys = by_name(await simulate(ws, ids["Arjun"]))["Production deployments"]
    assert deploys["reasons"][:2] == ["Arjun is primary owner.", "Nobody else holds it."]
    assert "No knowledge is recorded for it." in deploys["reasons"]


async def test_duration_flags_work_due_while_away(api: Api) -> None:
    ws, ids = await org(api)
    view = await ws.call("GET", f"/simulation?person_id={ids['Arjun']}&days=14")
    assert view["days"] == 14
    assert view["due_in_window"] == 0  # no dated tasks in this organisation
    await ws.call("GET", f"/simulation?person_id={ids['Arjun']}&days=0", 422)


async def test_candidates_are_compared_against_nobody_stepping_in(api: Api) -> None:
    ws, ids = await org(api)
    view = await ws.call("GET", f"/simulation/candidates?person_id={ids['Arjun']}")
    rows = view["candidates"]
    assert rows[-1]["person"] is None  # the "nobody" baseline is always last
    nobody = rows[-1]
    assert nobody["covered"] < nobody["total"]
    leo = next(r for r in rows if r["person"] and r["person"]["name"] == "Leo")
    assert "Already backup of Platform on-call" in leo["signals"]
    assert leo["covered"] == leo["total"]
    assert leo["critical_gaps"] == 0
    assert leo["readiness_score"] > nobody["readiness_score"]
    assert "No ranking model" in view["basis"]
    # Arjun 3, Leo 1, Maya 2: Leo taking over Arjun's work is busy but not overloaded.
    assert view["typical_load"] == 2.0
    assert not leo["overloaded"]
    # Candidates are simulated too: nothing was written.
    owners = await ws.call("GET", f"/responsibilities/{ids['deploys']}")
    assert [a["assignee"]["name"] for a in owners["assignments"] if a["state"] == "current"] == [
        "Arjun"
    ]


async def test_candidates_already_carrying_a_lot_are_flagged_as_overloaded(api: Api) -> None:
    ws, ids = await org(api)
    leo = await ws.call("GET", "/people")
    leo_id = next(p["id"] for p in leo if p["display_name"] == "Leo")
    for n in range(6):
        rid = await ws.responsibility(f"Leo's duty {n}")
        await assign(ws, rid, "primary", leo_id)
    view = await ws.call("GET", f"/simulation/candidates?person_id={ids['Arjun']}")
    row = next(r for r in view["candidates"] if r["person"] and r["person"]["name"] == "Leo")
    assert row["load_after"] >= 2 * view["typical_load"]
    assert row["overloaded"]
