"""Responsibility knowledge: capture, freshness, full-text search, visibility, handover."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

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
    workspace = Ws(api, await api.create_workspace(OWNER, "Acme"))
    await add_member(api, workspace.id, "user_member", "member")
    return workspace


def iso(delta: timedelta = timedelta()) -> str:
    return (datetime.now(UTC) + delta).isoformat()


async def note(ws: Ws, rid: str, title: str, **extra: Any) -> Any:
    body = {"kind": "procedure", "title": title, "body": f"{title} steps", **extra}
    return await ws.call("POST", f"/responsibilities/{rid}/knowledge", 201, json=body)


async def test_capture_review_freshness_and_search(api: Api, ws: Ws) -> None:
    rid = await ws.responsibility("Payments on-call", "critical")
    empty = await ws.responsibility("Quarterly audit")
    member = Ws(api, ws.id, "user_member")

    runbook = await member.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={
            "kind": "procedure",
            "title": "Rotate the Stripe webhook secret",
            "body": "1. Open the dashboard",
        },
    )
    assert (runbook["origin"], runbook["freshness"], runbook["author_name"]) == (
        "person",
        "fresh",
        "Member",
    )
    link = await note(
        ws, rid, "Incident channel", kind="link", body=None, url="https://chat.example/payments"
    )
    await ws.call(
        "POST", f"/responsibilities/{rid}/knowledge", 422, json={"kind": "note", "title": "Empty"}
    )
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        422,
        json={"kind": "link", "title": "Bad", "url": "javascript:alert(1)"},
    )

    found = await ws.call("GET", "/knowledge", params={"q": "stripe secret"})
    assert [k["title"] for k in found["results"]] == ["Rotate the Stripe webhook secret"]
    overview = await ws.call("GET", "/knowledge")
    assert [m["responsibility_name"] for m in overview["missing"]] == ["Quarterly audit"]
    assert empty in {m["responsibility_id"] for m in overview["missing"]}

    # Age the link past the review window: it becomes stale until someone reviews it.
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(ws.id),))
        conn.execute(
            "UPDATE catalog.knowledge_item SET last_reviewed_at = now() - interval '120 days', "
            "created_at = now() - interval '200 days' WHERE id = %s",
            (link["id"],),
        )
    stale = await ws.call("GET", "/knowledge", params={"freshness": "stale"})
    assert [k["id"] for k in stale["results"]] == [link["id"]]
    reviewed = await member.call("POST", f"/knowledge/{link['id']}/review")
    assert (reviewed["freshness"], reviewed["last_reviewed_by_name"]) == ("fresh", "Member")

    # Authors edit their own items; others need to manage responsibilities.
    await member.call(
        "PATCH", f"/knowledge/{runbook['id']}", json={"title": "Rotate Stripe secrets"}
    )
    await member.call("PATCH", f"/knowledge/{link['id']}", 403, json={"title": "Mine now"})
    archived = await ws.call("PATCH", f"/knowledge/{runbook['id']}", json={"status": "archived"})
    assert archived["status"] == "archived"
    assert [k["id"] for k in await ws.call("GET", f"/responsibilities/{rid}/knowledge")] == [
        link["id"]
    ]
    actions = {
        e["action"] for e in await ws.call("GET", "/audit-events", params={"category": "knowledge"})
    }
    assert {
        "knowledge.created",
        "knowledge.reviewed",
        "knowledge.updated",
        "knowledge.archived",
    } <= actions


async def test_visibility_and_isolation(api: Api, ws: Ws) -> None:
    rid = await ws.responsibility("Payroll")
    restricted = await note(ws, rid, "Payroll provider credentials process", visibility="managers")
    open_note = await note(ws, rid, "Payroll calendar")
    member = Ws(api, ws.id, "user_member")
    assert [k["id"] for k in await member.call("GET", f"/responsibilities/{rid}/knowledge")] == [
        open_note["id"]
    ]
    assert (await member.call("GET", "/knowledge", params={"q": "credentials"}))["results"] == []
    await member.call("POST", f"/knowledge/{restricted['id']}/review", 404)
    await member.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        403,
        json={"kind": "note", "title": "x", "body": "y", "visibility": "managers"},
    )
    await add_member(api, ws.id, "user_guest", "guest")
    await Ws(api, ws.id, "user_guest").call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        403,
        json={"kind": "note", "title": "x", "body": "y"},
    )

    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    await other.call("GET", f"/responsibilities/{rid}/knowledge", 404)
    assert (await other.call("GET", "/knowledge"))["results"] == []
    await other.call("POST", f"/knowledge/{open_note['id']}/review", 404)


async def test_case_surfaces_knowledge_and_records_handover(api: Api, ws: Ws) -> None:
    old, new = await ws.person("Old"), await ws.person("New")
    rid = await ws.responsibility("Deploys")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "person_id": old},
    )
    runbook = await note(ws, rid, "Deploy runbook")
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={"case_type": "transfer", "title": "Old leaves", "starts_at": iso()},
    )
    other_rid = await ws.responsibility("Unrelated")
    await ws.call("POST", f"/cases/{case['id']}/scope", 201, json={"responsibility_id": rid})

    [entry] = await ws.call("GET", f"/cases/{case['id']}/knowledge")
    assert [k["title"] for k in entry["knowledge"]] == ["Deploy runbook"]

    path = f"/cases/{case['id']}/knowledge"
    after = await ws.call(
        "POST",
        path,
        201,
        json={
            "responsibility_id": rid,
            "outcome": "handed_over",
            "knowledge_item_id": runbook["id"],
        },
    )
    assert after[0]["records"][0]["outcome"] == "handed_over"
    await ws.call(
        "POST",
        path,
        409,
        json={
            "responsibility_id": rid,
            "outcome": "handed_over",
            "knowledge_item_id": runbook["id"],
        },
    )
    await ws.call("POST", path, 422, json={"responsibility_id": rid, "outcome": "missing"})
    missing = await ws.call(
        "POST",
        path,
        201,
        json={
            "responsibility_id": rid,
            "outcome": "missing",
            "note": "Rollback steps live only in Old's head",
        },
    )
    assert [r["outcome"] for r in missing[0]["records"]] == ["handed_over", "missing"]
    await ws.call(
        "POST", path, 422, json={"responsibility_id": other_rid, "outcome": "missing", "note": "x"}
    )
    await Ws(api, ws.id, "user_member").call(
        "POST", path, 403, json={"responsibility_id": rid, "outcome": "missing", "note": "x"}
    )
    # Ownership is untouched by any of this.
    detail = await ws.call("GET", f"/responsibilities/{rid}")
    assert [o["assignee"]["id"] for o in detail["owners_as_of"]] == [old]
    assert new != old
