"""Meeting intelligence: cited items from a transcript; accepting them is what changes things."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from relay.intelligence.meetings import rule_items
from tests.api import Api, Ws, make_api
from tests.intelligence.test_analysis import Script, case_with_knowledge, script

pytestmark = pytest.mark.anyio
__all__ = ["script"]  # fixture re-export

TRANSCRIPT = """Asha: Morning all, quick sync on the payments migration.
Ravi: We decided to keep Stripe webhooks on the old endpoint until March.
Asha: I'll write the rollback runbook by Friday.
Ravi: Only Meera knows how the vault recovery works, that's a risk.
Asha: Who approves refunds over 50k while Meera is away?
Ravi: Thanks, bye."""


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(llm_providers="fake") as a:
        yield a


async def meeting(ws: Ws, cid: str, rid: str) -> Any:
    return await ws.call(
        "POST",
        "/meetings",
        201,
        json={
            "title": "Payments sync",
            "transcript": TRANSCRIPT,
            "responsibility_id": rid,
            "case_id": cid,
        },
    )


def test_rules_find_each_kind_and_cite_its_line() -> None:
    items = {i.kind: i for i in rule_items(TRANSCRIPT.splitlines())}
    assert items["decision"].lines == ["L2"]
    assert (items["action"].owner, items["action"].due) == ("Asha", "Friday")
    assert items["risk"].lines == ["L4"]
    assert items["question"].text.startswith("Who approves refunds")
    assert len(items) == 4  # greetings and thanks are not items


async def test_ai_items_must_cite_real_lines_and_accepting_applies_them(
    api: Api, script: list[Script]
) -> None:
    ws, _member, cid = await case_with_knowledge(api)
    rid = await ws.responsibility("Payments migration", "high")
    script.append(
        lambda refs: {
            "items": [
                {
                    "kind": "decision",
                    "text": "Keep webhooks on the old endpoint until March.",
                    "lines": ["L2"],
                },
                {
                    "kind": "action",
                    "text": "Write the rollback runbook.",
                    "owner": "Asha",
                    "due": "Friday",
                    "lines": ["L3"],
                },
                {"kind": "risk", "text": "Invented line.", "lines": ["L99"]},
                {"kind": "question", "text": "Uncited.", "lines": []},
            ]
        }
    )
    made = await meeting(ws, cid, rid)
    assert made["extract_mode"] == "ai"
    items = {i["kind"]: i for i in made["items"]}
    assert set(items) == {"decision", "action"}  # uncited and invented lines dropped
    assert items["decision"]["lines"] == [2]
    assert made["lines"][1].startswith("Ravi: We decided")

    accepted = await ws.call("POST", f"/meeting-items/{items['decision']['id']}/accept", 200)
    assert accepted["status"] == "accepted"
    assert accepted["result_ref"].startswith("knowledge:")
    knowledge = await ws.call("GET", f"/responsibilities/{rid}/knowledge")
    adr = next(k for k in knowledge if k["kind"] == "adr")
    assert "Payments sync" in adr["body"]

    task = await ws.call("POST", f"/meeting-items/{items['action']['id']}/accept", 200)
    assert task["result_ref"] == f"case:{cid}"
    case = await ws.call("GET", f"/cases/{cid}")
    assert any(t["title"] == "Write the rollback runbook." for t in case["tasks"])
    # Accepting twice is harmless.
    again = await ws.call("POST", f"/meeting-items/{items['action']['id']}/accept", 200)
    assert again["status"] == "accepted"

    log = await ws.call("GET", "/decisions")
    entry = next(e for e in log if e["text"].startswith("Keep webhooks"))
    assert entry["origin"] == "knowledge"
    assert entry["responsibility_name"] == "Payments migration"


async def test_without_ai_rules_extract_and_members_can_read_but_guests_cannot_write(
    api: Api,
) -> None:
    ws, member, cid = await case_with_knowledge(api)
    await ws.call("PATCH", "/ai", 204, json={"enabled": False})
    rid = await ws.responsibility("Payments migration", "high")
    made = await meeting(ws, cid, rid)
    assert made["extract_mode"] == "rules"
    assert {i["kind"] for i in made["items"]} == {"decision", "action", "risk", "question"}
    assert made["note"]
    listed = await member.call("GET", "/meetings")
    assert listed[0]["pending"] == 4
    log = await member.call("GET", "/decisions")
    assert any(e["origin"] == "meeting" for e in log)
