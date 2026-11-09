"""Person, team and department profiles: relationships, roles, risks, cases; isolated."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

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


async def test_profiles_show_structure_roles_risks_and_cases(api: Api, ws: Ws) -> None:
    eng = await ws.call("POST", "/departments", 201, json={"name": "Engineering"})
    ada = (
        await ws.call(
            "POST",
            "/people",
            201,
            json={"display_name": "Ada", "title": "SRE", "department_id": eng["id"]},
        )
    )["id"]
    team = await ws.call(
        "POST", "/teams", 201, json={"name": "Platform", "department_id": eng["id"]}
    )
    await ws.call("PUT", f"/teams/{team['id']}/members/{ada}", 204)
    payroll = await ws.responsibility("Payroll", "critical")
    await ws.call(
        "POST",
        f"/responsibilities/{payroll}/assignments",
        201,
        json={"role": "primary", "person_id": ada},
    )
    infra = await ws.responsibility("Infra", "high")
    await ws.call(
        "POST",
        f"/responsibilities/{infra}/assignments",
        201,
        json={"role": "primary", "team_id": team["id"]},
    )
    await ws.call("GET", "/risks")  # materialise detected risks
    await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "coverage",
            "title": "Ada on leave",
            "affected_person_id": ada,
            "starts_at": datetime.now(UTC).isoformat(),
            "ends_at": (datetime.now(UTC) + timedelta(days=5)).isoformat(),
        },
    )

    person = await ws.call("GET", f"/people/{ada}/profile")
    assert (person["title"], person["department"]["name"]) == ("SRE", "Engineering")
    assert [t["name"] for t in person["teams"]] == ["Platform"]
    assert [(r["responsibility_name"], r["role"]) for r in person["roles"]] == [
        ("Payroll", "primary")
    ]
    assert any(r["title"] == "No backup" for r in person["risks"])
    assert [c["relation"] for c in person["cases"]] == ["Affected person"]

    team_view = await ws.call("GET", f"/teams/{team['id']}/profile")
    assert [m["name"] for m in team_view["members"]] == ["Ada"]
    assert [r["responsibility_name"] for r in team_view["roles"]] == ["Infra"]

    dept = await ws.call("GET", f"/departments/{eng['id']}/profile")
    assert {r["responsibility_name"] for r in dept["roles"]} == {"Payroll", "Infra"}
    assert [p["name"] for p in dept["people"]] == ["Ada"]
    assert dept["continuity_debt"] > 0

    await add_member(api, ws.id, "user_guest", "guest")
    guest = await Ws(api, ws.id, "user_guest").call("GET", f"/departments/{eng['id']}/profile")
    assert guest["continuity_debt"] is None  # insights are for managers and auditors

    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    await other.call("GET", f"/people/{ada}/profile", 404)
    await other.call("GET", f"/teams/{team['id']}/profile", 404)
