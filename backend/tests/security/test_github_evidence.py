"""M5b: GitHub identities, teams, PR/issue metadata, webhooks, reconciliation, signals.

Real FastAPI app + PostgreSQL as relay_app; GitHub HTTP is simulated by tests/fakes.py.
"""

import hashlib
import hmac
import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

import psycopg
import pytest

from relay.integrations.github import webhooks
from relay.jobs import outbox
from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import INSPECTOR_URL, OWNER_URL, libpq_url
from tests.fakes import FakeExternal, FakeRepo, pull
from tests.security.test_members_and_github import connect

pytestmark = pytest.mark.anyio
SECRET = "whsec_test"


@pytest.fixture
def ext() -> FakeExternal:
    prs = [pull(n, "bea", merged="2026-11-01T10:00:00Z") for n in (1, 2, 3)]
    prs.append(pull(4, "eve", reviewers=("bea",)))
    return FakeExternal(
        repos=[
            FakeRepo(
                id=1,
                full_name="acme/payments",
                files={"CODEOWNERS": "* @dee\n"},
                collaborators=[("dee", "admin")],
                pulls=prs,
                pushed_at="2026-11-01T10:00:00Z",
            ),
            FakeRepo(id=2, full_name="acme/legacy", pushed_at="2024-01-01T00:00:00Z"),
        ],
        teams={"platform": ["bea", "dee"]},
        profiles={"bea": {"name": "Bea Ray", "email": "Bea@Acme.test"}},
    )


@pytest.fixture
async def api(ext: FakeExternal) -> AsyncIterator[Api]:
    async with make_api(ext, **ext.github_settings, github_webhook_secret=SECRET) as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


async def run_events(api: Api, workspace: uuid.UUID, *types: str) -> int:
    """Process pending outbox events exactly as the worker would."""
    ctx = outbox.JobContext(
        http=api.app.state.http, settings=api.app.state.settings, jobs=api.app.state.jobs
    )
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        events = conn.execute(
            "SELECT id FROM platform.outbox_event WHERE tenant_id = %s AND processed_at IS NULL "
            "AND event_type = ANY(%s) ORDER BY id",
            (workspace, list(types)),
        ).fetchall()
    for (event_id,) in events:
        await outbox.process(api.app.state.session_factory, workspace, event_id, ctx)
    return len(events)


async def synced(api: Api, ws: Ws, ext: FakeExternal) -> None:
    assert (await connect(api, ws, ext))["status"] == 200
    await run_events(api, ws.id, "github.sync_requested")


def signed(payload: dict[str, Any], secret: str = SECRET) -> tuple[bytes, str]:
    body = json.dumps(payload).encode()
    return body, "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def deliver(
    api: Api, event: str, payload: dict[str, Any], delivery: str, secret: str = SECRET
) -> Any:
    body, signature = signed(payload, secret)
    return await api.client.post(
        "/integrations/github/webhook",
        content=body,
        headers={
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery,
            "X-Hub-Signature-256": signature,
            "Content-Type": "application/json",
        },
    )


def scalar(sql: str, *params: object) -> Any:
    with psycopg.connect(libpq_url(INSPECTOR_URL)) as conn:
        row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


# ---------------------------------------------------------------- sync


