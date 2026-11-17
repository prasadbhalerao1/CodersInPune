"""Ask Relay: the workspace assistant, answering from records the asker can see.

Every question gets a permission-filtered overview of the whole workspace (responsibilities
and their holders, people, open cases, open risks), plus the records that best match it:
workspace search (which applies each record's permissions) run per keyword, ranked by how
many keywords a record matches. The model answers in its own words. Facts about the
workspace must cite the evidence they rest on; small talk and questions about Relay itself
are answered as conversation, citing nothing. The final event keeps only citations of
evidence that was actually given, and a factual answer citing nothing is shown as "not in
the evidence". With AI unavailable, the best-matching records are the answer.
"""

import json
import re
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, suppress
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, or_, select

from relay.audit import service as audit
from relay.catalog import service as catalog
from relay.catalog.knowledge import readable as knowledge_readable
from relay.catalog.models import KnowledgeItem, OwnershipAssignment, Responsibility
from relay.config import Settings
from relay.continuity import service as cases
from relay.directory import service as directory
from relay.directory.models import Person, Team
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import instant
from relay.intelligence.evidence import Pool, PoolItem
from relay.intelligence.llm import LLMError, LLMResult
from relay.intelligence.models import Meeting, MeetingItem
from relay.policy.permissions import Permission, authorize, visible
from relay.risks import service as risks
from relay.search import service as search
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError
from relay.shared.text import like_pattern

NAME = "workspace_answer"
MAX_SOURCES = 12
OVERVIEW_CHARS = 4000  # an overview section is a list, longer than one record's excerpt
HISTORY_TURNS = 6
ANSWER_FORMAT = (
    "Write plain prose: short paragraphs, or lines starting with '- ' for lists. Put the refs "
    "that support a sentence right after it in square brackets, like [E3] or [E2, E5]. If the "
    "evidence does not answer a question about the workspace, start with 'NOT_FOUND:' and say "
    "what is missing. For a greeting, thanks, a question about Relay itself or how to use it, "
    "or a request you must decline, start with 'CHAT:' and cite nothing."
)
# What the assistant may say about Relay itself, without evidence.
ABOUT_RELAY = """About Relay (use this freely when asked what Relay is or how to use it):
Relay is an organisational continuity platform. It records who owns each piece of work
(responsibilities, with a primary owner, backups and a criticality), gathers the evidence
behind it from GitHub, Linear and Notion, finds where knowledge sits with one person, and
runs handovers that end with the new owner accepting the work. Pages: Overview, My Work,
Inbox, Ask Relay (this assistant), Cases (handovers: plan, approve, hand over, complete, with
Handover Autopilot, the interview, handover briefs with the AI Copilot and 30/60/90 plans),
Responsibilities (with Memory Replay: how the work got here), Risks, What-if simulator (what
breaks if someone is away; it changes nothing), People & Teams, Knowledge, Meetings, Decision
log, Expertise map, Assets, Insights, and for admins Members, Integrations, Automations, AI
agents, Import, Audit log, Settings and Learn Relay (guided tours). Ctrl+K searches
everything. AI only drafts and proposes from cited evidence; people decide."""
_STOP_WORDS = (
    "a an and are as at be by can could did do does for from has have how i in is it its me "
    "my of on or our should so that the their them there these they this to was we were "
    "what when where which who whom why will with would you your about any all tell show "
    "give list know need please"
)
_STOP = frozenset(_STOP_WORDS.split())
_REFS = re.compile(r"\[((?:E\d+)(?:\s*,\s*E\d+)*)\]")
_NOT_FOUND = re.compile(r"^\s*NOT_FOUND\s*:?\s*", re.I)
_CHAT = re.compile(r"^\s*CHAT\s*:?\s*", re.I)

Reopen = Callable[[], AbstractAsyncContextManager[WorkspaceAccess]]


class AskTurn(StrictInput):
    """An earlier turn of the conversation, sent back by the browser for context."""

    question: Annotated[str, StringConstraints(max_length=500)]
    answer: Annotated[str, StringConstraints(max_length=3000)]


class AskWorkspaceIn(StrictInput):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    history: list[AskTurn] = Field(default_factory=list, max_length=HISTORY_TURNS)


class Source(BaseModel):
    ref: str
    kind: str
    id: str
    title: str
    detail: str | None
    url: str | None


class AskAnswer(BaseModel):
    mode: Literal["ai", "chat", "search", "not_found"]
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


