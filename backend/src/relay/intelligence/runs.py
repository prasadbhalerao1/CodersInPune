"""Run engine: one outbox event per step, each step committed (the checkpoint).

`start_analysis` runs in the requester's transaction: it builds the evidence pool with
their access, persists it, runs the deterministic rules and queues the first AI step.
Each AI step runs in the worker as `relay_app` under the run's tenant, reads only the
persisted pool, validates the model output, stores claims/proposals and queues the next
step. A crash re-delivers the same step; completed steps are never repeated (`step`).
"""

import hashlib
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import procrastinate
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.config import Settings
from relay.continuity import service as continuity
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import capabilities as caps
from relay.intelligence import deterministic
from relay.intelligence.evidence import Pool, PoolItem, build_pool
from relay.intelligence.llm import Gateway, LLMError, LLMResult
from relay.intelligence.models import (
    AgentRun,
    AgentRunEvent,
    AiCapabilitySetting,
    AiSettings,
    Claim,
    ClaimEvidence,
    Evidence,
    Proposal,
)
from relay.intelligence.registry import ANALYSIS_STEPS, capability
from relay.intelligence.validate import (
    ValidClaim,
    audience_of,
    normalise,
    valid_refs,
    validate_claims,
)
from relay.jobs import outbox
from relay.jobs.models import OutboxEvent
from relay.policy.permissions import Permission, authorize
from relay.shared.errors import ApiError

STEP_EVENT = "ai.run_step"
ANALYSIS = "case_analysis"
ACTIVE = ("queued", "running")
RUN_TIME_LIMIT = timedelta(minutes=15)

_gateways: dict[int, Gateway] = {}


def gateway_for(settings: Settings) -> Gateway:
    """One gateway per settings object, so key cooldowns persist across requests."""
    if id(settings) not in _gateways:
        _gateways[id(settings)] = Gateway(settings)
    return _gateways[id(settings)]


def _now() -> datetime:
    return datetime.now(UTC)


def _event(
    session: AsyncSession,
    run: AgentRun,
    step: str,
    code: str,
    level: str = "info",
    /,
    **detail: Any,
) -> None:
    session.add(
        AgentRunEvent(
            tenant_id=run.tenant_id, run_id=run.id, step=step, level=level, code=code, detail=detail
        )
    )


async def ai_enabled(session: AsyncSession, name: str) -> bool:
    """Workspace kill switch and per-capability toggle (absent rows mean on)."""
    if await session.scalar(select(AiSettings.enabled)) is False:
        return False
    toggle = await session.scalar(
        select(AiCapabilitySetting.enabled).where(AiCapabilitySetting.capability == name)
    )
    return toggle is not False


async def monthly_tokens_left(session: AsyncSession, settings: Settings) -> int:
    budget = await session.scalar(select(AiSettings.monthly_token_budget))
    budget = settings.ai_monthly_token_budget if budget is None else budget
    start = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = await session.scalar(
        select(func.coalesce(func.sum(AgentRun.input_tokens + AgentRun.output_tokens), 0)).where(
            AgentRun.created_at >= start
        )
    )
    return budget - int(used or 0)


# --- persistence --------------------------------------------------------------------


async def persist_pool(session: AsyncSession, run: AgentRun, pool: Pool) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}
    for i in pool.items:
        ids[i.ref] = uuid.uuid7()
        session.add(
            Evidence(
                id=ids[i.ref],
                tenant_id=run.tenant_id,
                run_id=run.id,
                case_id=pool.case_id,
                ref=i.ref,
                source_system=i.source_system,
                source_type=i.source_type,
                source_id=i.source_id,
                title=i.title[:300],
                url=i.url,
                revision=i.revision,
                source_ts=i.source_ts,
                excerpt=i.excerpt,
                audience=i.audience,
            )
        )
    await session.flush()
    return ids


