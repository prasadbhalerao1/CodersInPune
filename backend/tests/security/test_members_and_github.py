"""Member management, email-bound invitations and the GitHub ownership integration.

Real FastAPI app + PostgreSQL as relay_app. WorkOS and GitHub HTTP are simulated by
tests/fakes.py; GitHub's app JWT and the install-ownership check run for real.
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlparse

import psycopg
import pytest

from relay.integrations.github.parsing import parse_catalog_info, parse_codeowners
from relay.jobs import outbox
from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import INSPECTOR_URL, count_rows
from tests.fakes import FakeExternal, FakeRepo

pytestmark = pytest.mark.anyio

INVITEE = "user_invitee"


@pytest.fixture
def ext() -> FakeExternal:
    return FakeExternal(
        workos_users={
            INVITEE: {
                "id": INVITEE,
                "email": "Asha@Example.com",
                "email_verified": True,
                "first_name": "Asha",
            },
            "user_other": {
                "id": "user_other",
                "email": "other@example.com",
                "email_verified": True,
            },
            "user_unverified": {
                "id": "user_unverified",
                "email": "asha@example.com",
                "email_verified": False,
            },
        },
        repos=[
            FakeRepo(
                id=1,
                full_name="acme/payments",
                files={
                    ".github/CODEOWNERS": "# owners\n*  @acme/platform @bea\n/docs/ @cy\n",
                    "catalog-info.yaml": (
                        "kind: Component\nmetadata:\n  name: payments\n"
                        "spec:\n  owner: group:platform\n"
                    ),
                },
                collaborators=[("Dee", "maintain"), ("eve", "write")],
            ),
            FakeRepo(id=2, full_name="acme/website", files={"CODEOWNERS": "* @bea\n"}),
        ],
    )


@pytest.fixture
async def api(ext: FakeExternal) -> AsyncIterator[Api]:
    async with make_api(ext, **ext.github_settings) as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


async def me(api: Api, sub: str, method: str, path: str, expected: int) -> Any:
    response = await api.client.request(method, f"/me{path}", headers=api.as_user(sub))
    assert response.status_code == expected, response.text
    return response.json() if response.content else None


# Invitations and members


async def test_invitation_is_bound_to_the_verified_email(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    invite = await ws.call(
        "POST", "/invitations", 201, json={"email": "asha@example.com", "role": "member"}
    )
    assert invite["email_sent"] is True
    assert ext.sent_invitations == ["asha@example.com"]

    assert await me(api, "user_other", "GET", "/invitations", 200) == []
    await me(api, "user_other", "POST", f"/invitations/{invite['id']}/accept", 404)
    unverified = await me(
        api, "user_unverified", "POST", f"/invitations/{invite['id']}/accept", 403
    )
    assert unverified["code"] == "email_unverified"

    mine = await me(api, INVITEE, "GET", "/invitations", 200)
    assert [(i["workspace_name"], i["role"]) for i in mine] == [("Acme", "member")]
    joined = await me(api, INVITEE, "POST", f"/invitations/{invite['id']}/accept", 200)
    assert joined["workspace_id"] == str(ws.id)

    invitee = Ws(api, ws.id, INVITEE)
    assert (await invitee.call("GET", ""))["role"] == "member"
    members = {m["name"]: m["role"] for m in await ws.call("GET", "/members")}
    assert members["Asha"] == "member"
    await me(api, INVITEE, "POST", f"/invitations/{invite['id']}/accept", 404)  # single use


async def test_revoked_invitations_cannot_be_accepted(api: Api, ws: Ws) -> None:
    invite = await ws.call("POST", "/invitations", 201, json={"email": "asha@example.com"})
    await ws.call("POST", f"/invitations/{invite['id']}/revoke")
    assert await me(api, INVITEE, "GET", "/invitations", 200) == []
    await me(api, INVITEE, "POST", f"/invitations/{invite['id']}/accept", 404)
    assert count_rows("identity.membership", "tenant_id = %s", (ws.id,)) == 1


async def test_invitation_rules(api: Api, ws: Ws) -> None:
    await ws.call("POST", "/invitations", 201, json={"email": "asha@example.com"})
    dup = await ws.call("POST", "/invitations", 409, json={"email": "ASHA@example.com"})
    assert dup["code"] == "invitation_exists"
    await add_member(api, ws.id, "user_admin", "admin")
    admin = Ws(api, ws.id, "user_admin")
    owner_invite = await admin.call(
        "POST", "/invitations", 403, json={"email": "x@example.com", "role": "owner"}
    )
    assert owner_invite["code"] == "owner_required"
    await add_member(api, ws.id, "user_member", "member")
    await Ws(api, ws.id, "user_member").call(
        "POST", "/invitations", 403, json={"email": "y@example.com"}
    )


async def test_member_management_guards(api: Api, ws: Ws) -> None:
    await add_member(api, ws.id, "user_member", "member")
    members = {m["role"]: m["user_id"] for m in await ws.call("GET", "/members")}
    owner_id, member_id = members["owner"], members["member"]

    self_change = await ws.call("PATCH", f"/members/{owner_id}", 409, json={"role": "admin"})
    assert self_change["code"] == "cannot_change_self"
    await ws.call("PATCH", f"/members/{member_id}", json={"role": "admin"})
    admin = Ws(api, ws.id, "user_member")
    blocked = await admin.call("PATCH", f"/members/{owner_id}", 403, json={"status": "suspended"})
    assert blocked["code"] == "owner_required"

    await ws.call("PATCH", f"/members/{member_id}", json={"status": "suspended"})
    response = await api.client.get(f"/workspaces/{ws.id}", headers=api.as_user("user_member"))
    assert response.json()["code"] == "membership_inactive"
    assert count_rows("audit.audit_event", "action = 'membership.updated'") == 2


async def test_only_owners_can_change_owners(api: Api, ws: Ws) -> None:
    await add_member(api, ws.id, "user_two", "owner")
    for sub in (OWNER, "user_two"):
        response = await api.client.put(
            "/me/profile", json={"display_name": sub}, headers=api.as_user(sub)
        )
        assert response.status_code == 204
    ids = {m["name"]: m["user_id"] for m in await ws.call("GET", "/members")}
    two = Ws(api, ws.id, "user_two")
    await two.call("PATCH", f"/members/{ids[OWNER]}", json={"role": "admin"})
    # The demoted admin can no longer change the remaining owner.
    denied = await ws.call("PATCH", f"/members/{ids['user_two']}", 403, json={"role": "member"})
    assert denied["code"] == "owner_required"


# GitHub connect


async def connect(
    api: Api, ws: Ws, ext: FakeExternal, *, installation_id: int = 77
) -> dict[str, Any]:
    started = await ws.call("POST", "/integrations/github/connect")
    url = urlparse(started["install_url"])
    assert url.path == "/apps/relay-test/installations/new"
    state = parse_qs(url.query)["state"][0]
    ext.oauth_codes["code-ok"] = [77]
    response = await api.client.post(
        "/integrations/github/complete",
        json={"state": state, "code": "code-ok", "installation_id": installation_id},
        headers=api.as_user(ws.sub),
    )
    return {"state": state, "status": response.status_code, "body": response.json()}


async def run_sync(api: Api, workspace: uuid.UUID) -> None:
    """Process pending sync events exactly as the worker would (same handler and context)."""
    ctx = outbox.JobContext(http=api.app.state.http, settings=api.app.state.settings)
    with psycopg.connect(INSPECTOR_URL) as conn:
        events = conn.execute(
            "SELECT id FROM platform.outbox_event WHERE tenant_id = %s "
            "AND event_type = 'github.sync_requested' AND processed_at IS NULL",
            (workspace,),
        ).fetchall()
    for (event_id,) in events:
        await outbox.process(api.app.state.session_factory, workspace, event_id, ctx)


async def test_connect_verifies_installation_ownership(api: Api, ws: Ws, ext: FakeExternal) -> None:
    spoofed = await connect(api, ws, ext, installation_id=999)
    assert spoofed["status"] == 403
    assert spoofed["body"]["code"] == "installation_not_verified"
    assert count_rows("integrations.github_installation") == 0

    ok = await connect(api, ws, ext)
    assert ok["status"] == 200
    assert ok["body"]["workspace_id"] == str(ws.id)
    reused = await api.client.post(
        "/integrations/github/complete",
        json={"state": ok["state"], "code": "code-ok", "installation_id": 77},
        headers=api.as_user(OWNER),
    )
    assert reused.json()["code"] == "invalid_state"
    overview = await ws.call("GET", "/integrations/github")
    assert [(i["account_login"], i["last_sync_status"]) for i in overview["installations"]] == [
        ("acme", "queued")
    ]


async def test_connect_state_is_bound_to_the_workspace_and_user(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    started = await ws.call("POST", "/integrations/github/connect")
    state = parse_qs(urlparse(started["install_url"]).query)["state"][0]
    ext.oauth_codes["code-ok"] = [77]
    await api.create_workspace("user_intruder", "Theirs")
    stolen = await api.client.post(
        "/integrations/github/complete",
        json={"state": state, "code": "code-ok", "installation_id": 77},
        headers=api.as_user("user_intruder"),
    )
    assert stolen.status_code == 404  # not a member of the state's workspace
    await add_member(api, ws.id, "user_admin", "admin")
    other_user = await api.client.post(
        "/integrations/github/complete",
        json={"state": state, "code": "code-ok", "installation_id": 77},
        headers=api.as_user("user_admin"),
    )
    assert other_user.json()["code"] == "invalid_state"


# Sync and suggestions


async def test_sync_builds_evidence_based_suggestions(api: Api, ws: Ws, ext: FakeExternal) -> None:
    await connect(api, ws, ext)
    await run_sync(api, ws.id)
    overview = await ws.call("GET", "/integrations/github")
    assert overview["installations"][0]["last_sync_status"] == "ok"
    assert sorted(r["full_name"] for r in overview["repositories"]) == [
        "acme/payments",
        "acme/website",
    ]

    suggestions = await ws.call("GET", "/integrations/github/suggestions")
    payments = {s["handle"]: s for s in suggestions if s["repository"] == "acme/payments"}
    assert payments["group:platform"]["proposed_role"] == "primary"  # catalog owner wins
    assert payments["@acme/platform"]["proposed_role"] == "co_owner"
    assert payments["@cy"]["proposed_role"] == "backup"  # path-scoped CODEOWNERS
    assert payments["@dee"]["proposed_role"] == "backup"  # maintain collaborator
    assert "@eve" not in payments  # write access is not ownership
    assert payments["@bea"]["evidence"][0]["detail"].startswith(".github/CODEOWNERS:2")


async def test_approval_uses_ownership_history_and_never_replaces_a_primary(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    team = (
        await ws.call(
            "POST", "/teams", 201, json={"name": "Platform", "github_slug": "acme/platform"}
        )
    )["id"]
    bea = await ws.call("POST", "/people", 201, json={"display_name": "Bea", "github_login": "bea"})
    await connect(api, ws, ext)
    await run_sync(api, ws.id)
    suggestions = await ws.call("GET", "/integrations/github/suggestions")
    by = {(s["repository"], s["handle"]): s for s in suggestions}

    primary = by[("acme/payments", "group:platform")]
    assert primary["match"] == {"type": "team", "id": team, "name": "Platform"}
    decision = await ws.call(
        "POST",
        f"/integrations/github/suggestions/{primary['id']}/decision",
        json={"action": "approve"},
    )
    assert decision["status"] == "approved"
    rid = next(
        r["responsibility_id"]
        for r in (await ws.call("GET", "/integrations/github"))["repositories"]
        if r["full_name"] == "acme/payments"
    )
    owners = (await ws.call("GET", f"/responsibilities/{rid}"))["owners_as_of"]
    assert [(o["role"], o["assignee"]["name"]) for o in owners] == [("primary", "Platform")]

    # A second "primary" proposal for the same repository must not overwrite the first.
    bea_suggestion = by[("acme/payments", "@bea")]
    conflict = await ws.call(
        "POST",
        f"/integrations/github/suggestions/{bea_suggestion['id']}/decision",
        409,
        json={"action": "approve", "role": "primary"},
    )
    assert conflict["code"] == "primary_owner_conflict"
    await ws.call(
        "POST",
        f"/integrations/github/suggestions/{bea_suggestion['id']}/decision",
        json={"action": "approve", "role": "backup", "person_id": bea["id"]},
    )
    history = await ws.call("GET", f"/responsibilities/{rid}/history")
    assert {h["assignee"]["name"] for h in history} == {"Platform", "Bea"}
    assert count_rows("audit.audit_event", "action = 'suggestion.approved'") == 2

    unmatched = by[("acme/payments", "@cy")]
    needs = await ws.call(
        "POST",
        f"/integrations/github/suggestions/{unmatched['id']}/decision",
        422,
        json={"action": "approve"},
    )
    assert needs["code"] == "assignee_required"


async def test_dismissed_suggestions_stay_dismissed_until_evidence_changes(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await connect(api, ws, ext)
    await run_sync(api, ws.id)
    website = next(
        s
        for s in await ws.call("GET", "/integrations/github/suggestions")
        if s["repository"] == "acme/website"
    )
    await ws.call(
        "POST",
        f"/integrations/github/suggestions/{website['id']}/decision",
        json={"action": "dismiss"},
    )
    overview = await ws.call("GET", "/integrations/github")
    await ws.call(
        "POST", f"/integrations/github/installations/{overview['installations'][0]['id']}/sync"
    )
    await run_sync(api, ws.id)
    assert website["id"] not in {
        s["id"] for s in await ws.call("GET", "/integrations/github/suggestions")
    }

    ext.repos[1].files["CODEOWNERS"] = "* @bea  # still bea, new line\n/src/ @bea\n"
    await ws.call(
        "POST", f"/integrations/github/installations/{overview['installations'][0]['id']}/sync"
    )
    await run_sync(api, ws.id)
    assert website["id"] in {
        s["id"] for s in await ws.call("GET", "/integrations/github/suggestions")
    }


async def test_revoked_installation_is_reported(api: Api, ws: Ws, ext: FakeExternal) -> None:
    await connect(api, ws, ext)
    ext.revoked_installations.add(77)
    await run_sync(api, ws.id)
    installation = (await ws.call("GET", "/integrations/github"))["installations"][0]
    assert installation["status"] == "revoked"
    assert installation["last_sync_status"] == "error"
    assert "Reconnect" in installation["last_sync_error"]


async def test_github_outage_is_retried_not_marked_revoked(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await connect(api, ws, ext)
    ext.github_down = True
    with pytest.raises(Exception, match="502"):
        await run_sync(api, ws.id)
    installation = (await ws.call("GET", "/integrations/github"))["installations"][0]
    assert installation["status"] == "active"


async def test_integrations_are_isolated_and_manager_only(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    await connect(api, ws, ext)
    await run_sync(api, ws.id)
    other = Ws(api, await api.create_workspace("user_other_ws", "Other"), "user_other_ws")
    overview = await other.call("GET", "/integrations/github")
    assert (overview["installations"], overview["repositories"]) == ([], [])
    assert await other.call("GET", "/integrations/github/suggestions") == []
    some = (await ws.call("GET", "/integrations/github/suggestions"))[0]
    await other.call(
        "POST",
        f"/integrations/github/suggestions/{some['id']}/decision",
        404,
        json={"action": "dismiss"},
    )
    await add_member(api, ws.id, "user_member", "member")
    await Ws(api, ws.id, "user_member").call("GET", "/integrations/github", 403)


def test_parsers() -> None:
    owners = parse_codeowners(
        "# c\n*  @Org/Team  @bob  dev@x.io\n/api/ @carol # api\n", "CODEOWNERS"
    )
    assert [(o.handle, o.handle_type, o.repo_wide) for o in owners] == [
        ("@org/team", "team", True),
        ("@bob", "user", True),
        ("@carol", "user", False),
    ]
    catalog = parse_catalog_info(
        "---\nspec:\n  owner: group:default/payments\n---\nkind: API\nspec: {}\n"
    )
    assert [c.handle for c in catalog] == ["group:default/payments"]
    assert parse_catalog_info("not: [valid") == []
