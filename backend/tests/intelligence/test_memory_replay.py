"""Project Memory Replay: a factual timeline from live data, and an inferred narrative."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from relay.integrations.github.models import GitHubInstallation, GitHubRepository, GitHubWorkItem
from relay.integrations.linear.models import LinearConnection, LinearIssue, LinearProject
from relay.shared.db import unit_of_work
from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.intelligence.test_analysis import Script, script
from tests.test_simulation import statements

pytestmark = pytest.mark.anyio
__all__ = ["script"]  # fixture re-export

NOW = datetime.now(UTC)


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(llm_providers="fake") as a:
        yield a


async def history(api: Api) -> tuple[Ws, str]:
    """A deploy pipeline with a year of pull requests, issues, a decision and an owner."""
    ws = Ws(api, await api.create_workspace(OWNER, "Acme"))
    rid = await ws.responsibility("Production deployments", "critical")
    arjun = await ws.person("Arjun")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "person_id": arjun},
    )
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={
            "kind": "adr",
            "title": "Canary every deploy",
            "body": "All deploys go through a 30 minute canary.",
            "decision_rationale": "A bad deploy took checkout down in March.",
        },
    )
    user = (await ws_user(api, ws)).hex
    async with unit_of_work(api.app.state.session_factory, ws.id, OWNER) as s:
        inst = GitHubInstallation(
            id=uuid.uuid7(),
            tenant_id=ws.id,
            installation_id=4242,
            account_login="acme",
            account_type="Organization",
            connected_by=uuid.UUID(user),
        )
        s.add(inst)
        await s.flush()
        for name, audience, rid_ in (
            ("acme/deploy", "workspace", rid),
            ("acme/secret", "managers", rid),
        ):
            s.add(
                GitHubRepository(
                    id=uuid.uuid7(),
                    tenant_id=ws.id,
                    installation_ref=inst.id,
                    github_repo_id=abs(hash(name)) % 10**9,
                    full_name=name,
                    html_url=f"https://github.com/{name}",
                    private=True,
                    archived=False,
                    audience=audience,
                    responsibility_id=rid_,
                )
            )
        await s.flush()
        repos = {r.full_name: r.id for r in await s.scalars(_repos())}
        items: list[tuple[str, str, int, str, list[str], str, int]] = [
            # repo, kind, number, title, labels, state, days ago
            (
                "acme/deploy",
                "issue",
                3,
                "Deploys time out after 10 minutes",
                ["bug"],
                "closed",
                200,
            ),
            (
                "acme/deploy",
                "pull_request",
                4,
                "Raise deploy timeout (fixes #3)",
                [],
                "merged",
                199,
            ),
            ("acme/deploy", "pull_request", 7, "Add canary stage", ["feature"], "merged", 120),
            ("acme/deploy", "pull_request", 9, "Postmortem: checkout outage", [], "merged", 90),
            ("acme/deploy", "pull_request", 11, "Upgrade runner image", [], "open", 2),
            ("acme/secret", "pull_request", 1, "Rotate signing key", [], "merged", 30),
        ]
        for repo, kind, number, title, labels, state, days in items:
            at = NOW - timedelta(days=days)
            s.add(
                GitHubWorkItem(
                    tenant_id=ws.id,
                    repository_id=repos[repo],
                    kind=kind,
                    number=number,
                    github_id=number * 1000 + len(repo),
                    title=title,
                    state=state,
                    author_login="arjun-gh",
                    labels=labels,
                    html_url=f"https://github.com/{repo}/pull/{number}",
                    gh_created_at=at - timedelta(days=1),
                    gh_updated_at=at,
                    closed_at=at if state != "open" else None,
                    merged_at=at if state == "merged" else None,
                )
            )
        linear = LinearConnection(
            id=uuid.uuid7(),
            tenant_id=ws.id,
            organization_id="org",
            organization_name="Acme",
            connected_by=uuid.UUID(user),
        )
        s.add(linear)
        await s.flush()
        s.add(
            LinearProject(
                tenant_id=ws.id,
                connection_ref=linear.id,
                linear_id="proj-1",
                name="Deploy reliability",
                url="https://linear.app/acme/project/proj-1",
                responsibility_id=rid,
                audience="workspace",
            )
        )
        s.add(
            LinearIssue(
                tenant_id=ws.id,
                connection_ref=linear.id,
                linear_id="iss-1",
                identifier="OPS-12",
                title="Document rollback for acme/deploy",
                state_type="completed",
                project_linear_id="proj-1",
                labels=["documentation"],
                url="https://linear.app/acme/issue/OPS-12",
                li_created_at=NOW - timedelta(days=70),
                li_updated_at=NOW - timedelta(days=60),
                completed_at=NOW - timedelta(days=60),
            )
        )
    return ws, rid


async def ws_user(api: Api, ws: Ws) -> uuid.UUID:
    me = await ws.call("GET", "/members")
    return uuid.UUID(next(m["user_id"] for m in me if m["role"] == "owner"))


def _repos() -> Any:
    from sqlalchemy import select

    return select(GitHubRepository)


async def test_timeline_is_factual_ordered_and_categorised(api: Api) -> None:
    ws, rid = await history(api)
    view = await ws.call("GET", f"/responsibilities/{rid}/timeline")
    events = view["events"]
    assert events, "timeline is empty"
    times = [e["occurred_at"] for e in events]
    assert times == sorted(times, reverse=True)
    assert {e["uncertainty_level"] for e in events} == {"factual"}
    by_title = {e["title"]: e for e in events}
    assert by_title["Add canary stage"]["category"] == "implementation"
    assert by_title["Add canary stage"]["significance"] == "high"  # merged
    assert (by_title["Deploys time out after 10 minutes"]["category"], "label") == (
        "bug_fix",
        by_title["Deploys time out after 10 minutes"]["category_basis"],
    )
    assert by_title["Postmortem: checkout outage"]["category"] == "incident"
    assert by_title["Upgrade runner image"]["category"] == "technical_change"
    assert by_title["Canary every deploy"]["category"] == "decision"
    assert "Why: A bad deploy" in by_title["Canary every deploy"]["summary"]
    assert by_title["Arjun became primary owner"]["category"] == "ownership_change"
    assert by_title["OPS-12 Document rollback for acme/deploy"]["source_system"] == "Linear"
    assert view["sources"]


async def test_category_filter_returns_only_that_category(api: Api) -> None:
    ws, rid = await history(api)
    view = await ws.call("GET", f"/responsibilities/{rid}/timeline?category=bug_fix")
    assert view["events"]
    assert {e["category"] for e in view["events"]} == {"bug_fix"}
    assert view["counts"]["implementation"] >= 1  # counts ignore the filter
    await ws.call("GET", f"/responsibilities/{rid}/timeline?category=gossip", 422)
    limited = await ws.call("GET", f"/responsibilities/{rid}/timeline?limit=2")
    assert len(limited["events"]) == 2
    assert limited["truncated"]


async def test_references_in_titles_link_events(api: Api) -> None:
    ws, rid = await history(api)
    events = {
        e["id"]: e for e in (await ws.call("GET", f"/responsibilities/{rid}/timeline"))["events"]
    }
    assert "gh:acme/deploy#3" in events["gh:acme/deploy#4"]["linked_events"]
    assert "gh:acme/deploy#4" in events["gh:acme/deploy#3"]["linked_events"]


async def test_members_see_only_workspace_audience_sources(api: Api) -> None:
    ws, rid = await history(api)
    titles = {
        e["title"] for e in (await ws.call("GET", f"/responsibilities/{rid}/timeline"))["events"]
    }
    assert "Rotate signing key" in titles  # managers see the managers-only repository
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    seen = {
        e["title"]
        for e in (await member.call("GET", f"/responsibilities/{rid}/timeline"))["events"]
    }
    assert "Rotate signing key" not in seen
    assert "Add canary stage" in seen


async def test_outsiders_cannot_read_a_timeline(api: Api) -> None:
    ws, rid = await history(api)
    response = await api.client.get(
        f"/workspaces/{ws.id}/responsibilities/{rid}/timeline", headers=api.as_user("user_stranger")
    )
    assert response.status_code in (403, 404)
    other = Ws(api, await api.create_workspace("user_other", "Other"), "user_other")
    await other.call("GET", f"/responsibilities/{rid}/timeline", 404)


async def test_timeline_reads_without_writing(api: Api) -> None:
    ws, rid = await history(api)
    with statements() as seen:
        await ws.call("GET", f"/responsibilities/{rid}/timeline")
    assert not [s for s in seen if s.startswith(("INSERT", "UPDATE", "DELETE"))]


async def test_narrative_cites_events_and_drops_invented_ones(
    api: Api, script: list[Script]
) -> None:
    ws, rid = await history(api)

    def narrator(refs: dict[str, str]) -> dict[str, Any]:
        canary = next(r for r, t in refs.items() if t == "Add canary stage")
        outage = next(r for r, t in refs.items() if t == "Postmortem: checkout outage")
        return {
            "overview": "The pipeline gained a canary after an outage.",
            "overview_events": [canary],
            "chapters": [
                {
                    "title": "Safer releases",
                    "summary": "A canary stage was added [" + canary + "].",
                    "why_it_matters": "Bad deploys are caught early.",
                    "events": [outage],
                    "confidence": "medium",
                },
                {"title": "Invented", "summary": "Never happened.", "events": ["E999"]},
                {"title": "Uncited", "summary": "No refs at all.", "events": []},
            ],
            "links": [
                {"source": outage, "target": canary, "relation": "outage led to the canary"},
                {"source": canary, "target": "E404", "relation": "made up"},
            ],
        }

    script.append(narrator)
    view = await ws.call("POST", f"/responsibilities/{rid}/timeline/narrative")
    assert view["state"] == "ready"
    assert [c["title"] for c in view["chapters"]] == ["Safer releases"]
    chapter = view["chapters"][0]
    assert chapter["uncertainty_level"] == "inferred"
    assert set(chapter["event_ids"]) == {"gh:acme/deploy#7", "gh:acme/deploy#9"}
    assert "[" not in chapter["summary"]
    assert view["links"] == [
        {
            "from_event": "gh:acme/deploy#9",
            "to_event": "gh:acme/deploy#7",
            "relation": "outage led to the canary",
            "uncertainty_level": "inferred",
        }
    ]
    assert view["rejected"] == 3
    runs = await ws.call("GET", "/ai/runs")
    assert runs[0]["capability"] == "memory_narrator"
    assert runs[0]["state"] == "completed"


async def test_narrative_without_ai_or_events_says_why(api: Api) -> None:
    ws, rid = await history(api)
    async with make_api() as no_ai:
        plain = Ws(no_ai, await no_ai.create_workspace(OWNER, "Plain"))
        r2 = await plain.responsibility("Empty", "low")
        empty = await plain.call("POST", f"/responsibilities/{r2}/timeline/narrative")
        assert (empty["state"], empty["chapters"]) == ("empty", [])
        await plain.call(
            "POST",
            f"/responsibilities/{r2}/knowledge",
            201,
            json={"kind": "procedure", "title": "Water weekly", "body": "Every Monday."},
        )
        off = await plain.call("POST", f"/responsibilities/{r2}/timeline/narrative")
        assert off["state"] == "unavailable"
        assert off["reason"] == "AI is not configured on this server."
    await ws.call("PATCH", "/ai/capabilities/memory_narrator", 204, json={"enabled": False})
    disabled = await ws.call("POST", f"/responsibilities/{rid}/timeline/narrative")
    assert disabled["state"] == "unavailable"
    assert "switched off" in disabled["reason"]


async def test_narrative_is_stored_filtered_per_viewer_and_marked_outdated(
    api: Api, script: list[Script]
) -> None:
    ws, rid = await history(api)
    none = await ws.call("GET", f"/responsibilities/{rid}/timeline/narrative")
    assert none["state"] == "none"

    def narrator(refs: dict[str, str]) -> dict[str, Any]:
        public = next(r for r, t in refs.items() if t == "Add canary stage")
        secret = next(r for r, t in refs.items() if t == "Rotate signing key")
        return {
            "chapters": [
                {"title": "Canary", "summary": "Canary added.", "events": [public]},
                {"title": "Keys", "summary": "Keys rotated.", "events": [secret]},
            ]
        }

    script.append(narrator)
    made = await ws.call("POST", f"/responsibilities/{rid}/timeline/narrative")
    assert len(made["chapters"]) == 2
    stored = await ws.call("GET", f"/responsibilities/{rid}/timeline/narrative")
    assert [c["title"] for c in stored["chapters"]] == ["Canary", "Keys"]
    assert stored["outdated"] is False

    # A member never sees a chapter built on a managers-only source.
    await add_member(api, ws.id, "user_member", "member")
    member = await Ws(api, ws.id, "user_member").call(
        "GET", f"/responsibilities/{rid}/timeline/narrative"
    )
    assert [c["title"] for c in member["chapters"]] == ["Canary"]
    assert member["withheld"] == 1

    # New history after the reading: it says so instead of pretending to be complete.
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/knowledge",
        201,
        json={"kind": "procedure", "title": "Rollback", "body": "Use the one-click rollback."},
    )
    later = await ws.call("GET", f"/responsibilities/{rid}/timeline/narrative")
    assert later["outdated"] is True
    runs = await ws.call("GET", "/ai/runs")
    assert any(r["capability"] == "memory_narrator" for r in runs)


async def test_history_questions_cite_events_or_say_not_found(
    api: Api, script: list[Script]
) -> None:
    ws, rid = await history(api)
    script.append(
        lambda refs: {
            "found": True,
            "answer": "Because of the checkout outage.",
            "evidence": [next(r for r, t in refs.items() if t == "Postmortem: checkout outage")],
        }
    )
    why = await ws.call(
        "POST",
        f"/responsibilities/{rid}/timeline/questions",
        json={"question": "Why was the canary stage added?"},
    )
    assert why["mode"] == "ai"
    assert why["event_ids"] == ["gh:acme/deploy#9"]
    script.append(lambda refs: {"found": True, "answer": "Mars.", "evidence": ["E999"]})
    invented = await ws.call(
        "POST", f"/responsibilities/{rid}/timeline/questions", json={"question": "Where is prod?"}
    )
    assert invented["mode"] == "not_found"
    assert "Mars" not in invented["answer"]
