"""Memory Narrator: an AI reading of a responsibility's timeline, clearly marked inferred.

The model sees the timeline events the caller may see (as cited evidence E1, E2…) and
returns chapters (what happened and why it matters) and links between events. Every
chapter and link must cite events that exist; anything citing an unknown ref, or
nothing, is dropped and counted. The narrative is returned, not stored: the timeline is
always rebuilt from live data, and so is its explanation.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select

from relay.audit import service as audit
from relay.catalog import timeline
from relay.config import Settings
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import copilot, instant
from relay.intelligence.evidence import Pool, PoolItem
from relay.intelligence.models import AgentRun
from relay.intelligence.validate import split_refs, valid_refs
from relay.policy.permissions import Permission, authorize
from relay.shared.api_types import StrictInput

NAME = "memory_narrator"
MAX_EVENTS = 120  # most recent events sent to the model
MAX_CHAPTERS, MAX_LINKS = 8, 20


class MemoryChapter(BaseModel):
    title: str = Field(max_length=160)
    summary: str = Field(max_length=1200, description="What happened, citing events.")
    why_it_matters: str = Field(default="", max_length=600)
    events: list[str] = Field(default_factory=list, description="Event refs like E3.")
    confidence: Literal["high", "medium", "low"] = "medium"


class MemoryLink(BaseModel):
    source: str = Field(description="Ref of the earlier event.")
    target: str = Field(description="Ref of the later event.")
    relation: str = Field(max_length=200, description="How they relate, in a few words.")


class MemoryOutput(BaseModel):
    overview: str = Field(default="", max_length=1200)
    overview_events: list[str] = Field(default_factory=list)
    chapters: list[MemoryChapter] = Field(default_factory=list)
    links: list[MemoryLink] = Field(default_factory=list)


class ChapterView(BaseModel):
    title: str
    summary: str
    why_it_matters: str
    confidence: str
    uncertainty_level: Literal["inferred"] = "inferred"
    event_ids: list[str]
    started_at: datetime
    ended_at: datetime


class LinkView(BaseModel):
    from_event: str
    to_event: str
    relation: str
    uncertainty_level: Literal["inferred"] = "inferred"


class NarrativeView(BaseModel):
    responsibility_id: uuid.UUID
    # none: never generated; empty: nothing to explain; unavailable: the model couldn't answer
    state: Literal["ready", "empty", "unavailable", "none"]
    reason: str | None
    overview: str | None
    overview_event_ids: list[str]
    chapters: list[ChapterView]
    links: list[LinkView]
    events_considered: int
    rejected: int  # chapters or links dropped for citing nothing or unknown events
    generated_at: datetime
    # New events since it was written: the reading may be incomplete. Regenerate to refresh.
    outdated: bool = False
    withheld: int = 0  # chapters citing events this viewer can't see, left out


class HistoryQuestionIn(StrictInput):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class HistoryAnswer(BaseModel):
    question: str
    answer: str
    mode: Literal["ai", "search", "not_found"]
    confidence: str | None
    note: str | None
    event_ids: list[str]


def _pool(rid: uuid.UUID, name: str, events: list[timeline.TimelineEvent]) -> Pool:
    items = [
        PoolItem(
            ref=f"E{n}",
            source_system=e.source_system.lower(),
            source_type=e.category,
            source_id=e.id,
            title=e.title,
            excerpt=f"{e.occurred_at.date().isoformat()} [{e.category}, {e.significance}] "
            f"{e.title}. {e.summary}",
            url=e.source_url,
            source_ts=e.occurred_at,
        )
        for n, e in enumerate(reversed(events), start=1)  # oldest first reads as a story
    ]
    return Pool(rid, f"History of {name}", items, [])


async def narrate(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, settings: Settings
) -> NarrativeView:
    authorize(access, Permission.AI_READ)
    view = await timeline.responsibility_timeline(access, responsibility_id, limit=MAX_EVENTS)
    now = datetime.now(UTC)

    def result(
        state: Literal["ready", "empty", "unavailable", "none"], **kw: object
    ) -> NarrativeView:
        base: dict[str, object] = {
            "responsibility_id": responsibility_id,
            "state": state,
            "reason": None,
            "overview": None,
            "overview_event_ids": [],
            "chapters": [],
            "links": [],
            "events_considered": len(view.events),
            "rejected": 0,
            "generated_at": now,
        }
        return NarrativeView.model_validate({**base, **kw})

    if not view.events:
        return result("empty", reason="There are no events to explain yet.")
    pool = _pool(responsibility_id, view.responsibility_name, view.events)
    outcome = await instant.call(
        access,
        settings,
        name=NAME,
        pool=pool,
        extra=f"Responsibility: {view.responsibility_name}. Events are oldest first.",
        output_type=MemoryOutput,
        checkpoint={"responsibility_id": str(responsibility_id)},
    )
    if outcome.output is None:
        return result("unavailable", reason=outcome.message)
    out = outcome.output
    by_ref = {i.ref: i for i in pool.items}
    rejected = 0

    def refs_of(text: str, refs: list[str]) -> tuple[str, list[str]] | None:
        clean, inline = split_refs(text)
        valid = valid_refs(pool, [*refs, *inline])
        return None if not valid else (clean, valid)

    chapters = []
    for c in out.chapters[:MAX_CHAPTERS]:
        cited = refs_of(c.summary, c.events)
        if cited is None:
            rejected += 1
            continue
        summary, refs = cited
        when = [by_ref[r].source_ts for r in refs if by_ref[r].source_ts]
        chapters.append(
            ChapterView(
                title=" ".join(c.title.split()),
                summary=summary,
                why_it_matters=split_refs(c.why_it_matters)[0],
                confidence=c.confidence,
                event_ids=[by_ref[r].source_id for r in refs],
                started_at=min(when),  # type: ignore[type-var]
                ended_at=max(when),  # type: ignore[type-var]
            )
        )
    links = []
    for link in out.links[:MAX_LINKS]:
        pair = valid_refs(pool, [link.source, link.target])
        if not pair or len(pair) != 2:
            rejected += 1
            continue
        links.append(
            LinkView(
                from_event=by_ref[pair[0]].source_id,
                to_event=by_ref[pair[1]].source_id,
                relation=" ".join(link.relation.split()),
            )
        )
    overview = refs_of(out.overview, out.overview_events) if out.overview.strip() else None
    narrative = result(
        "ready",
        overview=overview[0] if overview else None,
        overview_event_ids=[by_ref[r].source_id for r in overview[1]] if overview else [],
        chapters=chapters,
        links=links,
        rejected=rejected,
    )
    # Persist the validated reading with the events it saw, so the page opens without a
    # model call and can tell when the history has moved on.
    run = await access.session.get(AgentRun, outcome.run_id)
    if run is not None:
        run.checkpoint = {
            **run.checkpoint,
            "narrative": narrative.model_dump(mode="json"),
            "event_ids": [e.id for e in view.events],
        }
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="ai.memory_generated",
        actor_user_id=access.user_id,
        target_type="responsibility",
        target_id=responsibility_id,
        details={"run_id": str(outcome.run_id), "chapters": len(chapters)},
    )
    await access.session.flush()
    return narrative


async def latest(access: WorkspaceAccess, responsibility_id: uuid.UUID) -> NarrativeView:
    """The last stored reading, as this viewer may see it now."""
    authorize(access, Permission.AI_READ)
    view = await timeline.responsibility_timeline(access, responsibility_id, limit=MAX_EVENTS)
    visible = {e.id for e in view.events}
    run = await access.session.scalar(
        select(AgentRun)
        .where(
            AgentRun.capability == NAME,
            AgentRun.state == "completed",
            AgentRun.checkpoint["responsibility_id"].astext == str(responsibility_id),
            AgentRun.checkpoint.has_key("narrative"),
        )
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    if run is None:
        return NarrativeView(
            responsibility_id=responsibility_id,
            state="none",
            reason=None,
            overview=None,
            overview_event_ids=[],
            chapters=[],
            links=[],
            events_considered=len(view.events),
            rejected=0,
            generated_at=datetime.now(UTC),
        )
    stored = NarrativeView.model_validate(run.checkpoint["narrative"])
    # Chapters and links are shown only if every event they cite is visible to this viewer.
    chapters = [c for c in stored.chapters if set(c.event_ids) <= visible]
    links = [link for link in stored.links if {link.from_event, link.to_event} <= visible]
    overview_ok = set(stored.overview_event_ids) <= visible
    seen = set(run.checkpoint.get("event_ids", []))
    return stored.model_copy(
        update={
            "chapters": chapters,
            "links": links,
            "overview": stored.overview if overview_ok else None,
            "overview_event_ids": stored.overview_event_ids if overview_ok else [],
            "withheld": len(stored.chapters) - len(chapters),
            "outdated": bool(visible - seen),
        }
    )


async def ask(
    access: WorkspaceAccess,
    responsibility_id: uuid.UUID,
    data: HistoryQuestionIn,
    settings: Settings,
) -> HistoryAnswer:
    """Answer a question about this history from its events only, citing them."""
    authorize(access, Permission.AI_READ)
    view = await timeline.responsibility_timeline(access, responsibility_id, limit=MAX_EVENTS)
    pool = _pool(responsibility_id, view.responsibility_name, view.events)
    by_ref = {i.ref: i for i in pool.items}
    refs = copilot.search(pool, data.question)
    mode: Literal["ai", "search", "not_found"] = "not_found"
    answer, confidence, note = copilot.NOT_FOUND_HISTORY, None, None
    if pool.items:
        outcome = await instant.call(
            access,
            settings,
            name=copilot.NAME,
            pool=pool,
            extra=f"Question about the history of {view.responsibility_name}: {data.question}",
            output_type=copilot.CopilotOutput,
            checkpoint={"responsibility_id": str(responsibility_id), "kind": "history_question"},
        )
        if outcome.output is None:
            note = outcome.message
            if refs:
                mode, answer = "search", "These events mention what you asked about."
        else:
            text, inline = split_refs(outcome.output.answer)
            cited = valid_refs(pool, [*outcome.output.evidence, *inline])
            if outcome.output.found and cited and text:
                mode, answer, refs, confidence = "ai", text, cited, outcome.output.confidence
    return HistoryAnswer(
        question=data.question,
        answer=answer,
        mode=mode,
        confidence=confidence,
        note=note,
        event_ids=[by_ref[r].source_id for r in refs],
    )
