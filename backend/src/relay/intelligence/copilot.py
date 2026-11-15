"""Handover Copilot: the incoming owner asks questions; answers come only from evidence.

The evidence is what the handover was built from (the capsule's citations and the case's
latest analysis pool), re-checked now for the person asking: withdrawn sources drop out
and managers-only evidence is never used for someone who can't see it (D2). The model
gets that pool and read-only search tools, must cite refs, and may say "not found".

An answer is only served as an answer when it cites evidence that exists in the pool.
Otherwise the reply is a "not found in the evidence" message with the closest sources
to check. With AI unavailable, a keyword search over the same pool is returned instead,
labelled as search results, never dressed up as an answer.
"""

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select

from relay.audit import service as audit
from relay.config import Settings
from relay.continuity import service as continuity
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import capsules, instant, runs
from relay.intelligence import service as svc
from relay.intelligence.evidence import Pool, PoolItem
from relay.intelligence.models import AgentRun, CapsuleQuestion, CapsuleVersion, Evidence
from relay.intelligence.validate import split_refs, valid_refs
from relay.shared.api_types import StrictInput

NAME = "handover_copilot"
MAX_SOURCES = 3
NOT_FOUND = "This isn't answered by the evidence attached to this handover."
NOT_FOUND_HISTORY = "No event in this history answers that."
_STOP = frozenset(
    [
        "the",
        "and",
        "for",
        "are",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "how",
        "does",
        "did",
        "this",
        "that",
        "with",
        "from",
        "have",
        "has",
        "into",
        "about",
        "there",
        "their",
        "them",
        "they",
        "you",
        "your",
        "our",
        "can",
        "should",
        "would",
        "could",
        "is",
        "it",
        "its",
        "of",
        "to",
        "in",
        "on",
        "at",
        "by",
        "an",
        "or",
        "be",
        "do",
        "we",
    ]
)


class AskIn(StrictInput):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class CopilotOutput(BaseModel):
    found: bool = Field(description="False if the evidence does not answer the question.")
    answer: str = Field(max_length=2000, description="The answer, or what is missing.")
    evidence: list[str] = Field(default_factory=list, description="Refs like E3 it rests on.")
    confidence: Literal["high", "medium", "low"] = "medium"


