"""Handover Copilot: answers grounded only in the handover's evidence, or an honest no."""

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
