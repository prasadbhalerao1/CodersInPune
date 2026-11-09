"""Case comments and mentions, the emergency flag, and asynchronous notifications."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from relay.jobs import outbox
from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import INSPECTOR_URL, count_rows, libpq_url

pytestmark = pytest.mark.anyio


def iso(delta: timedelta = timedelta()) -> str:
    return (datetime.now(UTC) + delta).isoformat()


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    workspace = Ws(api, await api.create_workspace(OWNER, "Acme"))
    for sub, role in (("user_admin", "admin"), ("user_member", "member"), ("user_guest", "guest")):
        await add_member(api, workspace.id, sub, role)
    return workspace


async def deliver(api: Api, workspace: uuid.UUID) -> int:
    """Run pending notification events now, as the worker would once they are due."""
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        events = conn.execute(
            "SELECT id FROM platform.outbox_event WHERE tenant_id = %s "
            "AND event_type = 'notification.requested' AND processed_at IS NULL ORDER BY id",
            (workspace,),
        ).fetchall()
    for (event_id,) in events:
        await outbox.process(api.app.state.session_factory, workspace, event_id)
    return len(events)


async def user_ids(ws: Ws) -> dict[str, str]:
    members = await ws.call("GET", "/members")
    return {m["role"]: m["user_id"] for m in members}


async def draft_transfer(ws: Ws, title: str = "Handover") -> dict[str, Any]:
    old, new = await ws.person(f"{title} old"), await ws.person(f"{title} new")
    rid = await ws.responsibility(f"{title} duty")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "person_id": old},
    )
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={"case_type": "transfer", "title": title, "starts_at": iso(timedelta(minutes=-1))},
    )
    item = (
        await ws.call("POST", f"/cases/{case['id']}/scope", 201, json={"responsibility_id": rid})
    )["scope"][0]
    await ws.call(
        "PATCH", f"/cases/{case['id']}/scope/{item['id']}", json={"recipient_person_id": new}
    )
    return dict(case)


async def test_comments_and_mentions_are_distinct_from_audit_events(api: Api, ws: Ws) -> None:
    ids = await user_ids(ws)
    case = await draft_transfer(ws)
    member = Ws(api, ws.id, "user_member")
    comment = await member.call(
        "POST",
        f"/cases/{case['id']}/comments",
        201,
        json={"body": "@Admin can you confirm access?", "mention_user_ids": [ids["admin"]]},
    )
    assert comment["kind"] == "comment"
    assert [m["user_id"] for m in comment["mentions"]] == [ids["admin"]]

    activity = await ws.call("GET", f"/cases/{case['id']}/activity")
    kinds = {a["kind"] for a in activity}
    assert kinds == {"comment", "event"}
    comments = [a for a in activity if a["kind"] == "comment"]
    assert comments[0]["body"] == "@Admin can you confirm access?"
    assert all(a["body"] is None for a in activity if a["kind"] == "event")
    added = [
        e for e in await ws.call("GET", "/audit-events") if e["action"] == "case.comment_added"
    ]
    assert added
    assert "body" not in added[0]["metadata"]  # metadata holds identifiers only

    guest = Ws(api, ws.id, "user_guest")
    await guest.call("POST", f"/cases/{case['id']}/comments", 403, json={"body": "hi"})
    await member.call(
        "POST",
        f"/cases/{case['id']}/comments",
        422,
        json={"body": "x", "mention_user_ids": [str(uuid.uuid4())]},
    )
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    await other.call("GET", f"/cases/{case['id']}/activity", 404)
    await other.call("POST", f"/cases/{case['id']}/comments", 404, json={"body": "x"})

    assert await deliver(api, ws.id) >= 1
    admin_inbox = await Ws(api, ws.id, "user_admin").call("GET", "/notifications")
    assert [n["kind"] for n in admin_inbox["items"]] == ["mentioned"]
    assert admin_inbox["items"][0]["actor_name"]


async def test_emergency_is_prominent_but_bypasses_nothing(api: Api, ws: Ws) -> None:
    calm = await draft_transfer(ws, "Calm")
    urgent = await draft_transfer(ws, "Urgent")
    await ws.call("POST", f"/cases/{urgent['id']}/emergency", 422, json={"emergency": True})
    member = Ws(api, ws.id, "user_member")
    await member.call(
        "POST", f"/cases/{urgent['id']}/emergency", 403, json={"emergency": True, "reason": "x"}
    )
    raised = await ws.call(
        "POST",
        f"/cases/{urgent['id']}/emergency",
        json={"emergency": True, "reason": "Owner hospitalised"},
    )
    assert (raised["emergency"], raised["emergency_reason"]) == (True, "Owner hospitalised")

    listed = await ws.call("GET", "/cases", params={"status": "open"})
    assert [c["title"] for c in listed][:1] == ["Urgent"]
    assert [c["title"] for c in (await member.call("GET", "/my-work"))["emergencies"]] == ["Urgent"]

    # Emergency changes nothing about approvals or ownership rules.
    await ws.call("POST", f"/cases/{urgent['id']}/submit")
    await ws.call("POST", f"/cases/{urgent['id']}/execute", 409)
    assert calm["emergency"] is False

    cleared = await ws.call("POST", f"/cases/{urgent['id']}/emergency", json={"emergency": False})
    assert (cleared["emergency"], cleared["emergency_reason"]) == (False, None)
    actions = {e["action"] for e in await ws.call("GET", "/audit-events")}
    assert {"case.emergency_raised", "case.emergency_cleared"} <= actions


async def test_notifications_are_async_idempotent_and_private(api: Api, ws: Ws) -> None:
    ids = await user_ids(ws)
    case = await draft_transfer(ws)
    before = count_rows("notifications.notification")
    await ws.call(
        "POST",
        f"/cases/{case['id']}/tasks",
        201,
        json={
            "title": "Share runbook",
            "assignee_user_id": ids["member"],
            "due_at": iso(timedelta(days=2)),
        },
    )
    assert count_rows("notifications.notification") == before  # nothing in the request itself
    assert count_rows("public.procrastinate_jobs", "scheduled_at IS NOT NULL") == 2  # reminders

    await ws.call("POST", f"/cases/{case['id']}/submit")
    await deliver(api, ws.id)
    await deliver(api, ws.id)  # redelivery is harmless

    member = Ws(api, ws.id, "user_member")
    admin = Ws(api, ws.id, "user_admin")
    member_inbox = await member.call("GET", "/notifications")
    assert sorted(n["kind"] for n in member_inbox["items"]) == [
        "task_assigned",
        "task_due_soon",
        "task_overdue",
    ]
    assert member_inbox["unread"] == 3
    admin_inbox = await admin.call("GET", "/notifications")
    assert [n["kind"] for n in admin_inbox["items"]] == ["approval_requested"]
    owner_inbox = await ws.call("GET", "/notifications")
    assert all(n["kind"] != "approval_requested" for n in owner_inbox["items"])  # not the actor

    first = member_inbox["items"][0]["id"]
    await member.call("POST", "/notifications/read", 204, json={"ids": [first]})
    assert (await member.call("GET", "/notifications"))["unread"] == 2
    await admin.call("POST", "/notifications/read", 204, json={"ids": [first]})  # not theirs
    assert (await member.call("GET", "/notifications"))["unread"] == 2
    await member.call("POST", "/notifications/read", 204, json={})
    assert (await member.call("GET", "/notifications", params={"unread_only": True}))["items"] == []

    # A reminder for a task that was completed in the meantime is dropped.
    task = await ws.call(
        "POST",
        f"/cases/{case['id']}/tasks",
        201,
        json={
            "title": "Quick check",
            "assignee_user_id": ids["member"],
            "due_at": iso(timedelta(days=3)),
        },
    )
    task_id = next(t["id"] for t in task["tasks"] if t["title"] == "Quick check")
    await member.call("PATCH", f"/cases/{case['id']}/tasks/{task_id}", json={"status": "done"})
    await deliver(api, ws.id)
    kinds = [
        n["kind"]
        for n in (await member.call("GET", "/notifications"))["items"]
        if n["task_title"] == "Quick check"
    ]
    assert kinds == ["task_assigned"]


async def test_my_work_lists_unread_mentions_and_my_stale_knowledge(api: Api, ws: Ws) -> None:
    case = await draft_transfer(ws, "Mentions")
    ids = await user_ids(ws)
    await ws.call(
        "POST",
        f"/cases/{case['id']}/comments",
        201,
        json={"body": "@Admin please check", "mention_user_ids": [ids["admin"]]},
    )
    await deliver(api, ws.id)
    admin = Ws(api, ws.id, "user_admin")
    work = await admin.call("GET", "/my-work")
    assert [(m["case_title"], m["actor_name"] is not None) for m in work["mentions"]] == [
        ("Mentions", True)
    ]
    await admin.call("POST", "/notifications/read", 204, json={})
    assert (await admin.call("GET", "/my-work"))["mentions"] == []  # read: gone

    rid = await ws.responsibility("Docs duty")
    item = await admin.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={"kind": "note", "title": "Old note", "body": "x"},
    )
    assert (await admin.call("GET", "/my-work"))["reviews"] == []  # fresh
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        conn.execute(
            "UPDATE catalog.knowledge_item SET last_reviewed_at = now() - interval '200 days' "
            "WHERE id = %s",
            (item["id"],),
        )
        conn.commit()
    [review] = (await admin.call("GET", "/my-work"))["reviews"]
    assert (review["title"], review["responsibility_id"]) == ("Old note", rid)
    assert (await ws.call("GET", "/my-work"))["reviews"] == []  # only the author's
