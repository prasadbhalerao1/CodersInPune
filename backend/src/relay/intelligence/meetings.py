"""Meeting intelligence: a transcript in; decisions, actions, open questions and risks out.

Every item cites the transcript lines it came from, so a reader can check it against what
was said. The model only proposes items (guardrail 9); with AI off or unavailable, rules
over the same lines do the job less thoroughly. Accepting an item is what changes
anything: a decision becomes decision knowledge (ADR) on the meeting's responsibility, an
action becomes a task on its case, assigned to the person named if they are a member.
"""

import re
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Annotated, Literal

import procrastinate
from pydantic import AwareDatetime, BaseModel, Field, StringConstraints
from sqlalchemy import delete, select

from relay.audit import service as audit
from relay.catalog import knowledge
from relay.catalog.models import KnowledgeItem, Responsibility
from relay.config import Settings
from relay.continuity import service as continuity
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import instant
from relay.intelligence.evidence import Pool, PoolItem
from relay.intelligence.models import Claim, Meeting, MeetingItem
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

NAME = "meeting_analyst"
MAX_ITEMS = 40
Kind = Literal["decision", "action", "question", "risk"]


class MeetingIn(StrictInput):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    held_at: AwareDatetime | None = None
    transcript: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60_000)
    ]
    responsibility_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None


class MeetingItemView(BaseModel):
    id: uuid.UUID
    meeting_id: uuid.UUID
    kind: Kind
    text: str
    owner_name: str | None
    due_text: str | None
    lines: list[int]
    source: Literal["ai", "rules"]
    status: Literal["proposed", "accepted", "dismissed"]
    result_ref: str | None


class MeetingSummary(BaseModel):
    id: uuid.UUID
    title: str
    held_at: datetime
    responsibility_id: uuid.UUID | None
    case_id: uuid.UUID | None
    extract_mode: Literal["ai", "rules"] | None
    counts: dict[str, int]
    pending: int


class MeetingDetail(MeetingSummary):
    lines: list[str]
    items: list[MeetingItemView]
    note: str | None = None
    can_review: bool


class _Point(BaseModel):
    kind: Kind
    text: str = Field(max_length=500)
    owner: str | None = None
    due: str | None = None
    lines: list[str] = Field(description="Line refs this item came from, e.g. ['L4', 'L5']")


class MeetingOutput(BaseModel):
    items: list[_Point]


# --- rules (also the fallback when AI is unavailable) ------------------------------------

_SPEAKER = re.compile(r"^\s*(?:\[[^\]]*\]\s*)?([A-Z][\w .'-]{0,40}?)\s*:\s*(.+)$")
_DECISION = re.compile(
    r"\b(decided|decision|we(?:'ll| will) go with|agreed (?:to|that|on)|let'?s go with|"
    r"approved|final call|settled on)\b",
    re.I,
)
_ACTION = re.compile(
    r"(\baction(?: item)?s?:|\btodo\b|\bi'?ll\b|\bi will\b|\bcan you\b|\bplease\b|"
    r"\b\w+ (?:will|to) (?:send|update|write|fix|follow up|own|take|draft|review|set up|"
    r"schedule|share|check|prepare|migrate|rotate|document)\b)",
    re.I,
)
_RISK = re.compile(
    r"\b(risk|risky|blocker|blocked|concern(?:ed)?|worried|single point|bus factor|"
    r"no one else|only (?:he|she|they|\w+) knows?)\b",
    re.I,
)
_DUE = re.compile(
    r"\bby (?:the )?(end of (?:day|week|month)|eod|eow|tomorrow|next week|"
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)day|\d{1,2}(?:st|nd|rd|th)?(?: \w+)?)\b",
    re.I,
)
_OWNER = re.compile(r"\b([A-Z][a-z]+)(?: will| to| can you)\b|@([A-Z][a-z]+)")


def _speaker(line: str) -> tuple[str | None, str]:
    m = _SPEAKER.match(line)
    return (m.group(1).strip(), m.group(2).strip()) if m else (None, line.strip())


def rule_items(lines: list[str]) -> list[_Point]:
    out: list[_Point] = []
    for n, raw in enumerate(lines, start=1):
        who, said = _speaker(raw)
        if len(said) < 8:
            continue
        kind: Kind | None = None
        if _DECISION.search(said):
            kind = "decision"
        elif _ACTION.search(said):
            kind = "action"
        elif _RISK.search(said):
            kind = "risk"
        elif said.rstrip().endswith("?"):
            kind = "question"
        if kind is None:
            continue
        owner = None
        if kind == "action":
            named = _OWNER.search(said)
            if re.search(r"\bi'?ll\b|\bi will\b", said, re.I):
                owner = who
            elif named:
                owner = named.group(1) or named.group(2)
        due = _DUE.search(said) if kind == "action" else None
        out.append(
            _Point(
                kind=kind,
                text=said[:500],
                owner=owner,
                due=due.group(1) if due else None,
                lines=[f"L{n}"],
            )
        )
    return out[:MAX_ITEMS]


