"""Handover Copilot: answers grounded only in the handover's evidence, or an honest no."""

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from tests.api import Api, Ws, make_api
from tests.intelligence.test_analysis import (
    CANARY,
    Script,
    case_with_knowledge,
    drain,
    ref_of,
    script,
)
from tests.intelligence.test_handover import member_id

pytestmark = pytest.mark.anyio
__all__ = ["script"]  # fixture re-export


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(llm_providers="fake") as a:
        yield a


async def handover(api: Api) -> tuple[Ws, Ws, str]:
    """An analysed departure and a capsule for the member who takes over."""
    ws, member, cid = await case_with_knowledge(api)
    await ws.call("POST", f"/cases/{cid}/analysis", 202)
    await drain(api, ws.id)
    await ws.call("PATCH", "/ai/capabilities/handover_generator", 204, json={"enabled": False})
    capsule = await ws.call(
        "POST", f"/cases/{cid}/capsules", 201, json={"recipient_user_id": await member_id(ws)}
    )
    return ws, member, capsule["id"]


def ask(who: Ws, capsule: str, question: str, expected: int = 201) -> Any:
    return who.call(
        "POST", f"/ai/capsules/{capsule}/questions", expected, json={"question": question}
    )


async def test_answer_cites_the_handover_evidence(api: Api, script: list[Script]) -> None:
    ws, member, capsule = await handover(api)
    seen: list[dict[str, str]] = []

    def answer(refs: dict[str, str]) -> dict[str, Any]:
        seen.append(refs)
        return {
            "found": True,
            "answer": "Open the dashboard first ["
            + ref_of(refs, "Rotate the webhook secret")
            + "].",
            "evidence": [],
            "confidence": "high",
        }

    script.append(answer)
    reply = await ask(member, capsule, "How do I rotate the webhook secret?")
    assert reply["mode"] == "ai"
    assert reply["answer"] == "Open the dashboard first."
    assert [e["title"] for e in reply["evidence"]] == ["Rotate the webhook secret"]
    assert reply["confidence"] == "high"
    # A member recipient's pool never contains managers-only evidence.
    assert "Vault recovery" not in seen[0].values()
    thread = await member.call("GET", f"/ai/capsules/{capsule}/questions")
    assert [q["question"] for q in thread] == ["How do I rotate the webhook secret?"]
    assert (await ws.call("GET", f"/ai/capsules/{capsule}/questions"))[0]["id"] == reply["id"]


async def test_unanswerable_questions_get_a_cited_not_found(api: Api, script: list[Script]) -> None:
    _ws, member, capsule = await handover(api)
    script.append(lambda refs: {"found": False, "answer": "No source covers this.", "evidence": []})
    reply = await ask(member, capsule, "Where is the webhook secret rotation calendar?")
    assert reply["mode"] == "not_found"
    assert "isn't answered by the evidence" in reply["answer"]
    assert reply["evidence"], "closest sources are cited"
    assert reply["confidence"] is None


async def test_invented_citations_are_never_served_as_answers(
    api: Api, script: list[Script]
) -> None:
    ws, member, capsule = await handover(api)
    script.append(lambda refs: {"found": True, "answer": "Ask Mallory.", "evidence": ["E999"]})
    reply = await ask(member, capsule, "Who approves refunds?")
    assert reply["mode"] == "not_found"
    assert "Mallory" not in reply["answer"]
    runs = await ws.call("GET", "/ai/runs")
    assert runs[0]["capability"] == "handover_copilot"
    assert runs[0]["state"] == "needs_human_review"


async def test_uncited_found_answers_are_rejected(api: Api, script: list[Script]) -> None:
    _ws, member, capsule = await handover(api)
    script.append(lambda refs: {"found": True, "answer": "From memory: use Vault.", "evidence": []})
    reply = await ask(member, capsule, "Which tool stores secrets?")
    assert reply["mode"] == "not_found"
    assert "Vault" not in reply["answer"]


async def test_without_ai_the_reply_is_a_labelled_search(api: Api) -> None:
    ws, member, capsule = await handover(api)
    await ws.call("PATCH", "/ai/capabilities/handover_copilot", 204, json={"enabled": False})
    reply = await ask(member, capsule, "How do I rotate the webhook secret?")
    assert reply["mode"] == "search"
    assert "switched off" in reply["note"]
    assert reply["evidence"][0]["title"] == "Rotate the webhook secret"
    nothing = await ask(member, capsule, "Zebra quokka?")
    assert (nothing["mode"], nothing["evidence"]) == ("not_found", [])


async def test_injection_in_evidence_does_not_leak_restricted_data(
    api: Api, script: list[Script]
) -> None:
    _ws, member, capsule = await handover(api)
    script.append(
        lambda refs: {
            "found": True,
            "answer": CANARY,
            "evidence": [ref_of(refs, "Incident notes")],
        }
    )
    reply = await ask(member, capsule, "What do the incident notes say?")
    # The model can only cite what the member may see; the reply carries their sources only.
    assert all(e["audience"] == "workspace" for e in reply["evidence"])
    assert {e["title"] for e in reply["evidence"]} == {"Incident notes"}


async def test_only_the_recipient_and_editors_can_ask(api: Api) -> None:
    ws, member, capsule = await handover(api)
    from tests.api import add_member

    await add_member(api, ws.id, "user_bystander", "member")
    bystander = Ws(api, ws.id, "user_bystander")
    await ask(bystander, capsule, "Can I see this?", 404)
    await bystander.call("GET", f"/ai/capsules/{capsule}/questions", 404)
    await ask(member, capsule, "x", 422)  # too short
    await member.call(
        "POST", f"/ai/capsules/{capsule}/questions", 422, json={"question": "ok?", "extra": 1}
    )
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    await ask(other, capsule, "Leak?", 404)


