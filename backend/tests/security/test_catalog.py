"""Responsibility catalogue, directory, ownership history and continuity risks.

Real FastAPI app + PostgreSQL as relay_app; tokens are real RS256 JWTs (JWKS simulated).
"""

import uuid
from collections.abc import AsyncIterator
from typing import Any

import psycopg
import pytest
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError

from relay.catalog import service as catalog_service
from relay.catalog.models import OwnershipAssignmentChange
from relay.identity.models import Membership, UserAccount
from relay.shared.db import unit_of_work
from tests.api import Api, make_api
from tests.db import count_rows

pytestmark = pytest.mark.anyio

OWNER = "user_owner"
T0, T1, T2 = "2026-01-01T00:00:00+00:00", "2026-06-01T00:00:00+00:00", "2026-03-01T00:00:00+00:00"


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


class Ws:
    def __init__(self, api: Api, workspace: uuid.UUID, sub: str = OWNER) -> None:
        self.api, self.id, self.sub = api, workspace, sub

    async def call(self, method: str, path: str, expected: int = 200, **kwargs: Any) -> Any:
        response = await self.api.client.request(
            method, f"/workspaces/{self.id}{path}", headers=self.api.as_user(self.sub), **kwargs
        )
        assert response.status_code == expected, response.text
        return response.json() if response.content else None

    async def person(self, name: str) -> str:
        return str((await self.call("POST", "/people", 201, json={"display_name": name}))["id"])

    async def responsibility(self, name: str, criticality: str = "standard") -> str:
        body = {"name": name, "criticality": criticality}
        return str((await self.call("POST", "/responsibilities", 201, json=body))["id"])


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


async def add_member(api: Api, tenant: uuid.UUID, sub: str, role: str) -> None:
    async with unit_of_work(api.app.state.session_factory, tenant, sub) as session:
        user_id = (
            await session.execute(
                insert(UserAccount)
                .values(workos_user_id=sub)
                .on_conflict_do_update(
                    index_elements=["workos_user_id"], set_={"workos_user_id": sub}
                )
                .returning(UserAccount.id)
            )
        ).scalar_one()
        session.add(Membership(tenant_id=tenant, user_id=user_id, role=role, status="active"))


# CRUD, search, archive


