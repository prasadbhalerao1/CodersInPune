"""Departments (lightweight grouping) and assets (stewarded by responsibilities)."""

from collections.abc import AsyncIterator

import pytest

from tests.api import OWNER, Api, Ws, add_member, make_api

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


async def test_departments_group_people_and_teams_and_filter_responsibilities(ws: Ws) -> None:
    eng = await ws.call("POST", "/departments", 201, json={"name": "Engineering"})
    ops = await ws.call("POST", "/departments", 201, json={"name": "Operations"})
    await ws.call("POST", "/departments", 409, json={"name": "Engineering"})

    ada = await ws.call(
        "POST", "/people", 201, json={"display_name": "Ada", "department_id": eng["id"]}
    )
    assert ada["department_name"] == "Engineering"
    team = await ws.call("POST", "/teams", 201, json={"name": "SRE", "department_id": ops["id"]})
    bob = await ws.person("Bob")

    api_r = await ws.responsibility("Payments API")
    oncall = await ws.responsibility("Pager rota")
    await ws.responsibility("Unowned thing")
    await ws.call(
        "POST",
        f"/responsibilities/{api_r}/assignments",
        201,
        json={"person_id": ada["id"], "role": "primary"},
    )
    await ws.call(
        "POST",
        f"/responsibilities/{oncall}/assignments",
        201,
        json={"team_id": team["id"], "role": "primary"},
    )
    await ws.call(
        "POST",
        f"/responsibilities/{oncall}/assignments",
        201,
        json={"person_id": bob, "role": "backup"},
    )

    in_eng = await ws.call("GET", "/responsibilities", params={"department_id": eng["id"]})
    assert [r["name"] for r in in_eng] == ["Payments API"]
    in_ops = await ws.call("GET", "/responsibilities", params={"department_id": ops["id"]})
    assert [r["name"] for r in in_ops] == ["Pager rota"]
    people = await ws.call("GET", "/people", params={"department_id": eng["id"]})
    assert [p["display_name"] for p in people] == ["Ada"]

    detail = await ws.call("GET", f"/responsibilities/{api_r}")
    assert detail["owners_as_of"][0]["assignee"]["department_name"] == "Engineering"

    listed = {d["name"]: d for d in await ws.call("GET", "/departments")}
    assert (listed["Engineering"]["people_count"], listed["Operations"]["team_count"]) == (1, 1)

    archived = await ws.call("PATCH", f"/departments/{ops['id']}", json={"status": "archived"})
    assert archived["status"] == "archived"
    assert [d["name"] for d in await ws.call("GET", "/departments")] == ["Engineering"]
    await ws.call("PATCH", f"/people/{bob}", 422, json={"department_id": ops["id"]})


async def test_assets_are_linked_to_responsibilities_without_their_own_owners(ws: Ws) -> None:
    repo = await ws.call(
        "POST",
        "/assets",
        201,
        json={
            "name": "payments-api",
            "asset_type": "repository",
            "url": "https://github.com/acme/payments-api",
        },
    )
    vendor = await ws.call("POST", "/assets", 201, json={"name": "Stripe", "asset_type": "vendor"})
    await ws.call(
        "POST",
        "/assets",
        422,
        json={"name": "x", "asset_type": "repository", "url": "javascript:alert(1)"},
    )
    await ws.call("POST", "/assets", 422, json={"name": "x", "asset_type": "spaceship"})

    rid = await ws.responsibility("Payments operations", "critical")
    ada = await ws.person("Ada")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"person_id": ada, "role": "primary"},
    )
    await ws.call("POST", f"/responsibilities/{rid}/assets", 204, json={"asset_id": repo["id"]})
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assets",
        204,
        json={"asset_id": vendor["id"], "relationship": "uses"},
    )
    await ws.call("POST", f"/responsibilities/{rid}/assets", 409, json={"asset_id": repo["id"]})

    detail = await ws.call("GET", f"/responsibilities/{rid}")
    assert {(a["name"], a["relationship"]) for a in detail["assets"]} == {
        ("payments-api", "stewards"),
        ("Stripe", "uses"),
    }
    asset = await ws.call("GET", f"/assets/{repo['id']}")
    assert asset["responsibilities"][0]["primary_owner"]["name"] == "Ada"
    assert "owner" not in asset  # ownership lives on the responsibility only

    found = await ws.call("GET", "/assets", params={"q": "pay", "asset_type": "repository"})
    assert [a["name"] for a in found] == ["payments-api"]

    await ws.call("PATCH", f"/assets/{vendor['id']}", json={"status": "archived"})
    assert [a["name"] for a in await ws.call("GET", "/assets")] == ["payments-api"]
    other = await ws.responsibility("Other")
    await ws.call("POST", f"/responsibilities/{other}/assets", 422, json={"asset_id": vendor["id"]})

    await ws.call("DELETE", f"/responsibilities/{rid}/assets/{repo['id']}", 204)
    assert len((await ws.call("GET", f"/responsibilities/{rid}"))["assets"]) == 1
    actions = [e["action"] for e in await ws.call("GET", "/audit-events")]
    assert {"asset.created", "responsibility.asset_linked", "responsibility.asset_unlinked"} <= set(
        actions
    )


async def test_members_read_but_cannot_manage_and_workspaces_are_isolated(api: Api, ws: Ws) -> None:
    asset = await ws.call("POST", "/assets", 201, json={"name": "CRM", "asset_type": "service"})
    dept = await ws.call("POST", "/departments", 201, json={"name": "Sales"})
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    assert len(await member.call("GET", "/assets")) == 1
    await member.call("POST", "/assets", 403, json={"name": "x", "asset_type": "service"})
    await member.call("POST", "/departments", 403, json={"name": "x"})
    await member.call("PATCH", f"/assets/{asset['id']}", 403, json={"name": "y"})

    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    await other.call("GET", f"/assets/{asset['id']}", 404)
    assert await other.call("GET", "/assets") == []
    assert await other.call("GET", "/departments") == []
    await other.call("PATCH", f"/departments/{dept['id']}", 404, json={"name": "Stolen"})
    await other.call(
        "POST", "/people", 422, json={"display_name": "X", "department_id": dept["id"]}
    )
