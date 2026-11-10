"""Export, retention, ownership transfer, classification and denial explanations."""

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


async def test_export_retention_transfer_and_classification(api: Api, ws: Ws) -> None:
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    rid = await ws.responsibility("Payroll")
    secret = await ws.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={
            "kind": "note",
            "title": "Salary bands",
            "body": "x",
            "classification": "confidential",
        },
    )
    assert (secret["classification"], secret["visibility"]) == ("confidential", "managers")
    assert [
        k["title"] for k in await member.call("GET", f"/responsibilities/{rid}/knowledge")
    ] == []
    await ws.call("PATCH", f"/knowledge/{secret['id']}", 409, json={"visibility": "workspace"})

    denied = await member.call("GET", "/export", 403)
    assert "owner" in denied["detail"]
    assert "admin" in denied["detail"]
    export = await ws.call("GET", "/export")
    assert export["format"] == "relay-workspace-export"
    assert [r["name"] for r in export["responsibilities"]] == ["Payroll"]
    assert export["knowledge"][0]["classification"] == "confidential"
    response = await api.client.get(
        f"/workspaces/{ws.id}/audit/export.csv", headers=api.as_user(OWNER)
    )
    assert response.status_code == 200
    assert response.text.startswith("occurred_at,action")
    assert "workspace.exported" in response.text

    await ws.call("PATCH", "/policy", json={"retention_days": 30})
    result = await ws.call("POST", "/retention/apply")
    assert result["retention_days"] == 30

    member_id = next(
        m["user_id"] for m in await ws.call("GET", "/members") if m["role"] == "member"
    )
    await member.call("POST", "/ownership/transfer", 403, json={"user_id": member_id})
    await ws.call("POST", "/ownership/transfer", 204, json={"user_id": member_id})
    roles = {m["user_id"]: m["role"] for m in await ws.call("GET", "/members")}
    assert roles[member_id] == "owner"
    assert "admin" in roles.values()
