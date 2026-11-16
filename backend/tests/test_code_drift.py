"""Code drift: knowledge flagged when its repository changed after it was last reviewed."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from relay.catalog.models import KnowledgeItem
from relay.shared.db import unit_of_work
from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.intelligence.test_memory_replay import history

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


async def test_merged_pull_requests_after_review_flag_the_knowledge(api: Api) -> None:
    ws, _rid = await history(api)
    assert await ws.call("GET", "/knowledge-drift") == []  # written after every merge
    async with unit_of_work(api.app.state.session_factory, ws.id, OWNER) as s:
        await s.execute(
            update(KnowledgeItem).values(
                updated_at=datetime.now(UTC) - timedelta(days=150),
                last_reviewed_at=datetime.now(UTC) - timedelta(days=150),
            )
        )
    drift = await ws.call("GET", "/knowledge-drift")
    assert [d["title"] for d in drift] == ["Canary every deploy"]
    # Two merges in acme/deploy plus one in the managers-only acme/secret.
    assert drift[0]["merged_since"] == 3
    assert drift[0]["latest"][0]["title"] == "Rotate signing key"  # newest first

    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    seen = await member.call("GET", "/knowledge-drift")
    assert seen[0]["merged_since"] == 2  # restricted repository work stays hidden
    assert all(c["repository"] == "acme/deploy" for c in seen[0]["latest"])