async def load_pool(session: AsyncSession, run: AgentRun) -> tuple[Pool, dict[str, uuid.UUID]]:
    rows = list(
        await session.scalars(
            select(Evidence).where(Evidence.run_id == run.id).order_by(Evidence.created_at)
        )
    )
    items = [
        PoolItem(
            ref=e.ref,
            source_system=e.source_system,
            source_type=e.source_type,
            source_id=e.source_id,
            title=e.title,
            excerpt=e.excerpt,
            audience=e.audience,
            url=e.url,
            revision=e.revision,
            source_ts=e.source_ts,
        )
        for e in rows
    ]
    items.sort(key=lambda i: int(i.ref[1:]))
    assert run.case_id is not None
    pool = Pool(
        case_id=run.case_id,
        case_title=str(run.checkpoint.get("case_title", "")),
        items=items,
        partial_sources=list(run.checkpoint.get("partial_sources", [])),
    )
    return pool, {e.ref: e.id for e in rows}


def store_claims(
    session: AsyncSession,
    run: AgentRun,
    name: str,
    claims: list[ValidClaim],
    ids: dict[str, uuid.UUID],
) -> None:
    assert run.case_id is not None
    for c in claims:
        claim_id = uuid.uuid7()
        session.add(
            Claim(
                id=claim_id,
                tenant_id=run.tenant_id,
                case_id=run.case_id,
                run_id=run.id,
                capability=name,
                kind=c.kind,
                claim_type=c.claim_type,
                text=c.text,
                confidence=c.confidence,
                audience=c.audience,
                timeline_at=c.timeline_at,
            )
        )
        for ref in c.refs:
            session.add(
                ClaimEvidence(tenant_id=run.tenant_id, claim_id=claim_id, evidence_id=ids[ref])
            )


def fingerprint(kind: str, title: str) -> str:
    norm = " ".join(re.findall(r"[a-z0-9]+", title.lower()))
    return hashlib.sha256(f"{kind}:{norm}".encode()).hexdigest()


def cited_revision(pool: Pool, refs: list[str]) -> str:
    """Revision of exactly the evidence a proposal cites: changes only when that does."""
    items = [i for r in refs if (i := pool.get(r)) is not None]
    parts = sorted(f"{i.source_system}:{i.source_id}:{i.revision}" for i in items)
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


async def store_proposals(
    session: AsyncSession,
    run: AgentRun,
    name: str,
    drafts: list[caps.ProposalDraft],
    pool: Pool,
    ids: dict[str, uuid.UUID],
) -> dict[str, int]:
    """Validated proposals; a rejected one is not proposed again for the same evidence."""
    assert run.case_id is not None
    counts = {"kept": 0, "invalid": 0, "suppressed": 0}
    for d in drafts:
        refs = valid_refs(pool, d.evidence)
        title = " ".join(d.title.split())
        if refs is None or not refs or not title:
            counts["invalid"] += 1
            continue
        fp = fingerprint(d.type, title)
        revision = cited_revision(pool, refs)
        previous = list(
            await session.execute(
                select(Proposal.status, Proposal.evidence_revision).where(
                    Proposal.case_id == run.case_id, Proposal.fingerprint == fp
                )
            )
        )
        if any(status != "rejected" or seen == revision for status, seen in previous):
            counts["suppressed"] += 1
            continue
        session.add(
            Proposal(
                tenant_id=run.tenant_id,
                case_id=run.case_id,
                run_id=run.id,
                capability=name,
                type=d.type,
                title=title[:200],
                payload={"detail": d.detail.strip()},
                evidence_ids=[str(ids[r]) for r in refs],
                confidence=d.confidence,
                audience=audience_of(pool, refs),
                fingerprint=fp,
                evidence_revision=revision,
            )
        )
        counts["kept"] += 1
    return counts


def record_usage(run: AgentRun, result: LLMResult[Any]) -> None:
    run.provider, run.model, run.key_index = result.provider, result.model, result.key_index
    run.input_tokens += result.input_tokens
    run.output_tokens += result.output_tokens
    run.cost_usd = (run.cost_usd or Decimal(0)) + result.cost_usd
    run.duration_ms += result.duration_ms


def finish(run: AgentRun, state: str, error_code: str | None = None) -> None:
    run.state, run.finished_at = state, _now()
    if error_code:
        run.error_code = error_code