async def test_responsibility_lifecycle(ws: Ws) -> None:
    created = await ws.call(
        "POST",
        "/responsibilities",
        201,
        json={"name": "Payments on-call", "category": "Operations", "criticality": "critical"},
    )
    rid = created["id"]
    await ws.responsibility("Quarterly audit", "low")

    found = await ws.call("GET", "/responsibilities", params={"q": "payments"})
    assert [r["name"] for r in found] == ["Payments on-call"]
    critical = await ws.call("GET", "/responsibilities", params={"criticality": "critical"})
    assert len(critical) == 1

    edited = await ws.call(
        "PATCH", f"/responsibilities/{rid}", json={"version": 1, "description": "Pager duty"}
    )
    assert (edited["description"], edited["version"]) == ("Pager duty", 2)
    stale = await ws.api.client.patch(
        f"/workspaces/{ws.id}/responsibilities/{rid}",
        json={"version": 1, "name": "Stale"},
        headers=ws.api.as_user(OWNER),
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "version_conflict"

    archived = await ws.call("POST", f"/responsibilities/{rid}/archive")
    assert archived["status"] == "archived"
    assert len(await ws.call("GET", "/responsibilities")) == 1
    assert len(await ws.call("GET", "/responsibilities", params={"status": "archived"})) == 1
    await ws.call("POST", f"/responsibilities/{rid}/restore")
    actions = "action IN ('responsibility.created', 'responsibility.updated', "
    actions += "'responsibility.archived', 'responsibility.restored')"
    assert count_rows("audit.audit_event", f"tenant_id = %s AND {actions}", (ws.id,)) == 5


async def test_workspace_isolation(api: Api, ws: Ws) -> None:
    rid = await ws.responsibility("Secret thing")
    pid = await ws.person("Asha")
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    assert await other.call("GET", "/responsibilities") == []
    assert await other.call("GET", "/people") == []
    await other.call("GET", f"/responsibilities/{rid}", 404)
    # Cannot attach a person from another workspace.
    their_rid = await other.responsibility("Theirs")
    response = await other.call(
        "POST",
        f"/responsibilities/{their_rid}/assignments",
        422,
        json={"role": "primary", "person_id": pid},
    )
    assert response["code"] == "assignee_not_found"
    # Cannot reach the first workspace's records through its own id either.
    foreign = await api.client.get(
        f"/workspaces/{ws.id}/responsibilities", headers=api.as_user("user_other")
    )
    assert foreign.status_code == 404
    assert count_rows("catalog.responsibility", "tenant_id = %s", (ws.id,)) == 1


async def test_members_can_read_but_not_mutate(api: Api, ws: Ws) -> None:
    rid = await ws.responsibility("Readable")
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    assert len(await member.call("GET", "/responsibilities")) == 1
    await member.call("GET", "/risks")
    for method, path, body in [
        ("POST", "/responsibilities", {"name": "x"}),
        ("PATCH", f"/responsibilities/{rid}", {"version": 1, "name": "y"}),
        ("POST", f"/responsibilities/{rid}/archive", None),
        ("POST", "/people", {"display_name": "z"}),
        ("POST", "/teams", {"name": "t"}),
    ]:
        denied = await member.call(method, path, 403, json=body)
        assert denied["code"] == "forbidden"
    assert count_rows("audit.audit_event", "action = 'authorization.denied'") == 5


# Ownership


async def test_person_and_team_ownership(ws: Ws) -> None:
    rid = await ws.responsibility("Release train")
    asha = await ws.person("Asha")
    team = (await ws.call("POST", "/teams", 201, json={"name": "Platform"}))["id"]
    await ws.call("PUT", f"/teams/{team}/members/{asha}", 204)
    teams = await ws.call("GET", "/teams")
    assert [m["display_name"] for m in teams[0]["members"]] == ["Asha"]

    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "team_id": team},
    )
    detail = await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "backup", "person_id": asha},
    )
    assert [(o["role"], o["assignee"]["type"]) for o in detail["owners_as_of"]] == [
        ("primary", "team"),
        ("backup", "person"),
    ]
    await ws.call("PATCH", f"/people/{asha}", json={"status": "archived"})
    archived = await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        422,
        json={"role": "co_owner", "person_id": asha},
    )
    assert archived["code"] == "assignee_archived"


async def test_only_one_primary_at_a_time(ws: Ws) -> None:
    rid = await ws.responsibility("Billing")
    a, b = await ws.person("A"), await ws.person("B")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "person_id": a},
    )
    conflict = await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        409,
        json={"role": "primary", "person_id": b},
    )
    assert conflict["code"] == "primary_owner_conflict"
    # The same person cannot hold two roles at once (e.g. be their own backup).
    twice = await ws.call(
        "POST", f"/responsibilities/{rid}/assignments", 409, json={"role": "backup", "person_id": a}
    )
    assert twice["code"] == "assignment_overlap"
    # No primary at all is allowed.
    await ws.responsibility("Unowned")


async def test_handover_preserves_history_and_answers_as_of(ws: Ws) -> None:
    rid = await ws.responsibility("Payments")
    old, new = await ws.person("Old Owner"), await ws.person("New Owner")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "person_id": old, "starts_at": T0, "reason": "initial"},
    )
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "backup", "person_id": new, "starts_at": T0},
    )
    replaced = await ws.call(
        "POST",
        f"/responsibilities/{rid}/primary",
        json={"person_id": new, "effective_at": T1, "reason": "Old Owner moved teams"},
    )
    names = [(o["role"], o["assignee"]["name"]) for o in replaced["owners_as_of"]]
    assert names == [("primary", "New Owner")]

    before = await ws.call("GET", f"/responsibilities/{rid}", params={"as_of": T2})
    assert [(o["role"], o["assignee"]["name"]) for o in before["owners_as_of"]] == [
        ("primary", "Old Owner"),
        ("backup", "New Owner"),
    ]
    old_assignment = next(
        a for a in replaced["assignments"] if a["assignee"]["name"] == "Old Owner"
    )
    assert old_assignment["valid_to"].startswith("2026-06-01T00:00:00")
    assert old_assignment["state"] == "ended"

    history = await ws.call("GET", f"/responsibilities/{rid}/history")
    assert sorted(h["change_type"] for h in history) == [
        "assigned",
        "assigned",
        "assigned",
        "ended",
        "ended",
    ]
    assert any(h["reason"] == "Old Owner moved teams" for h in history)


