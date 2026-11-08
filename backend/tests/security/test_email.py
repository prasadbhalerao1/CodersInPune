"""Email delivery: preferences, idempotency, retries, failures, invitations, no leaks.

Resend is simulated (tests/fakes.py) with its documented behaviour, including replaying
the original response for a repeated Idempotency-Key.
"""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from relay.jobs import outbox
from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import INSPECTOR_URL, OWNER_URL, count_rows, libpq_url
from tests.fakes import FakeExternal

pytestmark = pytest.mark.anyio


@pytest.fixture
def ext() -> FakeExternal:
    return FakeExternal()


@pytest.fixture
async def api(ext: FakeExternal) -> AsyncIterator[Api]:
    async with make_api(ext, **ext.email_settings, workos_api_key="sk_test_fake") as a:
        yield a


def set_email(workspace: uuid.UUID, user_id: str, email: str, name: str) -> None:
    """Simulates the WorkOS profile sync that fills membership email/name."""
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(workspace),))
        conn.execute(
            "UPDATE identity.membership SET email = %s, display_name = %s WHERE user_id = %s",
            (email, name, user_id),
        )


async def fill_emails(ws: Ws) -> None:
    for m in await ws.call("GET", "/members"):
        set_email(ws.id, m["user_id"], f"{m['role']}@acme.test", m["role"].title())


@pytest.fixture
async def ws(api: Api) -> Ws:
    workspace = Ws(api, await api.create_workspace(OWNER, "Acme"))
    for sub, role in (("user_admin", "admin"), ("user_member", "member")):
        await add_member(api, workspace.id, sub, role)
    await fill_emails(workspace)
    return workspace


async def run(api: Api, workspace: uuid.UUID, event_type: str) -> list[bool | Exception]:
    ctx = outbox.JobContext(
        http=api.app.state.http, settings=api.app.state.settings, jobs=api.app.state.jobs
    )
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        events = conn.execute(
            "SELECT id FROM platform.outbox_event WHERE tenant_id = %s AND event_type = %s "
            "AND processed_at IS NULL ORDER BY id",
            (workspace, event_type),
        ).fetchall()
    results: list[bool | Exception] = []
    for (event_id,) in events:
        try:
            results.append(
                await outbox.process(api.app.state.session_factory, workspace, event_id, ctx)
            )
        except Exception as exc:  # a failed attempt, as the worker would see it
            results.append(exc)
    return results


async def user_ids(ws: Ws) -> dict[str, str]:
    return {m["role"]: m["user_id"] for m in await ws.call("GET", "/members")}