def settled_state(run: AgentRun) -> str:
    if run.checkpoint.get("suspicious"):
        return "needs_human_review"
    if run.checkpoint.get("partial_sources") or run.checkpoint.get("failed_steps"):
        return "partial"
    return "completed"


# --- analysis -----------------------------------------------------------------------


async def start_analysis(
    access: WorkspaceAccess, case_id: uuid.UUID, settings: Settings, jobs: procrastinate.App
) -> AgentRun:
    authorize(access, Permission.AI_RUN)
    session = access.session
    case = await continuity._load(access, case_id)
    active = await session.scalar(
        select(AgentRun).where(
            AgentRun.case_id == case_id, AgentRun.capability == ANALYSIS, AgentRun.state.in_(ACTIVE)
        )
    )
    if active is not None:
        return active  # one analysis at a time per case; repeat clicks are idempotent

    pool = await build_pool(access, case)
    gateway = gateway_for(settings)
    steps = (
        [s for s in ANALYSIS_STEPS if await ai_enabled(session, s)] if gateway.configured else []
    )
    run = AgentRun(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        capability=ANALYSIS,
        capability_version=1,
        case_id=case_id,
        requested_by=access.user_id,
        state="running",
        input_hash=pool.input_hash(),
        step=0,
        checkpoint={
            "case_title": case.title,
            "partial_sources": pool.partial_sources,
            "steps": steps,
            "ai": "on" if steps else ("off" if gateway.configured else "not_configured"),
        },
        started_at=_now(),
    )
    session.add(run)
    await session.flush()
    ids = await persist_pool(session, run, pool)
    claims = deterministic.analyse(pool)
    store_claims(session, run, "deterministic", claims, ids)
    _event(session, run, "deterministic", "claims_recorded", claims=len(claims), evidence=len(ids))
    if pool.partial_sources:
        _event(session, run, "evidence", "partial_sources", "warning", sources=pool.partial_sources)
    if steps:
        await _queue(session, jobs, run)
    else:
        finish(run, settled_state(run))
    audit.record(
        session,
        tenant_id=access.tenant_id,
        action="ai.run_started",
        actor_user_id=access.user_id,
        target_type="continuity_case",
        target_id=case_id,
        details={"run_id": str(run.id), "capability": ANALYSIS, "ai_steps": len(steps)},
    )
    return run


async def _queue(session: AsyncSession, jobs: procrastinate.App, run: AgentRun) -> None:
    await outbox.emit(
        session,
        jobs,
        tenant_id=run.tenant_id,
        event_type=STEP_EVENT,
        payload={"run_id": str(run.id), "step": run.step},
    )


async def cancel_run(access: WorkspaceAccess, run_id: uuid.UUID) -> AgentRun:
    authorize(access, Permission.AI_RUN)
    run = await access.session.scalar(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.tenant_id == access.tenant_id)
    )
    if run is None:
        raise ApiError(404, "run_not_found", "Run not found.")
    if run.state in ACTIVE:
        run.cancel_requested = True
        finish(run, "cancelled")
        _event(access.session, run, "control", "cancelled_by_user", user=str(access.user_id))
    return run


