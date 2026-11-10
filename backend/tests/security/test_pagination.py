"""Long lists page with a keyset cursor instead of being silently truncated."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from tests.api import OWNER, Api, Ws, make_api

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


async def _all_pages(api: Api, ws: Ws, path: str, limit: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    pages, after = 0, None
    while True:
        params: dict[str, Any] = {"limit": limit}
        if after:
            params["after"] = after
        response = await api.client.get(
            f"/workspaces/{ws.id}{path}", params=params, headers=api.as_user(OWNER)
        )
        assert response.status_code == 200, response.text
        page = response.json()
        assert len(page) <= limit
        items += page
        pages += 1
        after = response.headers.get("X-Next-Cursor")
        if not after:
            return items, pages


async def test_people_responsibilities_and_cases_page_without_gaps(api: Api) -> None:
    ws = Ws(api, await api.create_workspace(OWNER, "Acme"))
    names = ["Ava", "Ben", "Cy", "Cy", "Dee"]  # a duplicate name must not be skipped
    for name in names:
        await ws.person(name)
        await ws.responsibility(f"Duty {name}")

    people, pages = await _all_pages(api, ws, "/people", 2)
    assert (sorted(p["display_name"] for p in people), pages) == (sorted(names), 3)
    assert len({p["id"] for p in people}) == len(names)
    duties, _ = await _all_pages(api, ws, "/responsibilities", 2)
    assert len({d["id"] for d in duties}) == len(names)

    response = await api.client.get(f"/workspaces/{ws.id}/people", headers=api.as_user(OWNER))
    assert "X-Next-Cursor" not in response.headers  # everything fits in the default page

    forged = await api.client.get(
        f"/workspaces/{ws.id}/people", params={"after": "bm90LWpzb24"}, headers=api.as_user(OWNER)
    )
    assert (forged.status_code, forged.json()["code"]) == (422, "invalid_cursor")

    for title in ("Move billing", "Move payroll", "Move support"):
        await ws.call(
            "POST",
            "/cases",
            201,
            json={"case_type": "transfer", "title": title, "starts_at": "2026-12-01T09:00:00Z"},
        )
    cases, pages = await _all_pages(api, ws, "/cases", 2)
    assert (len({c["id"] for c in cases}), pages) == (3, 2)
