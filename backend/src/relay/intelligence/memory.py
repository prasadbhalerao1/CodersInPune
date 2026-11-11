"""Memory Narrator: an AI reading of a responsibility's timeline, clearly marked inferred.

The model sees the timeline events the caller may see (as cited evidence E1, E2…) and
returns chapters (what happened and why it matters) and links between events. Every
chapter and link must cite events that exist; anything citing an unknown ref, or
nothing, is dropped and counted. The narrative is returned, not stored: the timeline is
always rebuilt from live data, and so is its explanation.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from relay.catalog import timeline
from relay.config import Settings
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import instant
from relay.intelligence.evidence import Pool, PoolItem
from relay.intelligence.validate import split_refs, valid_refs
from relay.policy.permissions import Permission, authorize

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
    state: Literal["ready", "empty", "unavailable"]
    reason: str | None
    overview: str | None
    overview_event_ids: list[str]
    chapters: list[ChapterView]
    links: list[LinkView]
    events_considered: int
    rejected: int  # chapters or links dropped for citing nothing or unknown events
    generated_at: datetime


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

    def result(state: Literal["ready", "empty", "unavailable"], **kw: object) -> NarrativeView:
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
    return result(
        "ready",
        overview=overview[0] if overview else None,
        overview_event_ids=[by_ref[r].source_id for r in overview[1]] if overview else [],
        chapters=chapters,
        links=links,
        rejected=rejected,
    )
