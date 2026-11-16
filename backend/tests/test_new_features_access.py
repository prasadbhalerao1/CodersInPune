"""Round 3 features on a brand-new workspace, and read-only roles on every new write."""

from collections.abc import AsyncIterator

import pytest

from tests.api import OWNER, Api, Ws, add_member, make_api

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(llm_providers="fake") as a:
        yield a


async def test_an_empty_workspace_loads_every_new_page(api: Api) -> None:
    ws = Ws(api, await api.create_workspace(OWNER, "Fresh Co"))
    for path in (
        "/meetings",
        "/decisions",
        "/knowledge-drift",
        "/search/expertise",
        "/integrations/slack",
        "/role-preview",
    ):
        await ws.call("GET", path)  # 200 with empty data, never an error
    assert await ws.call("GET", "/meetings") == []
    assert (await ws.call("GET", "/search/expertise"))["rows"] == []


@pytest.mark.parametrize("role", ["guest", "auditor"])
async def test_read_only_roles_cannot_write_anything_new(api: Api, role: str) -> None:
    ws = Ws(api, await api.create_workspace(OWNER, "Acme"))
    meeting = await ws.call(
        "POST", "/meetings", 201, json={"title": "Sync", "transcript": "We decided to ship."}
    )
    item = meeting["items"][0]["id"] if meeting["items"] else None
    await add_member(api, ws.id, f"user_{role}", role)
    reader = Ws(api, ws.id, f"user_{role}")
    # Auditors read AI-derived records; guests (outside contractors) do not.
    await reader.call("GET", "/meetings", 403 if role == "guest" else 200)
    await reader.call("POST", "/meetings", 403, json={"title": "X", "transcript": "Y"})
    if item:
        await reader.call("POST", f"/meeting-items/{item}/accept", 403)
    await reader.call(
        "PUT", "/integrations/slack", 403, json={"webhook_url": "https://x", "channel": "c"}
    )
    await reader.call("PUT", "/role-preview", 404, json={"role": "owner"})  # not a sample