async def case_with_task(ws: Ws, assignee: str) -> dict[str, Any]:
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "transfer",
            "title": "Priya's confidential exit",
            "starts_at": datetime.now(UTC).isoformat(),
        },
    )
    await ws.call(
        "POST",
        f"/cases/{case['id']}/tasks",
        201,
        json={
            "title": "Rotate prod keys",
            "assignee_user_id": assignee,
            "due_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        },
    )
    return dict(case)


async def test_emails_follow_notifications_once_and_respect_preferences(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    ids = await user_ids(ws)
    member = Ws(api, ws.id, "user_member")
    prefs = await member.call(
        "PUT", "/notifications/preferences", json={"preferences": {"reminders": False}}
    )
    assert {p["category"]: p["enabled"] for p in prefs}["reminders"] is False

    await case_with_task(ws, ids["member"])
    await run(api, ws.id, "notification.requested")  # in-app first (incl. reminders, early)
    await run(api, ws.id, "notification.requested")  # redelivery of the same events: no-op
    await run(api, ws.id, "email.send")
    await run(api, ws.id, "email.send")

    kinds = sorted(n["kind"] for n in (await member.call("GET", "/notifications"))["items"])
    assert kinds == ["task_assigned", "task_due_soon", "task_overdue"]  # in-app unaffected
    assert [e["to"] for e in ext.emails] == [["member@acme.test"]]  # reminders opted out
    [mail] = ext.emails
    assert mail["subject"] == "New task in Acme"  # generic: no case or task title
    assert "Priya" not in mail["subject"]
    assert "Rotate prod keys" in mail["text"]  # body names what the recipient can see
    assert f"https://relay.test/w/{ws.id}/cases/" in mail["html"]
    assert count_rows("notifications.email_delivery") == 1
    assert ext.resend_requests == 1


async def test_mentions_never_include_the_comment_text(api: Api, ws: Ws, ext: FakeExternal) -> None:
    ids = await user_ids(ws)
    case = await case_with_task(ws, ids["admin"])
    await ws.call(
        "POST",
        f"/cases/{case['id']}/comments",
        201,
        json={"body": "The root password is hunter2", "mention_user_ids": [ids["member"]]},
    )
    await run(api, ws.id, "notification.requested")
    await run(api, ws.id, "email.send")
    mention = next(e for e in ext.emails if e["to"] == ["member@acme.test"])
    assert "hunter2" not in mention["html"] + mention["text"] + mention["subject"]
    assert mention["subject"] == "You were mentioned in Acme"


async def test_transient_failures_retry_with_the_same_key_then_fail_visibly(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    ids = await user_ids(ws)
    await Ws(api, ws.id, "user_member").call(
        "PUT", "/notifications/preferences", json={"preferences": {"reminders": False}}
    )
    ext.resend_script = ["500", "timeout"]
    await case_with_task(ws, ids["member"])
    await run(api, ws.id, "notification.requested")
    first = await run(api, ws.id, "email.send")
    second = await run(api, ws.id, "email.send")
    third = await run(api, ws.id, "email.send")
    assert isinstance(first[0], Exception) and isinstance(second[0], Exception)
    assert third == [True]
    assert len(ext.emails) == 1  # one email despite three attempts
    status = "SELECT status, attempts FROM notifications.email_delivery"
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        assert conn.execute(status).fetchone() == ("sent", 3)

    # A provider that keeps failing ends as a visible failure after the retry budget.
    ext.resend_script = ["503"] * 10
    await ws.call(
        "POST",
        f"/cases/{(await case_with_task(ws, ids['member']))['id']}/tasks",
        201,
        json={"title": "Second", "assignee_user_id": ids["member"]},
    )
    await run(api, ws.id, "notification.requested")
    for _ in range(6):
        await run(api, ws.id, "email.send")
    status_view = await ws.call("GET", "/email/status")
    assert status_view["configured"] is True
    assert status_view["healthy"] is False
    assert {f["last_error"] for f in status_view["recent_failures"]} == {"provider_503"}
    assert "re_test_key" not in str(status_view)


async def test_permanent_rejection_fails_and_admin_retry_uses_a_new_key(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    ids = await user_ids(ws)
    await Ws(api, ws.id, "user_member").call(
        "PUT", "/notifications/preferences", json={"preferences": {"reminders": False}}
    )
    ext.resend_script = ["422"]
    await case_with_task(ws, ids["member"])
    await run(api, ws.id, "notification.requested")
    assert await run(api, ws.id, "email.send") == [True]  # handled: no retry storm
    [failure] = (await ws.call("GET", "/email/status"))["recent_failures"]
    assert failure["last_error"] == "rejected_422_validation_error"
    assert failure["recipient"] == "me…@acme.test"

    await Ws(api, ws.id, "user_member").call(
        "POST", f"/email/deliveries/{failure['id']}/retry", 403
    )
    await ws.call("POST", f"/email/deliveries/{failure['id']}/retry")
    await ws.call("POST", f"/email/deliveries/{failure['id']}/retry", 409)  # now pending
    await run(api, ws.id, "email.send")
    assert len(ext.emails) == 1
    assert not ext.emails[0]["idempotency_key"].endswith("-g0")  # a fresh generation


async def test_invitations_are_emailed_by_relay_when_configured(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    invitation = await ws.call(
        "POST", "/invitations", 201, json={"email": "new@acme.test", "role": "member"}
    )
    assert invitation["email_sent"] is True
    assert ext.sent_invitations == []  # WorkOS not used when Relay email is configured
    await run(api, ws.id, "email.send")
    [mail] = ext.emails
    assert (mail["to"], mail["subject"]) == (["new@acme.test"], "You're invited to Acme on Relay")
    assert "https://relay.test/invitations" in mail["html"]

    # A revoked invitation is not emailed even if its job runs late.
    second = await ws.call(
        "POST", "/invitations", 201, json={"email": "late@acme.test", "role": "member"}
    )
    await ws.call("POST", f"/invitations/{second['id']}/revoke")
    await run(api, ws.id, "email.send")
    assert len(ext.emails) == 1


async def test_removed_members_are_not_emailed(api: Api, ws: Ws, ext: FakeExternal) -> None:
    ids = await user_ids(ws)
    await case_with_task(ws, ids["member"])
    await run(api, ws.id, "notification.requested")
    await ws.call("PATCH", f"/members/{ids['member']}", json={"status": "removed"})
    await run(api, ws.id, "email.send")
    assert ext.emails == []
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        assert conn.execute(
            "SELECT status, last_error FROM notifications.email_delivery"
        ).fetchone() == (
            "skipped",
            "no_longer_relevant",
        )


async def test_without_configuration_only_in_app_notifications(ext: FakeExternal) -> None:
    async with make_api(ext) as unconfigured:
        ws = Ws(unconfigured, await unconfigured.create_workspace(OWNER, "Acme"))
        await add_member(unconfigured, ws.id, "user_member", "member")
        await fill_emails(ws)
        ids = await user_ids(ws)
        await case_with_task(ws, ids["member"])
        await run(unconfigured, ws.id, "notification.requested")
        assert count_rows("notifications.email_delivery") == 0
        assert (await Ws(unconfigured, ws.id, "user_member").call("GET", "/notifications"))[
            "unread"
        ] >= 1
        status = await ws.call("GET", "/email/status")
        assert (status["configured"], status["sender"]) == (False, None)


async def test_status_is_admin_only_and_isolated(api: Api, ws: Ws) -> None:
    await Ws(api, ws.id, "user_member").call("GET", "/email/status", 403)
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    assert (await other.call("GET", "/email/status"))["recent_failures"] == []
    await other.call("POST", f"/email/deliveries/{uuid.uuid4()}/retry", 404)
