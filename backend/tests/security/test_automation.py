"""Automation Center and workspace policies."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest

from relay.automation import service as automation
from relay.jobs import outbox
from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import INSPECTOR_URL, count_rows, libpq_url
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


async def run_due(api: Api, workspace: uuid.UUID) -> int:
    """Process automation runs that are due now (not the next day's scheduled run)."""
    ctx = outbox.JobContext(
        http=api.app.state.http, settings=api.app.state.settings, jobs=api.app.state.jobs
    )
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        events = conn.execute(
            "SELECT id FROM platform.outbox_event WHERE tenant_id = %s AND processed_at IS NULL "
            "AND event_type = 'automation.run_requested' AND coalesce("
            "(payload->>'scheduled_for')::timestamptz, now()) <= now() ORDER BY id",
            (workspace,),
        ).fetchall()
    for (event_id,) in events:
        await outbox.process(api.app.state.session_factory, workspace, event_id, ctx)
    return len(events)


async def rules(ws: Ws) -> dict[str, dict[str, Any]]:
    return {r["template"]: r for r in await ws.call("GET", "/automations")}


async def test_eight_templates_disabled_by_default(ws: Ws) -> None:
    found = await rules(ws)
    assert len(found) == 8
    assert not any(r["enabled"] for r in found.values())
    assert all(r["title"] and r["description"] for r in found.values())


async def test_notify_is_idempotent_and_never_changes_ownership(api: Api, ws: Ws) -> None:
    rid = await ws.responsibility("Payroll", "critical")
    await ws.call("PATCH", "/automations/no_primary_owner", json={"enabled": True})
    assert await run_due(api, ws.id) == 1
    [rule] = [
        r for r in await ws.call("GET", "/automations") if r["template"] == "no_primary_owner"
    ]
    assert (rule["last_status"], rule["runs"][0]["matched"], rule["runs"][0]["actions"]) == (
        "ok",
        1,
        1,
    )
    assert rule["next_run_at"]  # the next daily run is scheduled
    inbox = await ws.call("GET", "/notifications")
    [alert] = inbox["items"]
    assert (alert["kind"], alert["detail"], alert["responsibility_id"]) == (
        "automation",
        "no_primary_owner",
        rid,
    )
    assert alert["case_id"] is None

    for _ in range(2):  # manual reruns in the same week notify nobody again
        await ws.call("POST", "/automations/no_primary_owner/run", 202)
        await run_due(api, ws.id)
    assert len((await ws.call("GET", "/notifications"))["items"]) == 1
    assert count_rows("automation.automation_run") == 3
    assert count_rows("catalog.ownership_assignment") == 0  # automations never assign owners


async def test_follow_ups_go_to_the_assignee_and_reopen_only_after_done(api: Api, ws: Ws) -> None:
    await add_member(api, ws.id, "user_admin", "admin")
    members = await ws.call("GET", "/members")
    admin_id = next(m["user_id"] for m in members if m["role"] == "admin")
    await ws.responsibility("Payroll", "critical")
    await ws.call(
        "PATCH",
        "/automations/critical_without_backup",
        json={"enabled": True, "action": "create_follow_up", "assignee_user_id": admin_id},
    )
    await run_due(api, ws.id)
    admin = Ws(api, ws.id, "user_admin")
    [follow_up] = await admin.call("GET", "/follow-ups")
    assert follow_up["title"] == "Assign a backup: Payroll"
    assert await ws.call("GET", "/follow-ups") == []  # not the owner's

    await ws.call("POST", "/automations/critical_without_backup/run", 202)
    await run_due(api, ws.id)
    assert len(await admin.call("GET", "/follow-ups")) == 1  # still open: not duplicated
    await admin.call("POST", f"/follow-ups/{follow_up['id']}/complete", 204)
    await ws.call("POST", "/automations/critical_without_backup/run", 202)
    await run_due(api, ws.id)
    assert len(await admin.call("GET", "/follow-ups")) == 1  # the gap remains: a new one

    await ws.call(
        "PATCH",
        "/automations/critical_without_backup",
        422,
        json={"assignee_user_id": str(uuid.uuid4())},
    )


async def test_failures_roll_back_and_retry_safely(
    api: Api, ws: Ws, monkeypatch: pytest.MonkeyPatch
) -> None:
    await ws.responsibility("Payroll", "high")
    spec = automation.SPECS["no_primary_owner"]

    async def broken(session: Any, now: datetime) -> list[automation.Match]:
        raise RuntimeError("boom")

    monkeypatch.setitem(
        automation.SPECS,
        "no_primary_owner",
        automation.Spec(spec.title, spec.description, spec.follow_up, broken),
    )
    await ws.call("POST", "/automations/no_primary_owner/retry", 409)  # nothing failed yet
    await ws.call("POST", "/automations/no_primary_owner/run", 202)
    await run_due(api, ws.id)
    [rule] = [
        r for r in await ws.call("GET", "/automations") if r["template"] == "no_primary_owner"
    ]
    assert (rule["last_status"], rule["runs"][0]["status"]) == ("failed", "failed")
    assert rule["last_error"].startswith("RuntimeError")
    assert "boom" not in rule["last_error"]  # error class only, no content

    monkeypatch.setitem(automation.SPECS, "no_primary_owner", spec)
    await ws.call("POST", "/automations/no_primary_owner/retry", 202)
    await run_due(api, ws.id)
    [rule] = [
        r for r in await ws.call("GET", "/automations") if r["template"] == "no_primary_owner"
    ]
    assert (rule["last_status"], rule["runs"][0]["trigger"]) == ("ok", "retry")
    assert len((await ws.call("GET", "/notifications"))["items"]) == 1


async def test_disabling_makes_scheduled_runs_no_ops(api: Api, ws: Ws) -> None:
    await ws.responsibility("Payroll", "high")
    await ws.call("PATCH", "/automations/no_primary_owner", json={"enabled": True})
    await ws.call("PATCH", "/automations/no_primary_owner", json={"enabled": False})
    await run_due(api, ws.id)
    assert count_rows("automation.automation_run") == 0
    assert (await rules(ws))["no_primary_owner"]["next_run_at"] is None


async def test_case_and_task_escalations(api: Api, ws: Ws) -> None:
    ada = await ws.person("Ada")
    case = await ws.call(
        "POST",
        "/cases",
        201,
        json={
            "case_type": "coverage",
            "title": "Ada away",
            "affected_person_id": ada,
            "starts_at": iso(timedelta(days=-3)),
            "ends_at": iso(timedelta(days=-1)),
        },
    )
    await ws.call(
        "POST",
        f"/cases/{case['id']}/tasks",
        201,
        json={"title": "Hand over", "due_at": iso(timedelta(hours=-2))},
    )
    for template in ("case_overdue", "task_overdue"):
        await ws.call("PATCH", f"/automations/{template}", json={"enabled": True})
    await run_due(api, ws.id)
    found = await rules(ws)
    assert found["case_overdue"]["runs"][0]["matched"] == 1
    assert found["task_overdue"]["runs"][0]["matched"] == 1


async def test_automations_are_admin_only_and_audited(api: Api, ws: Ws) -> None:
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    await member.call("GET", "/automations", 403)
    await member.call("PATCH", "/automations/no_primary_owner", 403, json={"enabled": True})
    await ws.call("PATCH", "/automations/nope", 404, json={"enabled": True})
    await ws.call("PATCH", "/automations/stale_knowledge", json={"enabled": True})
    assert count_rows("audit.audit_event", "action = 'automation.updated'") == 1


# ---------------------------------------------------------------- policies


async def test_policies_drive_risks_and_knowledge_and_are_audited(api: Api, ws: Ws) -> None:
    rid = await ws.responsibility("Payroll", "critical")
    policy = await ws.call("GET", "/policy")
    assert (policy["critical_requires_backup"], policy["knowledge_review_days"]) == (True, 90)
    no_backup = next(r for r in await ws.call("GET", "/risks") if r["rule"] == "no_backup")
    assert no_backup["severity"] == "high"

    await ws.call("PATCH", "/policy", json={"critical_requires_backup": False})
    no_backup = next(r for r in await ws.call("GET", "/risks") if r["rule"] == "no_backup")
    assert no_backup["severity"] == "medium"

    item = await ws.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={"kind": "note", "title": "How", "body": "Steps"},
    )
    assert item["freshness"] == "fresh"
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        conn.execute(
            "UPDATE catalog.knowledge_item SET last_reviewed_at = now() - interval '20 days'"
        )
    assert (await ws.call("GET", f"/responsibilities/{rid}/knowledge"))[0]["freshness"] == "fresh"
    updated = await ws.call("PATCH", "/policy", json={"knowledge_review_days": 14})
    assert updated["updated_by_name"]
    assert (await ws.call("GET", f"/responsibilities/{rid}/knowledge"))[0]["freshness"] == "stale"
    assert (await ws.call("GET", "/insights"))["knowledge"]["review_interval_days"] == 14

    await ws.call("PATCH", "/policy", 422, json={"knowledge_review_days": 3})
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    assert (await member.call("GET", "/policy"))["knowledge_review_days"] == 14
    await member.call("PATCH", "/policy", 403, json={"knowledge_review_days": 30})
    assert count_rows("audit.audit_event", "action = 'policy.updated'") == 2
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    assert (await other.call("GET", "/policy"))["knowledge_review_days"] == 90
