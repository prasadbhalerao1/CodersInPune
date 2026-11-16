"""Handover rehearsal: the successor practises on their handover before they need it.

Drills are built from the brief's own evidence (procedures, decisions, contacts, open
work), only what the recipient may see. Each answer is graded by rules, not by a model:
the key terms of the evidence the drill came from are checked against the answer, and the
result shows what was covered, what was missed, and the source to re-read. Nothing is
stored but an audit event with the score.
"""

import hashlib
import re
import uuid
from collections import Counter
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from relay.audit import service as audit
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import copilot
from relay.intelligence.evidence import PoolItem
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

MAX_DRILLS = 6
_STOP_WORDS = (
    "about above after again against also because been before being below between both "
    "cannot could does doing down during each from further have having here into itself "
    "just more most must only other over same should some such than that their them then "
    "there these they this those through under until very were what when where which "
    "while with would your will make sure need using used"
)
_STOP = frozenset(_STOP_WORDS.split())
PROMPTS = {
    "knowledge": "Walk through it: {title}. What are the steps, and what must not be skipped?",
    "decision": "A colleague asks why: {title}. What was decided, and why?",
    "work": "This is still open: {title}. What is its state and what happens next?",
    "risk": "This could go wrong: {title}. What do you watch for, and who do you call?",
}


class Drill(BaseModel):
    id: str
    kind: Literal["knowledge", "decision", "work", "risk"]
    prompt: str
    source_title: str


class RehearsalView(BaseModel):
    drills: list[Drill]


class RehearsalAnswerIn(StrictInput):
    drill_id: Annotated[str, StringConstraints(min_length=8, max_length=64)]
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class GradeView(BaseModel):
    drill_id: str
    score: int  # 0-100: share of the source's key terms the answer covered
    verdict: Literal["ready", "partly", "not_yet"]
    covered: list[str]
    missed: list[str]
    source_title: str
    source_excerpt: str
    source_url: str | None


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9-]{3,}", text.lower()) if w not in _STOP]


def key_terms(item: PoolItem, limit: int = 8) -> list[str]:
    """The words that carry the source: frequent in its body, not filler, title words first."""
    title = _words(item.title)
    body = re.sub(r"^\s*\[[^\]]*\]\s*", "", item.excerpt)  # drop the "[procedure]" label
    counts = Counter(_words(body))
    ranked = [w for w, _ in counts.most_common() if w not in title]
    terms = list(dict.fromkeys([*title, *ranked]))
    return terms[:limit]


def _kind(item: PoolItem) -> Literal["knowledge", "decision", "work", "risk"] | None:
    t = item.source_type
    if t in ("knowledge", "notion_page"):
        decided = "decid" in item.excerpt.lower() or "adr" in item.title.lower()
        return "decision" if decided else "knowledge"
    if t in ("pull_request", "issue", "task"):
        return "work"
    if t == "readiness_criterion":
        return "risk"
    return None


def _drill_id(capsule_id: uuid.UUID, item: PoolItem) -> str:
    return hashlib.sha256(f"{capsule_id}:{item.ref}:{item.source_id}".encode()).hexdigest()[:16]


def _drills(capsule_id: uuid.UUID, items: list[PoolItem]) -> list[tuple[Drill, PoolItem]]:
    """Up to six drills: one of each kind first, then more of whatever the brief holds."""
    usable = [(k, i) for i in items if (k := _kind(i)) and len(key_terms(i)) >= 3]
    first = list({k: (k, i) for k, i in reversed(usable)}.values())
    rest = [pair for pair in usable if pair not in first]
    return [
        (
            Drill(
                id=_drill_id(capsule_id, item),
                kind=kind,
                prompt=PROMPTS[kind].format(title=item.title),
                source_title=item.title,
            ),
            item,
        )
        for kind, item in [*first, *rest][:MAX_DRILLS]
    ]


async def drills(access: WorkspaceAccess, capsule_id: uuid.UUID) -> RehearsalView:
    asked = await copilot._prepare(access, capsule_id, "rehearsal")  # recipient or editor
    return RehearsalView(drills=[d for d, _ in _drills(asked.capsule_id, asked.pool.items)])


async def grade(
    access: WorkspaceAccess, capsule_id: uuid.UUID, data: RehearsalAnswerIn
) -> GradeView:
    asked = await copilot._prepare(access, capsule_id, "rehearsal")
    found = next(
        ((d, i) for d, i in _drills(asked.capsule_id, asked.pool.items) if d.id == data.drill_id),
        None,
    )
    if found is None:
        raise ApiError(404, "drill_not_found", "This drill is no longer part of the handover.")
    drill, item = found
    terms = key_terms(item)
    said = set(_words(data.answer))
    # A term counts when the answer uses it or a word sharing its first five letters.
    covered = [t for t in terms if t in said or any(w[:5] == t[:5] for w in said)]
    missed = [t for t in terms if t not in covered]
    score = round(100 * len(covered) / len(terms)) if terms else 0
    verdict: Literal["ready", "partly", "not_yet"] = (
        "ready" if score >= 70 else "partly" if score >= 35 else "not_yet"
    )
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="handover.rehearsal_graded",
        actor_user_id=access.user_id,
        target_type="capsule",
        target_id=asked.capsule_id,
        details={"score": score, "kind": drill.kind},
    )
    return GradeView(
        drill_id=drill.id,
        score=score,
        verdict=verdict,
        covered=covered,
        missed=missed,
        source_title=item.title,
        source_excerpt=re.sub(r"^\s*\[[^\]]*\]\s*", "", item.excerpt)[:600],
        source_url=item.url,
    )