# --- service ------------------------------------------------------------------------------


def _lines(transcript: str) -> list[str]:
    return [line.rstrip() for line in transcript.splitlines()][:2000]


def _pool(meeting: Meeting, lines: list[str]) -> Pool:
    items = [
        PoolItem(
            ref=f"L{n}",
            source_system="relay",
            source_type="meeting_line",
            source_id=f"{meeting.id}:{n}",
            title=f"Line {n}",
            excerpt=line[:600],
        )
        for n, line in enumerate(lines, start=1)
        if line.strip()
    ]
    return Pool(meeting.id, meeting.title, items, [])


def _valid(points: list[_Point], lines: list[str]) -> list[tuple[_Point, list[int]]]:
    seen: set[str] = set()
    out = []
    for p in points:
        refs = sorted(
            {
                int(r[1:])
                for r in p.lines
                if re.fullmatch(r"L\d+", r) and 1 <= int(r[1:]) <= len(lines)
            }
        )
        key = re.sub(r"\W+", " ", p.text.lower()).strip()
        if not refs or not key or key in seen:
            continue  # uncited or repeated: dropped, never shown as fact
        seen.add(key)
        out.append((p, refs))
    return out[:MAX_ITEMS]


async def _extract(
    access: WorkspaceAccess, meeting: Meeting, settings: Settings, use_ai: bool = True
) -> str | None:
    """(Re)extract a meeting's proposed items; returns a note when rules stood in for AI."""
    lines = _lines(meeting.transcript)
    pool = _pool(meeting, lines)
    outcome: instant.Outcome[MeetingOutput] = (
        await instant.call(
            access,
            settings,
            name=NAME,
            pool=pool,
            extra=f"Meeting: {meeting.title}, held {meeting.held_at:%d %b %Y}.",
            output_type=MeetingOutput,
            case_id=meeting.case_id,
        )
        if use_ai
        else instant.Outcome(None, None, None)
    )
    points = outcome.output.items if outcome.output else []
    mode = "ai" if outcome.output and points else "rules"
    if mode == "rules":
        points = rule_items(lines)
    await access.session.execute(
        delete(MeetingItem).where(
            MeetingItem.meeting_id == meeting.id, MeetingItem.status == "proposed"
        )
    )
    kept = {
        re.sub(r"\W+", " ", t.lower()).strip()
        for t in await access.session.scalars(
            select(MeetingItem.text).where(MeetingItem.meeting_id == meeting.id)
        )
    }
    for p, refs in _valid(points, lines):
        if re.sub(r"\W+", " ", p.text.lower()).strip() in kept:
            continue  # already reviewed
        access.session.add(
            MeetingItem(
                tenant_id=access.tenant_id,
                meeting_id=meeting.id,
                kind=p.kind,
                text=p.text[:500],
                owner_name=(p.owner or None) and p.owner[:80],
                due_text=(p.due or None) and p.due[:80],
                lines=refs,
                source=mode,
            )
        )
    meeting.extract_mode = mode
    meeting.run_id = outcome.run_id
    await access.session.flush()
    if mode == "rules" and outcome.reason:
        return instant.reason_text(outcome.reason)
    return None


async def create_meeting(
    access: WorkspaceAccess, data: MeetingIn, settings: Settings, *, use_ai: bool = True
) -> MeetingDetail:
    authorize(access, Permission.KNOWLEDGE_WRITE)
    if data.case_id:
        await continuity._load(access, data.case_id)
    meeting = Meeting(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        title=data.title,
        held_at=data.held_at or datetime.now(UTC),
        transcript=data.transcript,
        responsibility_id=data.responsibility_id,
        case_id=data.case_id,
        created_by=access.user_id,
    )
    access.session.add(meeting)
    await access.session.flush()
    note = await _extract(access, meeting, settings, use_ai)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="meeting.created",
        actor_user_id=access.user_id,
        target_type="meeting",
        target_id=meeting.id,
        details={"mode": meeting.extract_mode},
    )
    return await get_meeting(access, meeting.id, note)