class AnswerView(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    mode: Literal["ai", "search", "not_found"]
    confidence: str | None
    note: str | None  # why the answer is a search result, when it is one
    asked_by: str
    asked_at: datetime
    capsule_version: int
    evidence: list[svc.EvidenceView]
    withdrawn_sources: int  # cited sources since withdrawn or no longer visible to you


Source = tuple[Evidence, svc.EvidenceView]


async def _evidence(
    access: WorkspaceAccess, capsule_id: uuid.UUID, case_id: uuid.UUID
) -> list[Source]:
    """Evidence behind the handover the viewer may see now, newest copy per source."""
    session = access.session
    cited = {
        uuid.UUID(e)
        for v in await session.scalars(
            select(CapsuleVersion).where(CapsuleVersion.capsule_id == capsule_id)
        )
        for s in v.sections
        for p in s["points"]
        for e in p["evidence_ids"]
    }
    rows = await svc._evidence_rows(access, cited)
    analysis = await capsules._latest_analysis(session, case_id)
    if analysis is not None:
        rows += list(await session.scalars(select(Evidence).where(Evidence.run_id == analysis.id)))
    current = await svc.current_evidence(access, rows)
    manager = svc._manager(access)
    newest: dict[tuple[str, str], Source] = {}
    for row in rows:
        view = current[row.id]
        if view.status != "active" or not (manager or view.audience == "workspace"):
            continue
        key = (row.source_type, row.source_id)
        if key not in newest or row.created_at > newest[key][0].created_at:
            newest[key] = (row, view)
    return list(newest.values())


def _pool(
    case_id: uuid.UUID, title: str, sources: list[Source]
) -> tuple[Pool, dict[str, uuid.UUID]]:
    items, ids = [], {}
    for n, (row, view) in enumerate(sources, start=1):
        ref = f"E{n}"
        ids[ref] = row.id
        items.append(
            PoolItem(
                ref=ref,
                source_system=row.source_system,
                source_type=row.source_type,
                source_id=row.source_id,
                title=row.title,
                excerpt=view.excerpt,
                audience=view.audience,
                url=row.url,
                revision=row.revision,
                source_ts=row.source_ts,
            )
        )
    return Pool(case_id, title, items, []), ids


def search(pool: Pool, question: str) -> list[str]:
    """Refs of the items sharing the most words with the question (best first)."""
    words = {w for w in re.findall(r"[a-z0-9]+", question.lower()) if len(w) > 2} - _STOP
    scored = []
    for i in pool.items:
        text = set(re.findall(r"[a-z0-9]+", f"{i.title} {i.excerpt}".lower()))
        score = len(words & text)
        if score:
            scored.append((score, i.ref))
    return [ref for _, ref in sorted(scored, key=lambda s: (-s[0], int(s[1][1:])))][:MAX_SOURCES]


async def ask(
    access: WorkspaceAccess, capsule_id: uuid.UUID, data: AskIn, settings: Settings
) -> AnswerView:
    capsule = await capsules._load(access, capsule_id)  # recipient or editor, else 404
    session = access.session
    case_title = (await continuity._load(access, capsule.case_id)).title
    pool, ids = _pool(
        capsule.case_id, case_title, await _evidence(access, capsule.id, capsule.case_id)
    )
    mode: Literal["ai", "search", "not_found"] = "not_found"
    answer, refs, confidence, run_id, note = (
        NOT_FOUND,
        search(pool, data.question),
        None,
        None,
        None,
    )
    if pool.items:
        outcome = await instant.call(
            access,
            settings,
            name=NAME,
            pool=pool,
            extra=f"Question from the incoming owner: {data.question}",
            output_type=CopilotOutput,
            case_id=capsule.case_id,
        )
        run_id = outcome.run_id
        out = outcome.output
        if out is None:
            note = outcome.message
            if refs:
                mode = "search"
                answer = "These sources in the handover mention what you asked about."
        else:
            text, inline = split_refs(out.answer)
            cited = valid_refs(pool, [*out.evidence, *inline])
            if out.found and cited and text:
                mode, answer, refs, confidence = "ai", text, cited, out.confidence
            elif cited is None and run_id is not None:
                # Cited evidence that isn't in the pool: an invented source. Flag the run.
                run = await session.get(AgentRun, run_id)
                if run is not None:
                    run.checkpoint = {**run.checkpoint, "suspicious": True}
                    run.state = runs.settled_state(run)
    question = CapsuleQuestion(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        capsule_id=capsule.id,
        version=capsule.current_version,
        asked_by=access.user_id,
        question=data.question,
        answer=answer,
        mode=mode,
        confidence=confidence,
        evidence_ids=[str(ids[r]) for r in refs],
        run_id=run_id,
    )
    session.add(question)
    audit.record(
        session,
        tenant_id=access.tenant_id,
        action="ai.copilot_question",
        actor_user_id=access.user_id,
        target_type="continuity_case",
        target_id=capsule.case_id,
        details={"capsule_id": str(capsule.id), "question_id": str(question.id), "mode": mode},
    )
    await session.flush()
    await session.refresh(question, ["created_at"])
    views = await _views(access, [question])
    views[0].note = note
    return views[0]


async def thread(access: WorkspaceAccess, capsule_id: uuid.UUID) -> list[AnswerView]:
    capsule = await capsules._load(access, capsule_id)
    rows = list(
        await access.session.scalars(
            select(CapsuleQuestion)
            .where(CapsuleQuestion.capsule_id == capsule.id)
            .order_by(CapsuleQuestion.created_at)
        )
    )
    return await _views(access, rows)


async def _views(access: WorkspaceAccess, rows: list[CapsuleQuestion]) -> list[AnswerView]:
    ids = {uuid.UUID(e) for q in rows for e in q.evidence_ids}
    current = await svc.current_evidence(access, await svc._evidence_rows(access, ids))
    names = await continuity._member_names(access)
    manager = svc._manager(access)
    out = []
    for q in rows:
        shown, dropped = [], 0
        for e in q.evidence_ids:
            view = current.get(uuid.UUID(e))
            if view is None or view.status != "active":
                dropped += 1
            elif manager or view.audience == "workspace":
                shown.append(view)
            else:
                dropped += 1
        # An answer whose every source is gone or hidden is no longer shown as an answer.
        hidden = q.mode == "ai" and not shown
        out.append(
            AnswerView(
                id=q.id,
                question=q.question,
                answer="The sources behind this answer are no longer available to you."
                if hidden
                else q.answer,
                mode="not_found" if hidden else q.mode,
                confidence=None if hidden else q.confidence,
                note=None,
                asked_by=names.get(q.asked_by, "Member"),
                asked_at=q.created_at,
                capsule_version=q.version,
                evidence=shown,
                withdrawn_sources=dropped,
            )
        )
    return out
