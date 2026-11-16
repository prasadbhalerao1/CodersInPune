"""Ask Relay: a question about the whole workspace, answered from records the asker can see.

Retrieval reuses workspace search (which already applies each record's permissions) once
per keyword of the question, ranks records by how many keywords they match, and gives the
best ones to the model as evidence. The answer streams as it is written; the final event
keeps only citations of evidence that was actually given, and an answer citing nothing is
shown as "not in the evidence". With AI unavailable, the ranked records are the answer.
"""

import json
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, or_, select

from relay.audit import service as audit
from relay.catalog.knowledge import readable as knowledge_readable
from relay.catalog.models import KnowledgeItem, OwnershipAssignment, Responsibility
from relay.config import Settings
from relay.directory.models import Person, Team
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import instant
from relay.intelligence.evidence import Pool, PoolItem
from relay.intelligence.llm import LLMError, LLMResult
from relay.intelligence.models import Meeting, MeetingItem
from relay.policy.permissions import Permission, authorize, visible
from relay.search import service as search
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError
from relay.shared.text import like_pattern

NAME = "workspace_answer"
MAX_SOURCES = 12
ANSWER_FORMAT = (
    "Write plain prose: short paragraphs, or lines starting with '- ' for lists. Put the refs "
    "that support a sentence right after it in square brackets, like [E3] or [E2, E5]. If the "
    "evidence does not answer the question, start with 'NOT_FOUND:' and say what is missing."
)
_STOP_WORDS = (
    "a an and are as at be by can could did do does for from has have how i in is it its me "
    "my of on or our should so that the their them there these they this to was we were "
    "what when where which who whom why will with would you your about any all tell show "
    "give list know need please"
)
_STOP = frozenset(_STOP_WORDS.split())
_REFS = re.compile(r"\[((?:E\d+)(?:\s*,\s*E\d+)*)\]")
_NOT_FOUND = re.compile(r"^\s*NOT_FOUND\s*:?\s*", re.I)

Reopen = Callable[[], AbstractAsyncContextManager[WorkspaceAccess]]


class AskWorkspaceIn(StrictInput):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class Source(BaseModel):
    ref: str
    kind: str
    id: str
    title: str
    detail: str | None
    url: str | None


class AskAnswer(BaseModel):
    mode: Literal["ai", "search", "not_found"]
    answer: str
    cited: list[str]
    note: str | None = None


def keywords(question: str) -> list[str]:
    words = [w for w in re.findall(r"[\w'-]{2,}", question.lower()) if w not in _STOP]
    seen: list[str] = []
    for w in words:
        if w not in seen:
            seen.append(w)
    return seen[:6]


async def retrieve(access: WorkspaceAccess, question: str) -> list[Source]:
    """The records that best match the question's keywords, best first."""
    scores: dict[tuple[str, str, str], int] = {}  # (kind, id, title)
    hits: dict[tuple[str, str, str], search.SearchHit] = {}
    terms = keywords(question)
    # The whole question first (exact phrases rank highest), then each keyword.
    for i, term in enumerate([" ".join(terms), *terms] if len(terms) > 1 else terms):
        view = await search.search(access, term, full=True)
        for h in view.hits:
            # Knowledge hits carry their responsibility's id, so the title tells them apart.
            key: tuple[str, str, str] = (h.kind, h.id, h.title)
            hits.setdefault(key, h)
            scores[key] = scores.get(key, 0) + (3 if i == 0 and len(terms) > 1 else 1)
    for item, meeting in await _meeting_items(access, terms):
        key = ("meeting", str(meeting.id), item.text)
        hits[key] = search.SearchHit(
            kind="knowledge",  # placeholder kind for typing; replaced below
            id=str(meeting.id),
            title=item.text[:200],
            detail=f"{item.kind.capitalize()} in the meeting “{meeting.title}” "
            f"({meeting.held_at:%d %b %Y}), {item.status}",
        )
        scores[key] = sum(t in item.text.lower() for t in terms)
    ranked = sorted(hits, key=lambda k: -scores[k])[:MAX_SOURCES]
    owners = await _owners(
        access, [uuid.UUID(hits[k].id) for k in ranked if hits[k].kind == "responsibility"]
    )
    bodies = await _knowledge_bodies(
        access, [uuid.UUID(hits[k].id) for k in ranked if hits[k].kind == "knowledge"]
    )
    return [
        Source(
            ref=f"E{n}",
            kind=k[0],
            id=hits[k].id,
            title=hits[k].title,
            detail=bodies.get((hits[k].id, hits[k].title))
            or owners.get(hits[k].id if hits[k].kind == "responsibility" else "")
            or hits[k].detail,
            url=hits[k].url,
        )
        for n, k in enumerate(ranked, start=1)
    ]


async def _meeting_items(
    access: WorkspaceAccess, terms: list[str]
) -> list[tuple[MeetingItem, Meeting]]:
    """Decisions, actions, questions and risks from meetings that mention a keyword."""
    if not terms:
        return []
    rows = await access.session.execute(
        select(MeetingItem, Meeting)
        .join(Meeting, Meeting.id == MeetingItem.meeting_id)
        .where(
            visible(access, Permission.AI_READ, MeetingItem.tenant_id),
            MeetingItem.status != "dismissed",
            or_(*(MeetingItem.text.ilike(like_pattern(t), escape="\\") for t in terms)),
        )
        .order_by(Meeting.held_at.desc())
        .limit(8)
    )
    return [(i, m) for i, m in rows.all()]