async def test_end_assignment_rules(ws: Ws) -> None:
    rid = await ws.responsibility("Docs")
    p = await ws.person("P")
    detail = await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "co_owner", "person_id": p, "starts_at": T0},
    )
    aid = detail["assignments"][0]["id"]
    bad = await ws.call(
        "POST", f"/responsibilities/{rid}/assignments/{aid}/end", 422, json={"ends_at": T0}
    )
    assert bad["code"] == "invalid_end"
    ended = await ws.call("POST", f"/responsibilities/{rid}/assignments/{aid}/end", json={})
    assert ended["owners_as_of"] == []
    again = await ws.call("POST", f"/responsibilities/{rid}/assignments/{aid}/end", 409, json={})
    assert again["code"] == "already_ended"


async def test_ownership_change_is_atomic(
    api: Api, ws: Ws, monkeypatch: pytest.MonkeyPatch
) -> None:
    rid = await ws.responsibility("Atomic")
    old, new = await ws.person("Old"), await ws.person("New")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "person_id": old},
    )
    changes_before = count_rows("catalog.ownership_assignment_change")
    audits_before = count_rows("audit.audit_event")

    async def boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("crash mid-handover")

    monkeypatch.setattr(catalog_service, "_insert_assignment", boom)
    with pytest.raises(RuntimeError):
        await api.client.post(
            f"/workspaces/{ws.id}/responsibilities/{rid}/primary",
            json={"person_id": new},
            headers=api.as_user(OWNER),
        )
    assert count_rows("catalog.ownership_assignment", "valid_to IS NULL AND role = 'primary'") == 1
    assert count_rows("catalog.ownership_assignment_change") == changes_before
    assert count_rows("audit.audit_event") == audits_before


async def test_change_history_is_append_only(api: Api, ws: Ws) -> None:
    rid = await ws.responsibility("Immutable")
    p = await ws.person("P")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "person_id": p},
    )
    with pytest.raises(DBAPIError) as excinfo:
        async with unit_of_work(api.app.state.session_factory, ws.id) as session:
            await session.execute(update(OwnershipAssignmentChange).values(reason="rewritten"))
    assert isinstance(excinfo.value.orig, psycopg.errors.InsufficientPrivilege)


# Risks and overview


async def test_risks_reflect_catalogue_and_resolve(ws: Ws) -> None:
    rid = await ws.responsibility("Core database", "critical")
    rules = {(r["rule"], r["severity"]) for r in await ws.call("GET", "/risks")}
    assert rules == {("no_primary_owner", "high"), ("no_backup", "high")}

    a, b = await ws.person("Asha"), await ws.person("Bo")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "person_id": a},
    )
    remaining = {r["rule"] for r in await ws.call("GET", "/risks")}
    assert remaining == {"no_backup", "insufficient_critical_coverage"}

    await ws.call(
        "POST", f"/responsibilities/{rid}/assignments", 201, json={"role": "backup", "person_id": b}
    )
    assert await ws.call("GET", "/risks") == []


async def test_single_person_dependency_and_overview(ws: Ws) -> None:
    solo = await ws.person("Solo")
    for name in ("Deploys", "Billing"):
        rid = await ws.responsibility(name, "high")
        await ws.call(
            "POST",
            f"/responsibilities/{rid}/assignments",
            201,
            json={"role": "primary", "person_id": solo},
        )
    await ws.responsibility("Nobody's job", "critical")

    risks = await ws.call("GET", "/risks")
    dependency = next(r for r in risks if r["rule"] == "single_person_dependency")
    assert dependency["severity"] == "high"
    assert sorted(r["name"] for r in dependency["related"]) == ["Billing", "Deploys"]

    overview = await ws.call("GET", "/overview")
    assert overview["active_responsibilities"] == 3
    assert overview["without_primary_owner"] == 1
    assert overview["critical_without_backup"] == 1
    assert overview["open_risks"] == len(risks)
    assert len(overview["recent_changes"]) == 2
