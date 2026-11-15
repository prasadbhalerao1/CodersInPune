"""Ask Relay: workspace-wide answers from records the asker can see, citing them."""

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from relay.intelligence.ask import Source, finalise, keywords
from tests.api import Api, Ws, make_api
from tests.intelligence.test_analysis import Script, case_with_knowledge, script

pytestmark = pytest.mark.anyio
__all__ = ["script"]  # fixture re-export


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(llm_providers="fake") as a:
        yield a


async def ask(who: Ws, question: str) -> list[tuple[str, Any]]:
    response = await who.api.client.post(
        f"/workspaces/{who.id}/ask", headers=who.api.as_user(who.sub), json={"question": question}
    )
    assert response.status_code == 200, response.text
    out = []
    for block in response.text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        out.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


def test_keywords_drop_filler_words() -> None:
    assert keywords("How do we rotate the webhook secret?") == ["rotate", "webhook", "secret"]


def test_only_given_evidence_counts_as_a_citation() -> None:
    given = [Source(ref="E1", kind="knowledge", id="x", title="t", detail=None, url=None)]
    good = finalise("Rotate it monthly [E1, E7].", given)
    assert (good.mode, good.cited, good.answer) == ("ai", ["E1"], "Rotate it monthly [E1].")
    assert finalise("Rotate it monthly [E7].", given).mode == "not_found"
    assert finalise("NOT_FOUND: nothing about refunds.", given).mode == "not_found"


async def test_answer_streams_and_cites_only_what_the_member_may_see(
    api: Api, script: list[Script]
) -> None:
    _ws, member, _cid = await case_with_knowledge(api)
    seen: list[str] = []

    def answer(refs: dict[str, str]) -> str:
        seen.extend(refs.values())
        return "Open the dashboard first [E1]."

    script.append(answer)
    events = await ask(member, "How do we rotate the webhook secret?")
    names = [n for n, _ in events]
    assert names[0] == "sources"
    assert names[-1] == "final"
    assert "delta" in names
    titles = [s["title"] for s in events[0][1]["sources"]]
    assert "Rotate the webhook secret" in titles
    assert "Vault recovery" not in titles
    assert "Vault recovery" not in seen
    final = events[-1][1]
    assert final["mode"] == "ai"
    assert final["cited"] == ["E1"]


async def test_without_ai_the_best_records_are_the_answer(api: Api) -> None:
    ws, _member, _cid = await case_with_knowledge(api)
    await ws.call("PATCH", "/ai", 204, json={"enabled": False})
    events = await ask(ws, "webhook secret rotation")
    final = events[-1][1]
    assert final["mode"] == "search"
    assert final["cited"]
    assert final["note"]
    nothing = await ask(ws, "zebra quokka marmalade")
    assert nothing[-1][1]["mode"] == "not_found"


async def test_meeting_items_are_searchable_evidence(api: Api, script: list[Script]) -> None:
    ws, _member, _cid = await case_with_knowledge(api)
    await ws.call("PATCH", "/ai", 204, json={"enabled": False})
    await ws.call(
        "POST",
        "/meetings",
        201,
        json={
            "title": "Sync",
            "transcript": "Ravi: We decided to keep webhooks on v1 until March.",
        },
    )
    final = await ask(ws, "What did we decide about webhooks?")
    sources = final[0][1]["sources"]
    assert any(s["kind"] == "meeting" and "keep webhooks" in s["title"] for s in sources)
