"""Product guidance: tours unlock from real workspace state; integrations count as ready only
after their sync jobs finish; the switch silences prompts but never the tutorials."""

from typing import Any

import pytest

from tests.api import OWNER, Api, Ws, add_member
from tests.fakes import FakeExternal
from tests.security.test_linear import api, connect, ext, run, ws

pytestmark = pytest.mark.anyio
__all__ = ["api", "ext", "ws"]  # fixture re-exports


def tours(view: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {t["id"]: t for t in view["tours"]}


def linear(view: dict[str, Any]) -> str:
    return next(i["state"] for i in view["integrations"] if i["provider"] == "linear")


async def test_tours_unlock_with_the_workspace(api: Api, ws: Ws) -> None:
    view = await ws.call("GET", "/guidance")
    assert view["enabled"]
    assert view["suggested"] == "basics"
    t = tours(view)
    assert t["basics"]["eligible"]
    assert not t["ownership"]["eligible"]
    assert t["ownership"]["reason"]
    assert not t["what_if"]["eligible"]
    assert t["what_if"]["path"] is None
    essentials = {c["key"]: c["done"] for c in view["checklist"] if c["essential"]}
    assert essentials["workspace"]
    assert not essentials["ownership"]
    assert {c["key"] for c in view["checklist"] if not c["essential"]} == {
        "github", "linear", "notion",
    }  # fmt: skip

    person = await ws.person("Arjun")
    rid = await ws.responsibility("Production deployments", "critical")
    await ws.call(
        "POST", f"/responsibilities/{rid}/assignments", 201,
        json={"role": "primary", "person_id": person},
    )  # fmt: skip
    t = tours(await ws.call("GET", "/guidance"))
    assert t["ownership"]["eligible"]
    assert t["what_if"]["eligible"]
    assert t["what_if"]["path"].endswith("/simulator")

    # A member can't simulate: the tour says why instead of leading to a 403.
    await add_member(api, ws.id, "member-sub", "member")
    member = Ws(api, ws.id, "member-sub")
    m = tours(await member.call("GET", "/guidance"))["what_if"]
    assert not m["eligible"]
    assert "role" in m["reason"]


async def test_switch_progress_resume_and_reset(api: Api, ws: Ws) -> None:
    off = await ws.call("PATCH", "/guidance", json={"enabled": False})
    assert not off["enabled"]
    assert off["suggested"] is None
    assert tours(off)["basics"]["eligible"]  # tutorials stay available when switched off

    view = await ws.call("PATCH", "/guidance", json={"progress": ["basics", 2]})
    assert tours(view)["basics"]["resume_step"] == 2
    view = await ws.call("PATCH", "/guidance", json={"complete": "basics", "dismiss": "checklist"})
    assert tours(view)["basics"]["completed"]
    assert tours(view)["basics"]["resume_step"] is None
    assert view["checklist_dismissed"]

    view = await ws.call("PATCH", "/guidance", json={"reset": True, "enabled": True})
    assert not tours(view)["basics"]["completed"]
    assert view["enabled"]
    assert view["checklist_dismissed"]  # resetting tours doesn't resurrect dismissed panels

    # Another member's state is separate.
    await add_member(api, ws.id, "other-sub", "member")
    other = await Ws(api, ws.id, "other-sub").call("GET", "/guidance")
    assert other["enabled"]
    assert not other["checklist_dismissed"]

    await ws.call("PATCH", "/guidance", 422, json={"complete": "made_up"})
    await ws.call("PATCH", "/guidance", 422, json={"dismiss": "<script>"})
    await ws.call("PATCH", "/guidance", 422, json={"unknown": True})


async def test_an_integration_is_ready_only_after_its_sync_finishes(
    api: Api, ws: Ws, ext: FakeExternal
) -> None:
    assert linear(await ws.call("GET", "/guidance")) == "not_connected"
    await connect(api, ws, ext)
    view = await ws.call("GET", "/guidance")
    assert linear(view) == "syncing"  # connected is not ready
    assert not tours(view)["integrations"]["eligible"]

    ext.linear_down = True
    await run(api, ws.id)
    assert linear(await ws.call("GET", "/guidance")) == "retrying"
    ext.linear_down = False
    await run(api, ws.id)
    view = await ws.call("GET", "/guidance")
    assert linear(view) == "ready"
    assert tours(view)["integrations"]["eligible"]
    assert next(c for c in view["checklist"] if c["key"] == "linear")["done"]

    ext.linear_tokens.clear()
    ext.linear_refresh.clear()
    connection = (await ws.call("GET", "/integrations/linear"))["connections"][0]
    await ws.call("POST", f"/integrations/linear/connections/{connection['id']}/sync", 202)
    await run(api, ws.id)
    assert linear(await ws.call("GET", "/guidance")) == "attention"


async def test_outsiders_get_nothing(api: Api, ws: Ws) -> None:
    other = Ws(api, await api.create_workspace("outsider", "Other"), "outsider")
    resp = await api.client.get(f"/workspaces/{ws.id}/guidance", headers=api.as_user(other.sub))
    assert resp.status_code in (403, 404)
    assert other.sub != OWNER
