"""Interview → capsule → approval → acknowledgement, with audience limits and redaction."""

from collections.abc import AsyncIterator
from typing import Any

import psycopg
import pytest

from tests.api import Api, Ws, make_api
from tests.db import OWNER_URL, libpq_url
from tests.intelligence.test_analysis import (
    CANARY,
    Script,
    case_with_knowledge,
    drain,
    ref_of,
    script,
)

pytestmark = pytest.mark.anyio
__all__ = ["script"]  # fixture re-export


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(llm_providers="fake") as a:
        yield a


def link_member_to_affected_person(ws: Ws) -> None:
    """The member is the person leaving: same email on membership and directory person."""
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(ws.id),))
        conn.execute(
            "UPDATE identity.membership SET email = 'old@acme.test' WHERE tenant_id = %s AND "
            "role = 'member'",
            (ws.id,),
        )
        conn.execute(
            "UPDATE directory.person SET email = 'old@acme.test' WHERE tenant_id = %s",
            (ws.id,),
        )


async def member_id(ws: Ws) -> str:
    members = await ws.call("GET", "/members")
    return str(next(m["user_id"] for m in members if m["role"] == "member"))


async def test_interview_capsule_approval_and_acknowledgement(
    api: Api, script: list[Script]
) -> None:
    ws, member, cid = await case_with_knowledge(api)
    link_member_to_affected_person(ws)
    script.append(
        lambda refs: {
            "questions": [
                {
                    "question": "Where is the refund approval list kept?",
                    "why": "Not in any source.",
                    "evidence": [next(iter(refs))],
                },
                {"question": "Invented?", "why": "x", "evidence": ["E404"]},
            ]
        }
    )
    await ws.call("POST", f"/cases/{cid}/interview", 202)
    await drain(api, ws.id)

    asked = await member.call("GET", f"/cases/{cid}/interview")
    questions = {q["question"]: q for q in asked["questions"]}
    ai_q = questions["Where is the refund approval list kept?"]
    assert ai_q["ai"]
    assert ai_q["can_answer"]
    assert ai_q["evidence"]
    assert "Invented?" not in questions
    await member.call("POST", f"/ai/questions/{ai_q['id']}/review", 403)
    await member.call(
        "PATCH",
        f"/ai/questions/{ai_q['id']}",
        204,
        json={"status": "answered", "answer": "In the finance shared drive, 'Refunds' sheet."},
    )
    await ws.call("POST", f"/ai/questions/{ai_q['id']}/to-knowledge", 409)  # not reviewed
    await ws.call("POST", f"/ai/questions/{ai_q['id']}/review", 204)
    draft = await ws.call("POST", f"/ai/questions/{ai_q['id']}/to-knowledge", 201)
    assert (draft["type"], draft["status"]) == ("knowledge_draft", "pending")

    vault_claim = "The vault recovery phrase is held by legal."
    script.append(
        lambda refs: {
            "claims": [
                {
                    "kind": "finding",
                    "text": vault_claim,
                    "evidence": [ref_of(refs, "Vault recovery")],
                }
            ]
        }
    )
    await ws.call("POST", f"/cases/{cid}/analysis", 202)
    await drain(api, ws.id)

    def generator(refs: dict[str, str]) -> dict[str, Any]:
        first = next(iter(refs))
        return {
            "summary": "You now own payments on-call.",
            "sections": [
                {
                    "heading": "What you now own",
                    "points": [
                        {
                            "kind": "finding",
                            "text": "Payments on-call is yours.",
                            "evidence": [first],
                        },
                        {"kind": "finding", "text": "Made up.", "evidence": ["E999"]},
                    ],
                },
            ],
        }

    script.append(generator)
    recipient = await member_id(ws)
    capsule = await ws.call(
        "POST", f"/cases/{cid}/capsules", 201, json={"recipient_user_id": recipient}
    )
    assert (capsule["version"], capsule["source"], capsule["generating"]) == (1, "rules", True)
    assert any(o["reason"].startswith("Relies on evidence") for o in capsule["omissions"])
    assert CANARY not in str(capsule)
    assert vault_claim not in str(capsule)
    headings = [s["heading"] for s in capsule["sections"]]
    assert "From the handover interview" in headings

    await drain(api, ws.id)
    capsule = await ws.call("GET", f"/ai/capsules/{capsule['id']}")
    assert (capsule["version"], capsule["source"], capsule["summary"]) == (
        2,
        "ai",
        "You now own payments on-call.",
    )
    assert [p["text"] for s in capsule["sections"] for p in s["points"]] == [
        "Payments on-call is yours."
    ]
    # Coverage: the one responsibility in scope is named by a cited statement.
    assert [
        (c["name"], c["criticality"], c["statements"], c["cited"]) for c in capsule["coverage"]
    ] == [("Payments on-call", "critical", 1, 1)]

    # Redact the AI point: editors still see it marked, the recipient doesn't.
    key = capsule["sections"][0]["points"][0]["key"]
    edited = await ws.call("PATCH", f"/ai/capsules/{capsule['id']}", json={"redactions": [key]})
    assert edited["version"] == 3
    assert edited["sections"][0]["points"][0]["redacted"]
    seen = await member.call("GET", f"/ai/capsules/{capsule['id']}")
    assert seen["sections"] == []
    assert seen["coverage"][0]["statements"] == 0  # redacted points don't count for them
    assert seen["can_acknowledge"] is False
    assert any(o["reason"].startswith("Withheld") for o in seen["omissions"])

    await member.call("POST", f"/ai/capsules/{capsule['id']}/approve", 403)
    await member.call("POST", f"/ai/capsules/{capsule['id']}/acknowledge", 409)
    approved = await ws.call("POST", f"/ai/capsules/{capsule['id']}/approve")
    assert approved["status"] == "approved"
    assert approved["approved_by"]
    acked = await member.call("POST", f"/ai/capsules/{capsule['id']}/acknowledge")
    assert acked["status"] == "acknowledged"
    assert acked["acknowledged_at"]
    versions = await member.call("GET", f"/ai/capsules/{capsule['id']}/versions")
    assert next((v["version"], v["acknowledged"]) for v in versions) == (3, True)
    assert [c["recipient_user_id"] for c in await member.call("GET", f"/cases/{cid}/capsules")] == [
        recipient
    ]