async def handle_step(session: AsyncSession, event: OutboxEvent, ctx: outbox.JobContext) -> None:
    run = await session.get(AgentRun, uuid.UUID(event.payload["run_id"]))
    if run is None or run.state not in ACTIVE or run.step != event.payload["step"]:
        return  # cancelled, finished or a duplicate delivery of a completed step
    assert ctx.settings is not None
    steps: list[str] = run.checkpoint.get("steps", [])
    if run.step >= len(steps):
        finish(run, settled_state(run))
        return
    started = run.started_at or run.created_at
    if _now() - started > RUN_TIME_LIMIT:
        finish(run, "timed_out", "run_time_limit")
        return
    name = steps[run.step]
    spec = capability(name)
    if not await ai_enabled(session, name):
        _event(session, run, name, "skipped_disabled")
    elif await monthly_tokens_left(session, ctx.settings) < spec.token_budget:
        _event(session, run, name, "monthly_budget_exhausted", "warning")
        _mark_failed(run, name)
    else:
        pool, ids = await load_pool(session, run)
        audience = str(run.checkpoint.get("audience", "managers"))
        pool = pool.for_audience(audience)
        kind = STEP_KINDS.get(name, ANALYSIS_KIND)
        try:
            result = await gateway_for(ctx.settings).run(
                instructions=caps.instructions(name),
                prompt=caps.prompt(pool, audience, await _brief(session, run)),
                output_type=kind.output_type,
                tools=[caps.TOOLS[t] for t in spec.tools],
                deps=pool,
                token_budget=spec.token_budget,
                time_limit=spec.timeout_seconds,
            )
        except LLMError as error:
            await session.refresh(run, ["state", "cancel_requested"])
            if run.cancel_requested:
                return
            _event(session, run, name, error.code, "error")
            if error.code == "timeout":
                finish(run, "timed_out", error.code)
                return
            _mark_failed(run, name, error.code)
        else:
            await session.refresh(run, ["state", "cancel_requested"])
            if run.cancel_requested:
                return  # cancelled while the model was answering: discard the output
            record_usage(run, result)
            counts = await kind.store(session, run, name, result.output, pool, ids)
            _event(
                session,
                run,
                name,
                "step_completed",
                tokens=result.input_tokens + result.output_tokens,
                tool_calls=list(result.tool_calls),
                **counts,
            )
    run.step += 1
    if run.step < len(steps) and ctx.jobs is not None:
        await _queue(session, ctx.jobs, run)
    else:
        failed = run.checkpoint.get("failed_steps", [])
        all_failed = failed and len(failed) == len(steps)
        finish(run, "failed" if all_failed else settled_state(run))


async def _store_analysis(
    session: AsyncSession,
    run: AgentRun,
    name: str,
    output: caps.AnalysisOutput,
    pool: Pool,
    ids: dict[str, uuid.UUID],
) -> dict[str, int]:
    existing = {
        normalise(t)
        for t in await session.scalars(select(Claim.text).where(Claim.run_id == run.id))
    }
    outcome = validate_claims(pool, output.claims[: caps.MAX_CLAIMS], existing)
    store_claims(session, run, name, outcome.claims, ids)
    counts = await store_proposals(
        session, run, name, output.proposals[: caps.MAX_PROPOSALS], pool, ids
    )
    if outcome.rejected.get("unknown_citation"):
        run.checkpoint = {**run.checkpoint, "suspicious": True}
    return {
        "claims": len(outcome.claims),
        "rejected": sum(outcome.rejected.values()),
        "proposals": counts["kept"],
        "suppressed": counts["suppressed"],
    }


@dataclass(frozen=True)
class StepKind:
    """How one AI step's typed output is validated and stored."""

    output_type: type[BaseModel]
    store: Callable[..., Awaitable[dict[str, int]]]


ANALYSIS_KIND = StepKind(caps.AnalysisOutput, _store_analysis)
# Other capabilities (interviews, capsules) register their own kinds at import time.
STEP_KINDS: dict[str, StepKind] = {}


async def _brief(session: AsyncSession, run: AgentRun) -> str:
    """Extra context: what earlier steps already recorded, so the model adds, not repeats."""
    known = list(
        await session.scalars(
            select(Claim.text).where(Claim.run_id == run.id).order_by(Claim.created_at).limit(40)
        )
    )
    brief = str(run.checkpoint.get("brief", ""))
    if known:
        lines = [f"- {t[:200]}" for t in known]
        brief = "\n".join(
            [brief, "Already recorded (do not repeat these; add only new, cited points):", *lines]
        )
    return brief


def _mark_failed(run: AgentRun, name: str, code: str | None = None) -> None:
    failed = [*run.checkpoint.get("failed_steps", []), name]
    run.checkpoint = {**run.checkpoint, "failed_steps": failed}
    if code:
        run.error_code = code


outbox.register(STEP_EVENT, handle_step, serial="ai")
