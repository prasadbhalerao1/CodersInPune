"""Knowledge interviews: targeted questions for the person handing over.

Rule-based questions (nothing written down, knowledge overdue for review) are created at
once; with AI on, the Knowledge Interviewer adds questions about what the evidence can't
answer. Questions are addressed to the case's affected person when they are a member
(matched by email); managers can answer on their behalf. A reviewed answer can become a
knowledge *proposal*, which still needs accepting.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

import procrastinate
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.config import Settings
from relay.continuity import service as continuity
from relay.continuity.models import ContinuityCase
from relay.directory.models import Person
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import capabilities as caps
from relay.intelligence import runs
from relay.intelligence import service as svc
from relay.intelligence.evidence import Pool, build_pool
from relay.intelligence.models import AgentRun, Evidence, InterviewQuestion, Proposal
from relay.intelligence.validate import valid_refs
from relay.policy.permissions import Permission, authorize, role_allows
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

INTERVIEW = "knowledge_interviewer"
Answer = Annotated[str, StringConstraints(strip_whitespace=True, max_length=8000)]


class QuestionView(BaseModel):
    id: uuid.UUID
    question: str
    why: str
    status: str
    answer: str | None
    answered_by: str | None
    answered_at: datetime | None
    reviewed_at: datetime | None
    asked_user_id: uuid.UUID | None
    asked_name: str | None
    ai: bool
    can_answer: bool
    evidence: list[svc.EvidenceView]


class InterviewView(BaseModel):
    case_id: uuid.UUID
    ai_configured: bool
    run: svc.RunView | None
    questions: list[QuestionView]
    can_generate: bool
    can_review: bool


class AnswerIn(StrictInput):
    status: Literal["answered", "unknown", "not_applicable", "cannot_share", "open"]
    answer: Answer | None = None


async def _asked_user(access: WorkspaceAccess, case: ContinuityCase) -> uuid.UUID | None:
    if case.affected_person_id is None:
        return None
    email = await access.session.scalar(
        select(Person.email).where(Person.id == case.affected_person_id)
    )
    if not email:
        return None
    return await access.session.scalar(
        select(Membership.user_id).where(
            func.lower(Membership.email) == email.lower(), Membership.status == "active"
        )
    )


async def _existing(session: AsyncSession, case_id: uuid.UUID) -> set[str]:
    rows = await session.scalars(
        select(InterviewQuestion.question).where(InterviewQuestion.case_id == case_id)
    )
    return {q.strip().lower() for q in rows}


def _add(
    session: AsyncSession,
    run: AgentRun,
    seen: set[str],
    question: str,
    why: str,
    evidence: list[uuid.UUID],
    responsibility_id: uuid.UUID | None,
    asked: uuid.UUID | None,
    source: str = "rules",
) -> bool:
    question = " ".join(question.split())[:500]
    if not question or question.lower() in seen:
        return False
    seen.add(question.lower())
    assert run.case_id is not None
    session.add(
        InterviewQuestion(
            tenant_id=run.tenant_id,
            case_id=run.case_id,
            run_id=run.id,
            responsibility_id=responsibility_id,
            question=question,
            why=" ".join(why.split())[:500],
            evidence_ids=[str(e) for e in evidence],
            asked_user_id=asked,
            source=source,
        )
    )
    return True


def _rule_questions(pool: Pool) -> list[tuple[str, str, list[str], str | None]]:
    out: list[tuple[str, str, list[str], str | None]] = []
    knowledge = [i for i in pool.items if i.facts.get("kind") == "knowledge"]
    for r in pool.items:
        if r.facts.get("kind") != "responsibility":
            continue
        mine = [
            k for k in knowledge if k.facts["responsibility_id"] == r.facts["responsibility_id"]
        ]
        if not mine:
            out.append(
                (
                    f"What does someone need to know to keep {r.title} running?",
                    "Nothing is written down for this responsibility.",
                    [r.ref],
                    r.source_id,
                )
            )
        for k in mine:
            if k.facts["stale"]:
                out.append(
                    (
                        f"Is '{k.title}' still accurate? What has changed?",
                        "It hasn't been reviewed within the workspace's review period.",
                        [k.ref],
                        r.source_id,
                    )
                )
    return out


async def generate(
    access: WorkspaceAccess, case_id: uuid.UUID, settings: Settings, jobs: procrastinate.App
) -> svc.RunView:
    authorize(access, Permission.AI_RUN)
    session = access.session
    case = await continuity._load(access, case_id)
    pool = await build_pool(access, case)
    gateway = runs.gateway_for(settings)
    ai = gateway.configured and await runs.ai_enabled(session, INTERVIEW)
    run = AgentRun(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        capability=INTERVIEW,
        capability_version=1,
        case_id=case_id,
        requested_by=access.user_id,
        state="running",
        input_hash=pool.input_hash(),
        checkpoint={
            "case_title": case.title,
            "partial_sources": pool.partial_sources,
            "steps": [INTERVIEW] if ai else [],
            "ai": "on" if ai else ("off" if gateway.configured else "not_configured"),
            "asked_user_id": str(asked) if (asked := await _asked_user(access, case)) else None,
        },
        started_at=runs._now(),
    )
    session.add(run)
    await session.flush()
    ids = await runs.persist_pool(session, run, pool)
    seen = await _existing(session, case_id)
    added = sum(
        _add(
            session,
            run,
            seen,
            q,
            why,
            [ids[r] for r in refs],
            uuid.UUID(rid) if rid else None,
            asked,
        )
        for q, why, refs, rid in _rule_questions(pool)
    )
    runs._event(session, run, "rules", "questions_added", count=added)
    if ai:
        await runs._queue(session, jobs, run)
    else:
        runs.finish(run, runs.settled_state(run))
    audit.record(
        session,
        tenant_id=access.tenant_id,
        action="ai.run_started",
        actor_user_id=access.user_id,
        target_type="continuity_case",
        target_id=case_id,
        details={"run_id": str(run.id), "capability": INTERVIEW},
    )
    return svc.run_view(run)


async def _store(
    session: AsyncSession,
    run: AgentRun,
    name: str,
    output: caps.InterviewOutput,
    pool: Pool,
    ids: dict[str, uuid.UUID],
) -> dict[str, int]:
    assert run.case_id is not None
    seen = await _existing(session, run.case_id)
    asked_raw = run.checkpoint.get("asked_user_id")
    asked = uuid.UUID(asked_raw) if asked_raw else None
    added = rejected = 0
    for q in output.questions:
        refs = valid_refs(pool, q.evidence)
        if refs is None:
            rejected += 1
            continue
        target = pool.get(q.responsibility.strip().upper()) if q.responsibility else None
        rid = (
            uuid.UUID(target.source_id)
            if target is not None and target.source_type == "responsibility"
            else None
        )
        if _add(session, run, seen, q.question, q.why, [ids[r] for r in refs], rid, asked, "ai"):
            added += 1
    return {"questions": added, "rejected": rejected}


runs.STEP_KINDS[INTERVIEW] = runs.StepKind(caps.InterviewOutput, _store)


async def interview(
    access: WorkspaceAccess, case_id: uuid.UUID, settings: Settings
) -> InterviewView:
    authorize(access, Permission.AI_READ)
    await continuity._load(access, case_id)
    session = access.session
    questions = list(
        await session.scalars(
            select(InterviewQuestion)
            .where(InterviewQuestion.case_id == case_id)
            .order_by(InterviewQuestion.status != "open", InterviewQuestion.created_at)
        )
    )
    rows = (
        list(
            await session.scalars(
                select(Evidence).where(
                    Evidence.id.in_([uuid.UUID(e) for q in questions for e in q.evidence_ids])
                )
            )
        )
        if questions
        else []
    )
    evidence = await svc.current_evidence(access, rows)
    names = await continuity._member_names(access)
    reviewer = role_allows(access.role, Permission.AI_REVIEW)
    views = []
    for q in questions:
        ev = [evidence[uuid.UUID(e)] for e in q.evidence_ids if uuid.UUID(e) in evidence]
        audience = "managers" if any(e.audience == "managers" for e in ev) else "workspace"
        if not svc._allowed(access, audience, ev):
            continue
        views.append(
            QuestionView(
                id=q.id,
                question=q.question,
                why=q.why,
                status=q.status,
                answer=q.answer,
                answered_by=names.get(q.answered_by) if q.answered_by else None,
                answered_at=q.answered_at,
                reviewed_at=q.reviewed_at,
                asked_user_id=q.asked_user_id,
                asked_name=names.get(q.asked_user_id) if q.asked_user_id else None,
                ai=q.source == "ai",
                can_answer=reviewer or q.asked_user_id == access.user_id,
                evidence=ev,
            )
        )
    run = await session.scalar(
        select(AgentRun)
        .where(AgentRun.case_id == case_id, AgentRun.capability == INTERVIEW)
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    return InterviewView(
        case_id=case_id,
        ai_configured=runs.gateway_for(settings).configured,
        run=svc.run_view(run) if run else None,
        questions=views,
        can_generate=role_allows(access.role, Permission.AI_RUN),
        can_review=reviewer,
    )


async def _question(access: WorkspaceAccess, question_id: uuid.UUID) -> InterviewQuestion:
    authorize(access, Permission.AI_READ)
    q = await access.session.scalar(
        select(InterviewQuestion)
        .where(
            InterviewQuestion.id == question_id,
            InterviewQuestion.tenant_id == access.tenant_id,
        )
        .with_for_update()
    )
    if q is None:
        raise ApiError(404, "question_not_found", "Question not found.")
    return q


async def answer(access: WorkspaceAccess, question_id: uuid.UUID, data: AnswerIn) -> None:
    q = await _question(access, question_id)
    if q.asked_user_id != access.user_id and not role_allows(access.role, Permission.AI_REVIEW):
        raise ApiError(403, "forbidden", "Only the person asked or a case manager can answer.")
    if data.status == "answered" and not data.answer:
        raise ApiError(422, "answer_required", "Write an answer, or choose another status.")
    q.status, q.answer = data.status, data.answer if data.status == "answered" else None
    q.answered_by, q.answered_at = access.user_id, func.now()
    q.reviewed_by = q.reviewed_at = None  # a changed answer needs reviewing again


async def review(access: WorkspaceAccess, question_id: uuid.UUID) -> None:
    authorize(access, Permission.AI_REVIEW)
    q = await _question(access, question_id)
    if q.status == "open":
        raise ApiError(409, "not_answered", "This question hasn't been answered yet.")
    q.reviewed_by, q.reviewed_at = access.user_id, func.now()


async def to_knowledge(access: WorkspaceAccess, question_id: uuid.UUID) -> svc.ProposalView:
    """Turn a reviewed answer into a knowledge proposal (still needs accepting)."""
    authorize(access, Permission.AI_REVIEW)
    q = await _question(access, question_id)
    if q.status != "answered" or not q.answer or q.reviewed_at is None:
        raise ApiError(409, "not_reviewed", "Review the answer before proposing it as knowledge.")
    rows = await svc._evidence_rows(access, (uuid.UUID(e) for e in q.evidence_ids))
    audience = "managers" if any(e.audience == "managers" for e in rows) else "workspace"
    title = q.question.rstrip("?")[:200]
    proposal = Proposal(
        tenant_id=access.tenant_id,
        case_id=q.case_id,
        run_id=q.run_id,
        capability=INTERVIEW,
        type="knowledge_draft",
        title=title,
        payload={"detail": q.answer, "question_id": str(q.id)},
        evidence_ids=q.evidence_ids,
        confidence="high",
        audience=audience,
        fingerprint=runs.fingerprint("knowledge_draft", title),
        evidence_revision=f"interview:{q.id}",
    )
    access.session.add(proposal)
    await access.session.flush()
    await access.session.refresh(proposal)
    return svc._proposal_view(proposal, {})