async def reextract(
    access: WorkspaceAccess, meeting_id: uuid.UUID, settings: Settings
) -> MeetingDetail:
    authorize(access, Permission.KNOWLEDGE_WRITE)
    meeting = await _load(access, meeting_id)
    note = await _extract(access, meeting, settings)
    return await get_meeting(access, meeting.id, note)


async def _load(access: WorkspaceAccess, meeting_id: uuid.UUID) -> Meeting:
    meeting = await access.session.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id, visible(access, Permission.AI_READ, Meeting.tenant_id)
        )
    )
    if meeting is None:
        raise ApiError(404, "not_found", "Meeting not found.")
    return meeting


def _item_view(i: MeetingItem) -> MeetingItemView:
    return MeetingItemView.model_validate(i, from_attributes=True)


def _summary(m: Meeting, items: list[MeetingItem]) -> dict[str, object]:
    return {
        "id": m.id,
        "title": m.title,
        "held_at": m.held_at,
        "responsibility_id": m.responsibility_id,
        "case_id": m.case_id,
        "extract_mode": m.extract_mode,
        "counts": dict(Counter(i.kind for i in items if i.status != "dismissed")),
        "pending": sum(i.status == "proposed" for i in items),
    }


async def list_meetings(access: WorkspaceAccess) -> list[MeetingSummary]:
    authorize(access, Permission.AI_READ)
    meetings = list(
        await access.session.scalars(
            select(Meeting)
            .where(visible(access, Permission.AI_READ, Meeting.tenant_id))
            .order_by(Meeting.held_at.desc())
            .limit(200)
        )
    )
    items = list(
        await access.session.scalars(
            select(MeetingItem).where(MeetingItem.meeting_id.in_([m.id for m in meetings]))
        )
    )
    return [
        MeetingSummary.model_validate(_summary(m, [i for i in items if i.meeting_id == m.id]))
        for m in meetings
    ]


async def get_meeting(
    access: WorkspaceAccess, meeting_id: uuid.UUID, note: str | None = None
) -> MeetingDetail:
    authorize(access, Permission.AI_READ)
    meeting = await _load(access, meeting_id)
    items = list(
        await access.session.scalars(
            select(MeetingItem)
            .where(MeetingItem.meeting_id == meeting.id)
            .order_by(MeetingItem.created_at)
        )
    )
    return MeetingDetail.model_validate(
        {
            **_summary(meeting, items),
            "lines": _lines(meeting.transcript),
            "items": [_item_view(i) for i in items],
            "note": note,
            "can_review": role_allows(access.role, Permission.KNOWLEDGE_WRITE),
        }
    )


async def _member_by_name(access: WorkspaceAccess, name: str | None) -> uuid.UUID | None:
    if not name:
        return None
    wanted = name.strip().lower()
    matches = [
        uid
        for uid, full in (await continuity._member_names(access)).items()
        if full.lower() == wanted or full.lower().split()[0] == wanted
    ]
    return matches[0] if len(matches) == 1 else None


async def review_item(
    access: WorkspaceAccess,
    item_id: uuid.UUID,
    accept: bool,
    jobs: procrastinate.App,
) -> MeetingItemView:
    authorize(access, Permission.KNOWLEDGE_WRITE)
    item = await access.session.scalar(
        select(MeetingItem)
        .where(
            MeetingItem.id == item_id, visible(access, Permission.AI_READ, MeetingItem.tenant_id)
        )
        .with_for_update()
    )
    if item is None:
        raise ApiError(404, "not_found", "Item not found.")
    if item.status != "proposed":
        return _item_view(item)  # already reviewed: repeat clicks are harmless
    meeting = await _load(access, item.meeting_id)
    if accept:
        item.result_ref = await _apply(access, meeting, item, jobs)
    item.status = "accepted" if accept else "dismissed"
    item.reviewed_by = access.user_id
    item.reviewed_at = datetime.now(UTC)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action=f"meeting.item_{item.status}",
        actor_user_id=access.user_id,
        target_type="meeting_item",
        target_id=item.id,
        details={"kind": item.kind, "result": (item.result_ref or "").split(":")[0] or None},
    )
    await access.session.flush()
    return _item_view(item)


