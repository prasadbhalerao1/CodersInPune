"""Scoped roles, member types, reporting lines, membership history, profiles, identity
review and the roles registry."""

from collections.abc import AsyncIterator

import pytest

from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.security.test_cases import iso, owned

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


async def user_id(ws: Ws, role: str) -> str:
    return str(next(m["user_id"] for m in await ws.call("GET", "/members") if m["role"] == role))


async def test_scoped_and_specialist_roles(api: Api, ws: Ws) -> None:
    for sub, role in (
        ("user_tm", "team_manager"),
        ("user_cm", "continuity_manager"),
        ("user_ks", "knowledge_steward"),
        ("user_member", "member"),
    ):
        await add_member(api, ws.id, sub, role)
    tm, cm, ks, member = (
        Ws(api, ws.id, s) for s in ("user_tm", "user_cm", "user_ks", "user_member")
    )
    platform = await ws.call("POST", "/teams", 201, json={"name": "Platform"})
    other = await ws.call("POST", "/teams", 201, json={"name": "Sales"})
    asha = await ws.person("Asha")
    await ws.call("PUT", f"/teams/{platform['id']}/members/{asha}", 204)
    ours = await owned(ws, "Deploys", asha)  # held by a member of the scoped team
    theirs = await ws.responsibility("Quotas")
    await ws.call(
        "POST",
        f"/responsibilities/{theirs}/assignments",
        201,
        json={"role": "primary", "team_id": other["id"]},
    )

    tm_id = await user_id(ws, "team_manager")
    updated = await ws.call(
        "PATCH",
        f"/members/{tm_id}",
        json={"team_ids": [platform["id"]], "member_type": "contractor"},
    )
    assert updated["team_ids"] == [platform["id"]]
    assert updated["member_type"] == "contractor"
    backup = await ws.person("Ben")
    await tm.call(
        "POST",
        f"/responsibilities/{ours}/assignments",
        201,
        json={"role": "backup", "person_id": backup},
    )
    await tm.call(
        "POST",
        f"/responsibilities/{theirs}/assignments",
        403,
        json={"role": "backup", "person_id": backup},
    )
    await tm.call("POST", "/responsibilities", 403, json={"name": "New"})

    # Continuity managers run cases but don't administer the workspace.
    case = await cm.call(
        "POST", "/cases", 201, json={"case_type": "transfer", "title": "T", "starts_at": iso()}
    )
    assert case["status"] == "draft"
    await cm.call("PATCH", f"/members/{tm_id}", 403, json={"role": "member"})

    # Knowledge stewards verify anyone's drafts.
    draft = await member.call(
        "POST",
        f"/responsibilities/{ours}/knowledge",
        201,
        json={"kind": "note", "title": "Rollback", "body": "Use the previous tag."},
    )
    assert draft["state"] == "draft"
    assert (await ks.call("POST", f"/knowledge/{draft['id']}/review"))["state"] == "verified"

    roles = {r["role"]: r for r in await member.call("GET", "/roles")}
    assert "knowledge.verify" in roles["knowledge_steward"]["permissions"]
    assert "member.manage" not in roles["continuity_manager"]["permissions"]


async def test_reporting_lines_history_profiles_and_identity_review(ws: Ws) -> None:
    dept = await ws.call("POST", "/departments", 201, json={"name": "Engineering"})
    lead = await ws.call("POST", "/people", 201, json={"display_name": "Lead"})
    dev = await ws.call(
        "POST",
        "/people",
        201,
        json={
            "display_name": "Dev",
            "manager_person_id": lead["id"],
            "department_id": dept["id"],
            "email": "dev@acme.test",
        },
    )
    await ws.call("POST", "/people", 201, json={"display_name": "Dev 2", "email": "DEV@acme.test"})
    await ws.call(
        "PATCH", f"/people/{lead['id']}", 422, json={"manager_person_id": dev["id"]}
    )  # a reporting loop
    team = await ws.call("POST", "/teams", 201, json={"name": "Core"})
    await ws.call("PUT", f"/teams/{team['id']}/members/{dev['id']}", 204)
    await ws.call("DELETE", f"/teams/{team['id']}/members/{dev['id']}", 204)

    profile = await ws.call("GET", f"/people/{dev['id']}/profile")
    assert profile["reports_to"]["name"] == "Lead"
    assert [h["change"] for h in profile["history"]] == [
        "left_team",
        "joined_team",
        "joined_department",
    ]
    assert [
        r["name"] for r in (await ws.call("GET", f"/people/{lead['id']}/profile"))["direct_reports"]
    ] == ["Dev"]

    rid = await ws.responsibility("Core API", "critical")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "team_id": team["id"]},
    )
    coverage = (await ws.call("GET", f"/teams/{team['id']}/profile"))["coverage"]
    assert coverage == {
        "responsibilities": 1,
        "critical": 1,
        "without_backup": 1,
        "single_holder": 1,
    }
    breakdown = (await ws.call("GET", f"/departments/{dept['id']}/profile"))["risk_breakdown"]
    assert set(breakdown) == {"high", "medium", "low"}

    conflicts = await ws.call("GET", "/identity-conflicts")
    assert [c["kind"] for c in conflicts] == ["duplicate_email"]
