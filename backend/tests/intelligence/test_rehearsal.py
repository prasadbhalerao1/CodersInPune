"""Handover rehearsal: drills from the brief's evidence, graded by rules against it."""

from collections.abc import AsyncIterator

import pytest

from tests.api import Api, make_api
from tests.intelligence.test_analysis import Script, script
from tests.intelligence.test_copilot import handover

pytestmark = pytest.mark.anyio
__all__ = ["script"]  # fixture re-export


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(llm_providers="fake") as a:
        yield a


async def test_drills_come_from_visible_evidence_and_grade_against_it(
    api: Api, script: list[Script]
) -> None:
    _ws, member, capsule = await handover(api)
    drills = (await member.call("GET", f"/ai/capsules/{capsule}/rehearsal"))["drills"]
    titles = [d["source_title"] for d in drills]
    assert "Rotate the webhook secret" in titles
    assert "Vault recovery" not in titles  # managers-only evidence never becomes a drill
    drill = next(d for d in drills if d["source_title"] == "Rotate the webhook secret")

    good = await member.call(
        "POST",
        f"/ai/capsules/{capsule}/rehearsal",
        200,
        json={
            "drill_id": drill["id"],
            "answer": "Open the dashboard and rotate the webhook secret.",
        },
    )
    assert good["verdict"] == "ready"
    assert good["score"] >= 70
    assert not good["missed"]

    weak = await member.call(
        "POST",
        f"/ai/capsules/{capsule}/rehearsal",
        200,
        json={"drill_id": drill["id"], "answer": "I would ask someone."},
    )
    assert weak["verdict"] == "not_yet"
    assert "dashboard" in weak["missed"]
    assert weak["source_excerpt"]  # what to re-read

    await member.call(
        "POST",
        f"/ai/capsules/{capsule}/rehearsal",
        404,
        json={"drill_id": "0" * 16, "answer": "anything"},
    )


async def test_editors_can_preview_a_brief_as_a_member_sees_it(
    api: Api, script: list[Script]
) -> None:
    ws, member, capsule = await handover(api)
    full = await ws.call("GET", f"/ai/capsules/{capsule}")
    preview = await ws.call("GET", f"/ai/capsules/{capsule}?as_member=true")
    assert (full["preview_as_member"], preview["preview_as_member"]) == (False, True)
    count = lambda v: sum(len(s["points"]) for s in v["sections"])  # noqa: E731
    assert count(preview) <= count(full)
    assert "Vault recovery" not in str(preview)  # managers-only evidence stays out
    # A member asking for a preview just gets their own view; the flag only narrows.
    own = await member.call("GET", f"/ai/capsules/{capsule}?as_member=true")
    assert own["preview_as_member"] is False
