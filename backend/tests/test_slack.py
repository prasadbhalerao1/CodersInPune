"""Slack: an encrypted incoming webhook, a test message on connect, posts only on request."""

from collections.abc import AsyncIterator
from typing import Any

import pytest
from cryptography.fernet import Fernet

from relay.integrations.slack import service as slack
from tests.api import Api, make_api
from tests.intelligence.test_analysis import case_with_knowledge

pytestmark = pytest.mark.anyio
URL = "https://hooks.slack.com/services/T000/B000/secret"


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(integration_encryption_key=Fernet.generate_key().decode()) as a:
        yield a


@pytest.fixture
def posted(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, dict[str, Any]]]:
    sent: list[tuple[str, dict[str, Any]]] = []

    async def fake(url: str, payload: dict[str, Any]) -> str | None:
        sent.append((url, payload))
        return "slack_invalid_token" if "bad" in url else None

    monkeypatch.setattr(slack, "_post", fake)
    return sent


async def test_connect_tests_the_webhook_and_never_returns_it(
    api: Api, posted: list[tuple[str, dict[str, Any]]]
) -> None:
    ws, member, _cid = await case_with_knowledge(api)
    await ws.call(
        "PUT", "/integrations/slack", 422, json={"webhook_url": "https://x.y", "channel": "a"}
    )
    await ws.call(
        "PUT", "/integrations/slack", 422, json={"webhook_url": URL + "bad", "channel": "a"}
    )
    view = await ws.call(
        "PUT", "/integrations/slack", 200, json={"webhook_url": URL, "channel": "#handovers"}
    )
    assert (view["connected"], view["channel"]) == (True, "handovers")
    assert "secret" not in str(view)
    assert "connected" in posted[-1][1]["text"]
    await member.call("PUT", "/integrations/slack", 403, json={"webhook_url": URL, "channel": "x"})
    assert (await member.call("GET", "/integrations/slack"))["can_manage"] is False


async def test_sharing_a_meeting_posts_its_items_with_a_link(
    api: Api, posted: list[tuple[str, dict[str, Any]]]
) -> None:
    ws, _member, _cid = await case_with_knowledge(api)
    await ws.call("PATCH", "/ai", 204, json={"enabled": False})
    meeting = await ws.call(
        "POST",
        "/meetings",
        201,
        json={"title": "Sync", "transcript": "Ravi: We decided to keep webhooks on v1."},
    )
    await ws.call("POST", f"/meetings/{meeting['id']}/slack", 409)  # not connected yet
    await ws.call("PUT", "/integrations/slack", 200, json={"webhook_url": URL, "channel": "ops"})
    result = await ws.call("POST", f"/meetings/{meeting['id']}/slack", 200)
    assert result["channel"] == "ops"
    url, payload = posted[-1]
    assert url == URL
    text = str(payload["blocks"])
    assert "keep webhooks on v1" in text
    assert f"/meetings/{meeting['id']}" in text
    assert "Ravi:" not in text  # the items, never the raw transcript
    await ws.call("DELETE", "/integrations/slack", 204)
    assert (await ws.call("GET", "/integrations/slack"))["connected"] is False
