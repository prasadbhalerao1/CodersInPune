"""Rate limits on sensitive endpoints: per user, with Retry-After."""

from collections.abc import AsyncIterator

import psycopg
import pytest

from tests.api import OWNER, Api, make_api
from tests.db import APP_URL, libpq_url
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


async def test_limits_are_shared_by_every_api_replica(api: Api) -> None:
    """Two app instances (replicas) count against the same window in PostgreSQL."""
    async with make_api(FakeExternal()) as replica:
        for i in range(10):
            await (api if i % 2 else replica).create_workspace(OWNER, f"Acme {i}")
        blocked = await replica.client.post(
            "/workspaces",
            json={"name": "One too many"},
            headers={**replica.as_user(OWNER), "Idempotency-Key": "k-11"},
        )
    assert blocked.status_code == 429
    # The app role can only call the counting function, never read or reset counters.
    with (
        psycopg.connect(libpq_url(APP_URL)) as conn,
        pytest.raises(psycopg.errors.InsufficientPrivilege),
    ):
        conn.execute("DELETE FROM platform.rate_limit_window")