async def test_brief_uses_the_committed_sections(api: Api) -> None:
    _ws, member, capsule = await handover(api)
    view = await member.call("GET", f"/ai/capsules/{capsule}")
    headings = [s["heading"] for s in view["sections"]]
    known = {
        "What you now own",
        "In-flight work",
        "Decisions already made",
        "Knowledge gaps and open questions",
        "Risks and conflicts",
        "Dependencies",
        "From the handover interview",
        "Recommended first steps",
        "Other findings",
    }
    assert headings
    assert set(headings) <= known
    assert "changed_sources" in view


# --- streaming ------------------------------------------------------------------------


async def ask_stream(who: Ws, capsule: str, question: str) -> list[tuple[str, Any]]:
    """The server-sent events of one streamed answer, parsed."""
    response = await who.api.client.post(
        f"/workspaces/{who.id}/ai/capsules/{capsule}/questions/stream",
        headers=who.api.as_user(who.sub),
        json={"question": question},
    )
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    events = []
    for block in response.text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return events


async def test_streamed_answer_sends_evidence_then_text_then_the_stored_answer(
    api: Api, script: list[Script]
) -> None:
    ws, member, capsule = await handover(api)

    def answer(refs: dict[str, str]) -> str:
        ref = ref_of(refs, "Rotate the webhook secret")
        return (
            f"Open the dashboard first [{ref}].\n- Then rotate the key [{ref}].\nConfidence: high"
        )

    script.append(answer)
    events = await ask_stream(member, capsule, "How do I rotate the webhook secret?")
    names = [name for name, _ in events]
    assert names[0] == "evidence"
    assert names[-1] == "final"
    assert set(names[1:-1]) == {"delta"}
    assert len(names) > 3  # written as it arrives, not in one piece
    titles = [s["title"] for s in events[0][1]["sources"]]
    assert "Rotate the webhook secret" in titles
    assert "Vault recovery" not in titles  # managers-only evidence never reaches a member
    streamed = "".join(data["text"] for name, data in events if name == "delta")
    assert "Confidence: high" in streamed
    final = events[-1][1]
    assert final["mode"] == "ai"
    assert final["answer"] == "Open the dashboard first.\n- Then rotate the key."
    assert final["confidence"] == "high"
    assert [e["title"] for e in final["evidence"]] == ["Rotate the webhook secret"]
    # Stored and audited like a non-streamed answer.
    thread = await member.call("GET", f"/ai/capsules/{capsule}/questions")
    assert [q["id"] for q in thread] == [final["id"]]
    runs = await ws.call("GET", "/ai/runs")
    assert [r["state"] for r in runs if r["capability"] == "handover_copilot"] == ["completed"]


async def test_streamed_invented_citation_ends_as_not_found(api: Api, script: list[Script]) -> None:
    _ws, member, capsule = await handover(api)
    script.append(lambda refs: "It rotates every Monday [E99].\nConfidence: high")
    events = await ask_stream(member, capsule, "When does the webhook secret rotate?")
    final = events[-1][1]
    assert final["mode"] == "not_found"
    assert "isn't answered by the evidence" in final["answer"]


async def test_streamed_not_found_is_an_honest_no(api: Api, script: list[Script]) -> None:
    _ws, member, capsule = await handover(api)
    script.append(lambda refs: "NOT_FOUND: no source covers the calendar.\nConfidence: low")
    final = (await ask_stream(member, capsule, "Where is the rotation calendar?"))[-1][1]
    assert final["mode"] == "not_found"


async def test_streaming_without_ai_replays_a_labelled_search(api: Api) -> None:
    ws, member, capsule = await handover(api)
    await ws.call("PATCH", "/ai/capabilities/handover_copilot", 204, json={"enabled": False})
    events = await ask_stream(member, capsule, "How do I rotate the webhook secret?")
    assert [name for name, _ in events] == ["evidence", "final"]
    final = events[-1][1]
    assert final["mode"] == "search"
    assert final["note"]


async def test_only_the_recipient_and_editors_can_stream(api: Api) -> None:
    ws, _member, capsule = await handover(api)
    from tests.api import add_member

    await add_member(api, ws.id, "user_bystander", "member")
    bystander = Ws(api, ws.id, "user_bystander")
    response = await api.client.post(
        f"/workspaces/{ws.id}/ai/capsules/{capsule}/questions/stream",
        headers=api.as_user("user_bystander"),
        json={"question": "Can I see this?"},
    )
    assert response.status_code == 404
    await bystander.call("GET", f"/ai/capsules/{capsule}/questions", 404)


async def test_streamed_bare_refs_count_only_when_they_are_real(
    api: Api, script: list[Script]
) -> None:
    _ws, member, capsule = await handover(api)

    def answer(refs: dict[str, str]) -> str:
        ref = ref_of(refs, "Rotate the webhook secret")
        return f"**Evidence {ref}** says to open the dashboard first.\nConfidence: medium"

    script.append(answer)
    final = (await ask_stream(member, capsule, "How do I rotate the webhook secret?"))[-1][1]
    assert final["mode"] == "ai"
    assert "**" not in final["answer"]
    script.append(lambda refs: "Evidence E99 says it rotates on Mondays.\nConfidence: high")
    final = (await ask_stream(member, capsule, "When does it rotate?"))[-1][1]
    assert final["mode"] == "not_found"