async def test_sync_ingests_teams_identities_and_metadata_but_never_bodies(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    dee = await ws.call("POST", "/people", 201, json={"display_name": "Dee", "github_login": "dee"})
    await ws.call(
        "POST", "/people", 201, json={"display_name": "Bea Ray", "email": "bea@acme.test"}
    )
    await synced(api, ws, ext)

    identities = {i["login"]: i for i in await ws.call("GET", "/integrations/github/identities")}
    assert identities["dee"]["link_status"] == "linked"  # login recorded on the person
    assert identities["dee"]["person"]["id"] == dee["id"]
    assert identities["bea"]["link_status"] == "suggested"  # public email: needs review
    assert identities["bea"]["person"] is None
    assert identities["bea"]["recent_items"] == 3
    assert identities["eve"]["link_status"] == "unmatched"
    assert identities["bea"]["teams"] == ["acme/platform"]

    [team] = await ws.call("GET", "/integrations/github/teams")
    assert (team["slug"], sorted(m["login"] for m in team["members"])) == (
        "platform",
        ["bea", "dee"],
    )

    assert (
        scalar("SELECT count(*) FROM integrations.github_work_item WHERE tenant_id = %s", ws.id)
        == 4
    )
    assert scalar(
        "SELECT reviewer_logins FROM integrations.github_work_item "
        "WHERE number = 4 AND tenant_id = %s",
        ws.id,
    ) == ["bea"]
    for table in ("integrations.github_work_item", "platform.outbox_event", "audit.audit_event"):
        assert not scalar(f"SELECT count(*) FROM {table} t WHERE t::text LIKE '%%SECRET BODY%%'")  # noqa: S608

    # Query filters reach GitHub (httpx would otherwise drop them in favour of paging).
    assert any("state=all" in c and "/pulls" in c for c in ext.calls)
    assert any("affiliation=direct" in c for c in ext.calls)

    suggestions = await ws.call("GET", "/integrations/github/suggestions")
    bea = next(s for s in suggestions if s["handle"] == "@bea")
    assert bea["evidence"][0]["source"] == "activity"
    assert bea["evidence"][0]["url"].startswith("https://github.com/acme/payments/pull/")


async def test_missing_permissions_degrade_with_actionable_notes(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    ext.activity_forbidden = ext.members_forbidden = True
    await synced(api, ws, ext)
    [installation] = (await ws.call("GET", "/integrations/github"))["installations"]
    assert installation["last_sync_status"] == "partial"
    assert "Pull requests: Read-only" in installation["last_sync_error"]
    assert "Members: Read-only" in installation["last_sync_error"]
    assert len((await ws.call("GET", "/integrations/github"))["repositories"]) == 2


# ---------------------------------------------------------------- identity review


async def test_identity_review_is_explicit_and_never_merges_people(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    bea_person = await ws.call(
        "POST", "/people", 201, json={"display_name": "Bea Ray", "email": "bea@acme.test"}
    )
    other = await ws.call(
        "POST", "/people", 201, json={"display_name": "Other", "github_login": "someone"}
    )
    await synced(api, ws, ext)
    ids = {i["login"]: i["id"] for i in await ws.call("GET", "/integrations/github/identities")}
    path = "/integrations/github/identities/{}/decision"

    linked = await ws.call(
        "POST", path.format(ids["bea"]), json={"action": "link", "person_id": bea_person["id"]}
    )
    assert linked["person"]["name"] == "Bea Ray"
    people = {p["display_name"]: p for p in await ws.call("GET", "/people")}
    assert people["Bea Ray"]["github_login"] == "bea"

    # One identity per person; a person already tied to another login is refused.
    await ws.call(
        "POST", path.format(ids["eve"]), 409, json={"action": "link", "person_id": bea_person["id"]}
    )
    await ws.call(
        "POST", path.format(ids["eve"]), 409, json={"action": "link", "person_id": other["id"]}
    )

    created = await ws.call("POST", path.format(ids["eve"]), json={"action": "create_person"})
    assert created["link_status"] == "linked"
    unlinked = await ws.call("POST", path.format(ids["bea"]), json={"action": "unlink"})
    assert unlinked["link_status"] == "unmatched"
    people = {p["display_name"]: p for p in await ws.call("GET", "/people")}
    assert people["Bea Ray"]["github_login"] is None
    await run_events(api, ws.id, "github.sync_requested")
    await ws.call("POST", "/integrations/github/installations/x/sync", 422)  # invalid ref
    assert {
        a["action"]
        for a in await ws.call("GET", "/audit-events", params={"category": "integration"})
    } >= {
        "integration.github_identity_linked",
        "integration.github_identity_unlinked",
    }


async def test_team_link_imports_linked_people_only(api: Api, ws: Ws, ext: FakeExternal) -> None:
    await ws.call("POST", "/people", 201, json={"display_name": "Dee", "github_login": "dee"})
    await synced(api, ws, ext)
    [team] = await ws.call("GET", "/integrations/github/teams")
    linked = await ws.call(
        "POST", f"/integrations/github/teams/{team['id']}/link", json={"action": "create"}
    )
    assert linked["linked_team"]["name"] == "Platform"
    [relay_team] = await ws.call("GET", "/teams")
    assert relay_team["github_slug"] == "acme/platform"
    assert [m["display_name"] for m in relay_team["members"]] == ["Dee"]  # bea isn't linked


# ---------------------------------------------------------------- webhooks


async def test_webhooks_are_authenticated_deduplicated_and_order_safe(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await synced(api, ws, ext)
    base = {"installation": {"id": 77}, "repository": {"id": 1, "default_branch": "main"}}
    newer = {
        **base,
        "action": "edited",
        "pull_request": pull(4, "eve", updated="2026-11-05T00:00:00Z", state="closed"),
    }
    older = {
        **base,
        "action": "edited",
        "pull_request": pull(4, "eve", updated="2026-11-02T00:00:00Z"),
    }

    bad = await deliver(api, "pull_request", newer, "d-1", secret="wrong")
    assert bad.status_code == 401
    first = await deliver(api, "pull_request", newer, "d-1")
    again = await deliver(api, "pull_request", newer, "d-1")
    assert (first.json(), again.json()) == ({"queued": 1}, {"queued": 0})  # redelivery ignored
    assert (await deliver(api, "pull_request", older, "d-2")).json() == {"queued": 1}
    assert await run_events(api, ws.id, "github.webhook") == 2  # applied out of order
    state = scalar(
        "SELECT state FROM integrations.github_work_item WHERE number = 4 AND tenant_id = %s", ws.id
    )
    assert state == "closed"  # the older snapshot did not overwrite the newer one
    assert not scalar(
        "SELECT count(*) FROM platform.outbox_event WHERE payload::text LIKE '%%SECRET BODY%%'"
    )

    unknown = await deliver(api, "pull_request", {**newer, "installation": {"id": 999}}, "d-3")
    assert unknown.json() == {"queued": 0}
    assert (await deliver(api, "ping", {"zen": "hi"}, "d-4")).json() == {"queued": 0}

    # A push that touches CODEOWNERS queues one re-sync; ordinary pushes are ignored.
    push = {**base, "ref": "refs/heads/main", "commits": [{"modified": ["CODEOWNERS"]}]}
    assert (await deliver(api, "push", push, "d-5")).json() == {"queued": 1}
    plain = {**base, "ref": "refs/heads/main", "commits": [{"modified": ["src/app.py"]}]}
    assert (await deliver(api, "push", plain, "d-6")).json() == {"queued": 0}
    await run_events(api, ws.id, "github.webhook")
    assert await run_events(api, ws.id, "github.sync_requested") == 1

    # Uninstalling on GitHub marks the installation revoked (nothing is deleted).
    await deliver(api, "installation", {"action": "deleted", "installation": {"id": 77}}, "d-7")
    await run_events(api, ws.id, "github.webhook")
    [installation] = (await ws.call("GET", "/integrations/github"))["installations"]
    assert installation["status"] == "revoked"
    assert "uninstalled" in installation["last_sync_error"]


async def test_webhooks_need_a_configured_secret(ext: FakeExternal) -> None:
    async with make_api(ext, **ext.github_settings) as unsecured:
        response = await deliver(unsecured, "ping", {"installation": {"id": 77}}, "d-1")
    assert response.status_code == 503


async def test_reconciliation_requeues_stale_and_stuck_installations(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await synced(api, ws, ext)
    factory, jobs = api.app.state.session_factory, api.app.state.jobs
    assert await webhooks.reconcile(factory, jobs) == 0  # just synced
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(ws.id),))
        conn.execute(
            "UPDATE integrations.github_installation "
            "SET last_synced_at = now() - interval '1 day', last_sync_status = 'queued'"
        )
    assert await webhooks.reconcile(factory, jobs) == 1  # stuck 'queued' is recovered
    assert await webhooks.reconcile(factory, jobs) == 0  # and not queued twice
    assert await run_events(api, ws.id, "github.sync_requested") >= 1
    [installation] = (await ws.call("GET", "/integrations/github"))["installations"]
    assert installation["last_sync_status"] in ("ok", "partial")


# ---------------------------------------------------------------- signals and bulk review


async def test_signals_are_evidence_backed_and_change_nothing(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    dee = await ws.call("POST", "/people", 201, json={"display_name": "Dee", "github_login": "dee"})
    await synced(api, ws, ext)
    repos = {
        r["full_name"]: r for r in (await ws.call("GET", "/integrations/github"))["repositories"]
    }
    kinds = {s["kind"] for s in await ws.call("GET", "/integrations/github/signals")}
    assert {"unowned_active", "unmaintained"} <= kinds

    # Approve Dee as primary through the normal flow, then the activity tells a story.
    suggestion = next(
        s for s in await ws.call("GET", "/integrations/github/suggestions") if s["handle"] == "@dee"
    )
    await ws.call(
        "POST",
        f"/integrations/github/suggestions/{suggestion['id']}/decision",
        json={"action": "approve"},
    )
    signals = await ws.call("GET", "/integrations/github/signals")
    inactive = next(s for s in signals if s["kind"] == "owner_inactive")
    assert "Dee" in inactive["explanation"]
    assert inactive["evidence"][0]["url"].startswith("https://github.com/acme/payments/pull/")
    assert any(s["kind"] == "active_non_owner" and "@bea" in s["explanation"] for s in signals)

    assert repos["acme/payments"]["responsibility_id"] is None  # created by the approval
    refreshed = (await ws.call("GET", "/integrations/github"))["repositories"]
    rid = next(r for r in refreshed if r["full_name"] == "acme/payments")["responsibility_id"]
    detail = await ws.call("GET", f"/responsibilities/{rid}")
    assert [o["assignee"]["id"] for o in detail["owners_as_of"]] == [
        dee["id"]
    ]  # unchanged by signals


async def test_bulk_review_decides_each_independently(api: Api, ws: Ws, ext: FakeExternal) -> None:
    await ws.call("POST", "/people", 201, json={"display_name": "Dee", "github_login": "dee"})
    await synced(api, ws, ext)
    suggestions = {
        s["handle"]: s["id"] for s in await ws.call("GET", "/integrations/github/suggestions")
    }
    results = await ws.call(
        "POST",
        "/integrations/github/suggestions/bulk",
        json={"ids": [suggestions["@dee"], suggestions["@bea"]], "action": "approve"},
    )
    by_id = {r["id"]: r for r in results}
    assert by_id[suggestions["@dee"]]["ok"] is True
    assert by_id[suggestions["@bea"]]["ok"] is False  # no linked person: needs an explicit owner
    assert "choose the person or team" in by_id[suggestions["@bea"]]["error"].lower()
    deferred = await ws.call(
        "POST",
        "/integrations/github/suggestions/bulk",
        json={"ids": [suggestions["@bea"]], "action": "defer"},
    )
    assert deferred[0]["status"] == "deferred"


# ---------------------------------------------------------------- visibility and isolation


async def test_evidence_is_for_admins_and_isolated_per_workspace(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await synced(api, ws, ext)
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    for path in ("/identities", "/teams", "/signals", "/suggestions"):
        await member.call("GET", f"/integrations/github{path}", 403)
    await member.call(
        "POST",
        "/integrations/github/suggestions/bulk",
        403,
        json={"ids": [str(uuid.uuid4())], "action": "defer"},
    )

    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    assert await other.call("GET", "/integrations/github/identities") == []
    assert await other.call("GET", "/integrations/github/teams") == []
    assert await other.call("GET", "/integrations/github/signals") == []
    identity = (await ws.call("GET", "/integrations/github/identities"))[0]["id"]
    await other.call(
        "POST",
        f"/integrations/github/identities/{identity}/decision",
        404,
        json={"action": "dismiss"},
    )
    # A webhook for this installation reaches only the workspace that connected it.
    payload = {
        "installation": {"id": 77},
        "repository": {"id": 1},
        "action": "opened",
        "pull_request": pull(9, "bea"),
    }
    assert (await deliver(api, "pull_request", payload, "iso-1")).json() == {"queued": 1}
    assert (
        scalar("SELECT count(*) FROM integrations.webhook_delivery WHERE tenant_id = %s", other.id)
        == 0
    )


async def test_private_repository_evidence_is_managers_only_until_an_admin_widens_it(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    """Relay can't read each member's GitHub access, so private repos never default open."""
    await ws.call("POST", "/people", 201, json={"display_name": "Dee", "github_login": "dee"})
    await synced(api, ws, ext)
    suggestion = next(
        s for s in await ws.call("GET", "/integrations/github/suggestions") if s["handle"] == "@dee"
    )
    await ws.call(
        "POST",
        f"/integrations/github/suggestions/{suggestion['id']}/decision",
        json={"action": "approve"},
    )
    repo = next(
        r
        for r in (await ws.call("GET", "/integrations/github"))["repositories"]
        if r["full_name"] == "acme/payments"
    )
    assert repo["audience"] == "managers"
    rid = repo["responsibility_id"]
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")

    async def sees(who: Ws) -> tuple[bool, bool]:
        context = await who.call("GET", f"/responsibilities/{rid}/context")
        hits = (await who.call("GET", "/search", params={"q": "Change"}))["hits"]
        return (
            any(e["source"] == "GitHub" for e in context["evidence"]),
            any(h["kind"] == "github" for h in hits),
        )

    assert await sees(ws) == (True, True)
    assert await sees(member) == (False, False)
    await member.call(
        "PATCH",
        f"/integrations/github/repositories/{repo['id']}",
        403,
        json={"audience": "workspace"},
    )

    # An admin's explicit, audited decision widens it; GitHub turning it private again narrows it.
    await ws.call(
        "PATCH", f"/integrations/github/repositories/{repo['id']}", json={"audience": "workspace"}
    )
    assert await sees(member) == (True, True)
    assert (
        scalar(
            "SELECT count(*) FROM audit.audit_event WHERE tenant_id = %s AND "
            "action = 'integration.github_repository_updated' "
            "AND metadata->>'audience' = 'workspace'",
            ws.id,
        )
        == 1
    )
    ext.repos[0].private = False
    await ws.call("POST", f"/integrations/github/installations/{repo['installation_ref']}/sync")
    await run_events(api, ws.id, "github.sync_requested")
    ext.repos[0].private = True
    await ws.call("POST", f"/integrations/github/installations/{repo['installation_ref']}/sync")
    await run_events(api, ws.id, "github.sync_requested")
    assert await sees(member) == (False, False)
