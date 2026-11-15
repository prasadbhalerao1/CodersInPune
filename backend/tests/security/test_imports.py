"""CSV import: preview is read-only, commit is transactional, existing data is never
overwritten and existing owners are never replaced."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from tests.api import OWNER, Api, Ws, add_member, make_api

pytestmark = pytest.mark.anyio

PEOPLE = """Name,Email,Title,Department,Shoe size
Ada Lovelace,ada@acme.test,Staff engineer,Engineering,
Grace Hopper,grace@acme.test,,Engineering,
Bad Email,not-an-email,,,
Ada Again,ADA@acme.test,,,
"""
RESPONSIBILITIES = """name,criticality,category
Payments on-call,critical,Operations
Quarterly audit,low,
Mystery,catastrophic,
"""


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


async def _import(ws: Ws, kind: str, text: str, step: str = "commit") -> Any:
    return await ws.call("POST", f"/imports/{step}", json={"kind": kind, "csv": text})


def _actions(result: Any) -> list[tuple[int, str]]:
    return [(r["line"], r["action"]) for r in result["rows"]]


async def test_people_preview_writes_nothing_and_commit_creates_valid_rows(ws: Ws) -> None:
    preview = await _import(ws, "people", PEOPLE, "preview")
    assert preview["committed"] is False
    assert preview["ignored_columns"] == ["shoe size"]
    assert _actions(preview) == [(2, "create"), (3, "create"), (4, "error"), (5, "error")]
    assert "department" in (preview["rows"][0]["message"] or "").lower()
    assert await ws.call("GET", "/people") == []

    committed = await _import(ws, "people", PEOPLE)
    assert (committed["created"], committed["errors"]) == (2, 2)
    people = {p["display_name"]: p for p in await ws.call("GET", "/people")}
    assert people["Ada Lovelace"]["department_name"] == "Engineering"
    assert people["Grace Hopper"]["department_name"] == "Engineering"
    assert len(await ws.call("GET", "/departments")) == 1  # created once, reused

    again = await _import(ws, "people", PEOPLE, "preview")
    assert _actions(again)[:2] == [(2, "skip"), (3, "skip")]  # never overwritten


async def test_responsibilities_and_assignments_never_replace_owners(ws: Ws) -> None:
    result = await _import(ws, "responsibilities", RESPONSIBILITIES)
    assert _actions(result) == [(2, "create"), (3, "create"), (4, "error")]
    await _import(ws, "people", "name,email\nAda,ada@acme.test\nBob,bob@acme.test\n")
    await ws.call("POST", "/teams", 201, json={"name": "Platform"})

    payments = next(
        r for r in await ws.call("GET", "/responsibilities") if r["name"] == "Payments on-call"
    )
    bob = next(p for p in await ws.call("GET", "/people") if p["display_name"] == "Bob")
    await ws.call(
        "POST",
        f"/responsibilities/{payments['id']}/assignments",
        201,
        json={"person_id": bob["id"], "role": "primary"},
    )

    assignments = (
        "responsibility,owner,role,owner_type\n"
        "Payments on-call,ada@acme.test,primary,\n"  # Bob is primary: must not be replaced
        "Payments on-call,ada@acme.test,backup,\n"
        "Payments on-call,bob@acme.test,primary,\n"  # identical: skipped
        "Quarterly audit,Platform,primary,team\n"
        "Quarterly audit,Ada,co-owner,\n"
        "Nope,Ada,backup,\n"
        "Quarterly audit,Nobody,backup,\n"
    )
    preview = await _import(ws, "assignments", assignments, "preview")
    assert _actions(preview) == [
        (2, "error"),
        (3, "create"),
        (4, "skip"),
        (5, "create"),
        (6, "create"),
        (7, "error"),
        (8, "error"),
    ]
    assert "transfer case" in preview["rows"][0]["message"]

    committed = await _import(ws, "assignments", assignments)
    assert committed["created"] == 3
    detail = await ws.call("GET", f"/responsibilities/{payments['id']}")
    owners = {(o["role"], o["assignee"]["name"]) for o in detail["owners_as_of"]}
    assert owners == {("primary", "Bob"), ("backup", "Ada")}
    history = await ws.call("GET", f"/responsibilities/{payments['id']}/history")
    assert any(h["reason"] == "Imported from CSV" for h in history)
    events = await ws.call("GET", "/audit-events")
    assert any(e["action"] == "import.committed" for e in events)


async def test_bad_files_and_permissions(api: Api, ws: Ws) -> None:
    await ws.call("POST", "/imports/preview", 422, json={"kind": "people", "csv": "email\nx@y.z\n"})
    big = "name\n" + "".join(f"P{i}\n" for i in range(1001))
    await ws.call("POST", "/imports/preview", 422, json={"kind": "people", "csv": big})
    await ws.call("POST", "/imports/preview", 422, json={"kind": "assets", "csv": "name\nx\n"})

    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    await member.call("POST", "/imports/preview", 403, json={"kind": "people", "csv": "name\nX\n"})
    await member.call("POST", "/imports/commit", 403, json={"kind": "people", "csv": "name\nX\n"})
    assert await ws.call("GET", "/people") == []