async def _apply(
    access: WorkspaceAccess, meeting: Meeting, item: MeetingItem, jobs: procrastinate.App
) -> str | None:
    lines = _lines(meeting.transcript)
    quoted = "\n".join(f"> {lines[n - 1]}" for n in item.lines if n <= len(lines))
    where = f'From the meeting "{meeting.title}" on {meeting.held_at:%d %b %Y}:\n\n{quoted}'
    if item.kind == "decision" and meeting.responsibility_id:
        made = await knowledge.add_knowledge(
            access,
            meeting.responsibility_id,
            knowledge.KnowledgeIn(
                kind="adr",
                title=item.text[:200],
                body=where,
                decided_at=meeting.held_at,
            ),
        )
        return f"knowledge:{made.id}"
    if item.kind == "action" and meeting.case_id:
        assignee = await _member_by_name(access, item.owner_name)
        due = f" Due: {item.due_text}." if item.due_text else ""
        await continuity.add_task(
            access,
            meeting.case_id,
            continuity.TaskIn(
                title=item.text[:200], description=f"{where}{due}", assignee_user_id=assignee
            ),
            jobs,
        )
        return f"case:{meeting.case_id}"
    return None


# --- decision log -------------------------------------------------------------------------


class DecisionEntry(BaseModel):
    id: str
    text: str
    origin: Literal["meeting", "knowledge", "analysis"]
    status: str  # proposed | accepted | recorded | superseded | unreviewed
    decided_at: datetime | None
    rationale: str | None = None
    responsibility_id: uuid.UUID | None = None
    responsibility_name: str | None = None
    meeting_id: uuid.UUID | None = None
    meeting_title: str | None = None
    case_id: uuid.UUID | None = None
    knowledge_id: uuid.UUID | None = None
    lines: list[int] = []


async def decision_log(access: WorkspaceAccess) -> list[DecisionEntry]:
    """Every decision Relay knows about, newest first: decision knowledge (ADRs), decisions
    found in meetings, and decisions an analysis reconstructed, each linked to its source."""
    authorize(access, Permission.AI_READ)
    session = access.session
    manager = role_allows(access.role, Permission.RESPONSIBILITY_MANAGE)
    names = dict(
        (
            await session.execute(
                select(Responsibility.id, Responsibility.name).where(
                    visible(access, Permission.AI_READ, Responsibility.tenant_id)
                )
            )
        ).all()
    )
    out: list[DecisionEntry] = []
    adrs = await session.scalars(
        select(KnowledgeItem)
        .where(
            KnowledgeItem.kind == "adr",
            KnowledgeItem.status == "active",
            visible(access, Permission.AI_READ, KnowledgeItem.tenant_id),
        )
        .limit(300)
    )
    for k in adrs:
        if k.visibility != "workspace" and not manager:
            continue
        out.append(
            DecisionEntry(
                id=f"k:{k.id}",
                text=k.title,
                origin="knowledge",
                status="superseded" if k.superseded_by_id else "recorded",
                decided_at=k.decided_at or k.created_at,
                rationale=k.decision_rationale,
                responsibility_id=k.responsibility_id,
                responsibility_name=names.get(k.responsibility_id),
                knowledge_id=k.id,
            )
        )
    rows = await session.execute(
        select(MeetingItem, Meeting)
        .join(Meeting, Meeting.id == MeetingItem.meeting_id)
        .where(
            MeetingItem.kind == "decision",
            MeetingItem.status != "dismissed",
            visible(access, Permission.AI_READ, MeetingItem.tenant_id),
        )
        .limit(300)
    )
    for item, m in rows.all():
        if item.result_ref and item.result_ref.startswith("knowledge:"):
            continue  # already listed as the knowledge it became
        out.append(
            DecisionEntry(
                id=f"m:{item.id}",
                text=item.text,
                origin="meeting",
                status=item.status,
                decided_at=m.held_at,
                responsibility_id=m.responsibility_id,
                responsibility_name=names.get(m.responsibility_id) if m.responsibility_id else None,
                meeting_id=m.id,
                meeting_title=m.title,
                lines=item.lines,
            )
        )
    claims = await session.scalars(
        select(Claim)
        .where(
            Claim.kind == "decision",
            Claim.review_status != "rejected",
            Claim.supported.is_(True),
            visible(access, Permission.AI_READ, Claim.tenant_id),
        )
        .order_by(Claim.created_at.desc())
        .limit(200)
    )
    seen = {re.sub(r"\W+", " ", e.text.lower()).strip() for e in out}
    for c in claims:
        key = re.sub(r"\W+", " ", c.text.lower()).strip()
        if key in seen or (c.audience != "workspace" and not manager):
            continue
        seen.add(key)
        out.append(
            DecisionEntry(
                id=f"c:{c.id}",
                text=c.text,
                origin="analysis",
                status="accepted" if c.review_status == "accepted" else "unreviewed",
                decided_at=c.timeline_at or c.created_at,
                case_id=c.case_id,
            )
        )
    out.sort(key=lambda e: e.decided_at or datetime.min.replace(tzinfo=UTC), reverse=True)
    return out