async def overview(access: WorkspaceAccess) -> list[Source]:
    """The whole workspace in a few lists, each filtered to what the asker may see.

    A section the asker has no permission for is left out.
    """
    sections: list[tuple[str, list[str]]] = []
    with suppress(ApiError):
        duties, _ = await catalog.list_responsibilities(access, limit=60)
        duties = [d for d in duties if not d.restricted]
        holders = await _owners(access, [d.id for d in duties])
        sections.append(
            (
                "Responsibilities and who holds them",
                [
                    f"- {d.name} ({d.criticality}): "
                    + holders.get(str(d.id), "no current holder").split("Current holders: ")[-1]
                    for d in duties
                ],
            )
        )
    with suppress(ApiError):
        people, _ = await directory.list_people(access, limit=60)
        sections.append(
            (
                "People",
                [
                    f"- {p.display_name}"
                    + (f", {p.title}" if p.title else "")
                    + (f" ({p.department_name})" if p.department_name else "")
                    for p in people
                ],
            )
        )
    with suppress(ApiError):
        open_cases, _ = await cases.list_cases(access, status="open", limit=20)
        sections.append(
            (
                "Open continuity cases (handovers)",
                [
                    f"- {c.title}: {c.case_type.replace('_', ' ')}, {c.status}"
                    + (f", about {c.affected_person_name}" if c.affected_person_name else "")
                    + f", {c.open_tasks} open tasks"
                    + (f", due {c.due_at:%d %b %Y}" if c.due_at else "")
                    for c in open_cases
                ],
            )
        )
    with suppress(ApiError):
        found = await risks.compute_risks(access, statuses=risks.ACTIVE)
        sections.append(
            ("Open continuity risks", [f"- {r.severity}: {r.title}" for r in found[:25]])
        )
    return [
        Source(
            ref="",
            kind="overview",
            id=str(access.tenant_id),
            title=title,
            detail="\n".join(lines)[:OVERVIEW_CHARS] if lines else "None.",
            url=None,
        )
        for title, lines in sections
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
            excerpt=(s.detail or "")[: OVERVIEW_CHARS if s.kind == "overview" else 1200],
            url=s.url,
        )
        for s in sources
    ]
    return Pool(uuid.UUID(int=0), "Workspace question", items, [])


def finalise(text: str, sources: list[Source]) -> AskAnswer:
    """Keep only citations of given evidence; an answer citing nothing is not an answer."""
    given = {s.ref for s in sources}
    body = text.replace("**", "").strip()
    if _CHAT.match(body):
        # Conversation, not a claim about the workspace: refs mean nothing here.
        chat = re.sub(r"\s*" + _REFS.pattern, "", _CHAT.sub("", body)).strip()
        return AskAnswer(mode="chat", answer=chat[:3000], cited=[])
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
    # A follow-up ("and his backup?") is searched together with the question before it.
    previous = data.history[-1].question if data.history else ""
    sources = await retrieve(access, f"{data.question} {previous}".strip())
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="ai.workspace_question",
        actor_user_id=access.user_id,
        target_type="workspace",
        target_id=access.tenant_id,
        details={"sources": len(sources)},
    )
    reason = await instant.unavailable(access, settings, NAME)
    if reason is None:
        # The model sees the whole workspace first, then the closest records.
        sources = _numbered([*await overview(access), *sources])
    return _run(data.question, data.history, sources, reason, settings, reopen)


def _numbered(sources: list[Source]) -> list[Source]:
    return [s.model_copy(update={"ref": f"E{n}"}) for n, s in enumerate(sources, start=1)]


def _conversation(question: str, history: list[AskTurn]) -> str:
    earlier = "".join(f"\nUser: {t.question}\nRelay: {t.answer[:600]}" for t in history)
    context = (
        f"Conversation so far (the user's earlier turns; context only, not evidence):{earlier}\n\n"
        if earlier
        else ""
    )
    return f"{ABOUT_RELAY}\n\n{context}Question: {question}"


async def _run(
    question: str,
    history: list[AskTurn],
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
            extra=_conversation(question, history),
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
        matches = [s.ref for s in sources if s.kind != "overview"][:6]
        final = AskAnswer(
            mode="search" if matches else "not_found",
            answer="These are the records that best match your question."
            if matches
            else "The answer could not be written just now. Try again.",
            cited=matches,
            note=instant.reason_text(error or "stream_interrupted"),
        )
    else:
        final = finalise(result.output, sources)
    yield _sse("final", final.model_dump())