async def _owners(access: WorkspaceAccess, ids: list[uuid.UUID]) -> dict[str, str]:
    """Who holds each responsibility today, so "who is the backup for X?" is answerable."""
    if not ids:
        return {}
    now = datetime.now(UTC)
    rows = await access.session.execute(
        select(
            Responsibility.id,
            Responsibility.criticality,
            Responsibility.description,
            OwnershipAssignment.role,
            func.coalesce(Person.display_name, Team.name),
        )
        .join(OwnershipAssignment, OwnershipAssignment.responsibility_id == Responsibility.id)
        .outerjoin(Person, Person.id == OwnershipAssignment.person_id)
        .outerjoin(Team, Team.id == OwnershipAssignment.team_id)
        .where(
            Responsibility.id.in_(ids),
            visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
            OwnershipAssignment.valid_from <= now,
            or_(OwnershipAssignment.valid_to.is_(None), OwnershipAssignment.valid_to > now),
        )
    )
    holders: dict[str, list[str]] = {}
    about: dict[str, str] = {}
    for rid, criticality, description, role, name in rows.all():
        holders.setdefault(str(rid), []).append(f"{role} {name}")
        about[str(rid)] = f"Criticality {criticality}. {description or ''}".strip()
    return {
        rid: f"{about[rid]} Current holders: {', '.join(names)}." for rid, names in holders.items()
    }


async def _knowledge_bodies(
    access: WorkspaceAccess, responsibility_ids: list[uuid.UUID]
) -> dict[tuple[str, str], str]:
    """Knowledge bodies by (responsibility id, title), the way search identifies them."""
    if not responsibility_ids:
        return {}
    rows = await access.session.execute(
        select(KnowledgeItem.responsibility_id, KnowledgeItem.title, KnowledgeItem.body).where(
            KnowledgeItem.responsibility_id.in_(responsibility_ids),
            KnowledgeItem.status == "active",
            knowledge_readable(access),
        )
    )
    return {(str(r), t): b[:1200] for r, t, b in rows.all() if b}


def _pool(sources: list[Source]) -> Pool:
    items = [
        PoolItem(
            ref=s.ref,
            source_system="relay",
            source_type=s.kind,
            source_id=s.id,
            title=s.title,
            excerpt=(s.detail or "")[:1200],
            url=s.url,
        )
        for s in sources
    ]
    return Pool(uuid.UUID(int=0), "Workspace question", items, [])


def finalise(text: str, sources: list[Source]) -> AskAnswer:
    """Keep only citations of given evidence; an answer citing nothing is not an answer."""
    given = {s.ref for s in sources}
    body = text.replace("**", "").strip()
    if _NOT_FOUND.match(body):
        return AskAnswer(mode="not_found", answer=_NOT_FOUND.sub("", body)[:2000], cited=[])
    cited: list[str] = []
    for group in _REFS.findall(body):
        for ref in re.split(r"\s*,\s*", group):
            if ref in given and ref not in cited:
                cited.append(ref)
    if not cited:
        return AskAnswer(
            mode="not_found",
            answer="The records found don't support an answer to this question.",
            cited=[],
        )
    # Refs to evidence that wasn't given are removed from the text, never shown as sources.
    clean = _REFS.sub(
        lambda m: (
            "[" + ", ".join(r for r in re.split(r"\s*,\s*", m.group(1)) if r in given) + "]"
            if any(r in given for r in re.split(r"\s*,\s*", m.group(1)))
            else ""
        ),
        body,
    )
    return AskAnswer(mode="ai", answer=clean[:3000], cited=cited)


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


async def ask_stream(
    access: WorkspaceAccess, data: AskWorkspaceIn, settings: Settings, reopen: Reopen
) -> AsyncIterator[str]:
    """Server-sent events: `sources`, then `delta`s, then `final` (an `AskAnswer`)."""
    authorize(access, Permission.AI_READ)
    sources = await retrieve(access, data.question)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="ai.workspace_question",
        actor_user_id=access.user_id,
        target_type="workspace",
        target_id=access.tenant_id,
        details={"sources": len(sources)},
    )
    reason = await instant.unavailable(access, settings, NAME) if sources else None
    return _run(data.question, sources, reason, settings, reopen)


async def _run(
    question: str,
    sources: list[Source],
    reason: str | None,
    settings: Settings,
    reopen: Reopen,
) -> AsyncIterator[str]:
    yield _sse("sources", {"sources": [s.model_dump() for s in sources]})
    if not sources:
        final = AskAnswer(
            mode="not_found",
            answer="Nothing you can see in this workspace matches that question. Try other words.",
            cited=[],
        )
        yield _sse("final", final.model_dump())
        return
    if reason:
        final = AskAnswer(
            mode="search",
            answer="These are the records that best match your question.",
            cited=[s.ref for s in sources[:6]],
            note=instant.reason_text(reason),
        )
        yield _sse("final", final.model_dump())
        return
    pool = _pool(sources)
    result: LLMResult[str] | None = None
    error: str | None = None
    try:
        async for item in instant.stream(
            settings,
            name=NAME,
            pool=pool,
            extra=f"Question: {question}",
            answer_format=ANSWER_FORMAT,
        ):
            if isinstance(item, LLMResult):
                result = item
            else:
                yield _sse("delta", {"text": item})
    except LLMError as failure:
        error = failure.code
    try:
        async with reopen() as access:
            run = instant.start_run(access, name=NAME, pool=pool)
            await access.session.flush()
            instant.settle(run, result, error)
    except ApiError as denied:
        yield _sse("error", {"message": denied.detail})
        return
    if result is None:
        final = AskAnswer(
            mode="search",
            answer="These are the records that best match your question.",
            cited=[s.ref for s in sources[:6]],
            note=instant.reason_text(error or "stream_interrupted"),
        )
    else:
        final = finalise(result.output, sources)
    yield _sse("final", final.model_dump())
