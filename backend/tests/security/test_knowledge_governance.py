"""Knowledge governance: stewards verify, edits are versioned, disputes keep history,
duplicates surface, and the Markdown export never exceeds the reader's access."""

from collections.abc import AsyncIterator
from datetime import timedelta

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


async def test_knowledge_lifecycle_and_export(api: Api, ws: Ws) -> None:
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    member_id = next(
        m["user_id"] for m in await ws.call("GET", "/members") if m["role"] == "member"
    )
    person = await ws.person("Old")
    rid = await owned(ws, "Billing", person)

    draft = await member.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={"kind": "procedure", "title": "Month-end close", "body": "Run the ledger export."},
    )
    assert draft["state"] == "draft"
    denied = await member.call("POST", f"/knowledge/{draft['id']}/review", 403)
    assert denied["code"] == "steward_required"
    await ws.call("PATCH", f"/knowledge/{draft['id']}", json={"steward_user_id": member_id})
    verified = await member.call("POST", f"/knowledge/{draft['id']}/review")
    assert verified["state"] == "verified"

    # Edits are new immutable versions; the steward's own edit stays verified.
    edited = await member.call(
        "PATCH",
        f"/knowledge/{draft['id']}",
        json={"body": "Run the ledger export, then reconcile.", "change_note": "Added step"},
    )
    assert edited["version"] == 2
    assert edited["state"] == "verified"
    diff = await ws.call(
        "GET",
        f"/knowledge/{draft['id']}/compare",
        params={"from_version": 1, "to_version": 2},
    )
    assert "+Run the ledger export, then reconcile." in diff["diff"]

    # A dispute keeps the content and history; the steward sees it in My Work.
    await ws.call("POST", f"/knowledge/{draft['id']}/dispute", json={"reason": "Wrong ledger"})
    reviews = (await member.call("GET", "/my-work"))["reviews"]
    assert [r["title"] for r in reviews] == ["Month-end close"]
    gov = await ws.call("POST", f"/knowledge/{draft['id']}/feedback", 201, json={"kind": "stale"})
    assert [v["version"] for v in gov["versions"]] == [2, 1]
    assert gov["feedback"][0]["kind"] == "stale"

    dup = await ws.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={"kind": "procedure", "title": "Month-end close", "url": "https://x.test/close"},
    )
    assert [
        d["id"] for d in (await ws.call("GET", f"/knowledge/{dup['id']}/governance"))["duplicates"]
    ] == [draft["id"]]
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={
            "kind": "adr",
            "title": "Use Stripe for refunds",
            "body": "Secret pricing context",
            "visibility": "managers",
        },
    )
    expired = await ws.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={
            "kind": "faq",
            "title": "Old VPN",
            "body": "Use the old VPN",
            "valid_from": iso(timedelta(days=-60)),
            "valid_until": iso(timedelta(days=-1)),
        },
    )
    assert expired["state"] == "expired"

    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "departure",
            "title": "Old leaves",
            "affected_person_id": person,
            "starts_at": iso(),
        },
    )
    response = await api.client.get(
        f"/workspaces/{ws.id}/cases/{case['id']}/export.md", headers=api.as_user("user_member")
    )
    assert response.status_code == 200
    text = response.text
    assert "## Billing" in text
    assert "Secret pricing context" not in text  # managers-only: counted, never named
    assert "1 managers-only knowledge item(s)" in text
    assert "“Month-end close” (disputed)" in text  # left out until resolved
    assert "“Old VPN” (expired)" in text
    assert "| Month-end close | v1 | person |" in text  # the verified duplicate
