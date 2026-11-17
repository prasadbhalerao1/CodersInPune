"""Ask Relay: workspace-wide answers from records the asker can see, citing them."""

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo

from relay.intelligence import llm
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
    partial = finalise("NOT_FOUND: The full status isn't recorded, but it is blocked [E1].", given)
    assert (partial.mode, partial.cited) == ("ai", ["E1"])
    assert not partial.answer.startswith("NOT_FOUND")


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


async def test_responsibility_evidence_names_its_current_holders(api: Api) -> None:
    ws, _member, _cid = await case_with_knowledge(api)
    await ws.call("PATCH", "/ai", 204, json={"enabled": False})
    sources = (await ask(ws, "Who is the backup for payments on-call?"))[0][1]["sources"]
    duty = next(s for s in sources if s["kind"] == "responsibility")
    assert "primary Old Owner" in duty["detail"]


def test_conversation_is_answered_without_citations() -> None:
    given = [Source(ref="E1", kind="overview", id="x", title="t", detail=None, url=None)]
    hello = finalise("CHAT: Hi! I'm Relay's assistant [E1].", given)
    assert (hello.mode, hello.cited) == ("chat", [])
    assert hello.answer == "Hi! I'm Relay's assistant."


async def test_the_assistant_sees_the_whole_workspace_and_the_conversation(api: Api) -> None:
    _ws, member, _cid = await case_with_knowledge(api)
    prompts: list[str] = []

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        prompts.append(
            " ".join(
                str(p.content) for m in messages for p in m.parts if isinstance(p, UserPromptPart)
            )
        )
        return ModelResponse(parts=[TextPart("CHAT: Hi, I'm Relay's assistant.")])

    llm.Gateway._cooldown.clear()
    llm.fake_handler = respond
    try:
        response = await member.api.client.post(
            f"/workspaces/{member.id}/ask",
            headers=member.api.as_user(member.sub),
            json={"question": "Hi", "history": [{"question": "Who are you?", "answer": "Relay."}]},
        )
    finally:
        llm.fake_handler = None
    assert response.status_code == 200, response.text
    final = json.loads(response.text.strip().split("\n\n")[-1].split("data: ", 1)[1])
    assert final["mode"] == "chat"
    assert final["cited"] == []
    prompt = prompts[0]
    assert "Responsibilities and who holds them" in prompt
    assert "Payments on-call" in prompt
    assert "Who are you?" in prompt
    assert "Vault recovery" not in prompt


async def test_a_greeting_without_ai_is_not_an_error(api: Api) -> None:
    ws, _member, _cid = await case_with_knowledge(api)
    await ws.call("PATCH", "/ai", 204, json={"enabled": False})
    events = await ask(ws, "Hi")
    assert events[-1][1]["mode"] == "not_found"
