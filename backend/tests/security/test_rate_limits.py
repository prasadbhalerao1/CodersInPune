"""Rate limits on sensitive endpoints: per user, with Retry-After."""

from collections.abc import AsyncIterator

import pytest

from tests.api import OWNER, Api, make_api
from tests.fakes import FakeExternal

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(FakeExternal()) as a:
        yield a


async def test_workspace_creation_is_limited_per_user(api: Api) -> None:
    for i in range(10):
        await api.create_workspace(OWNER, f"Acme {i}")
    blocked = await api.client.post(
        "/workspaces",
        json={"name": "One too many"},
        headers={**api.as_user(OWNER), "Idempotency-Key": "k-11"},
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert blocked.json()["code"] == "rate_limited"
    # Another user has their own window.
    assert await api.create_workspace("user_other", "Other")