async def test_a_stalled_ai_draft_is_reported_and_can_be_retried(
    api: Api, script: list[Script]
) -> None:
    ws, _, cid = await case_with_knowledge(api)
    script.append(lambda refs: {"claims": []})
    await ws.call("POST", f"/cases/{cid}/analysis", 202)
    await drain(api, ws.id)
    recipient = await member_id(ws)
    body = {"recipient_user_id": recipient}

    capsule = await ws.call("POST", f"/cases/{cid}/capsules", 201, json=body)
    assert (capsule["generating"], capsule["generation"]) == (True, "running")
    # Asking again while the draft is on its way does not start a second one.
    await ws.call("POST", f"/cases/{cid}/capsules", 201, json=body)
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(ws.id),))
        key = (ws.id, "handover_generator")
        count = conn.execute(
            "SELECT count(*) FROM intelligence.agent_run WHERE tenant_id = %s AND capability = %s",
            key,
        ).fetchone()
        assert count == (1,)
        # The worker never picked it up: past the time limit it is stalled, not spinning.
        conn.execute(
            "UPDATE intelligence.agent_run SET started_at = now() - interval '20 minutes' "
            "WHERE tenant_id = %s AND capability = %s",
            key,
        )

    stalled = await ws.call("GET", f"/ai/capsules/{capsule['id']}")
    assert (stalled["generating"], stalled["generation"]) == (False, "stalled")

    retried = await ws.call("POST", f"/cases/{cid}/capsules", 201, json=body)
    assert retried["generation"] == "running"
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(ws.id),))
        states = conn.execute(
            "SELECT state FROM intelligence.agent_run WHERE tenant_id = %s AND capability = %s "
            "ORDER BY created_at",
            key,
        ).fetchall()
    assert [s for (s,) in states] == ["timed_out", "running"]
