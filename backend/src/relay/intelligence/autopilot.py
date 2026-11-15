"""Handover Autopilot: one click runs the whole case analysis while the person watches.

It drives the same run engine as the queued analysis (`runs.run_step`), step by step, in
the request, streaming each step as server-sent events: the case it read, the evidence it
gathered, the rule-based findings, each AI reviewer with the evidence tools it called, and
the interview and brief it queued. Nothing is applied: every change it suggests lands as a
pending proposal a person accepts or rejects (guardrail 9).
"""

import json
import uuid
from collections import Counter
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any

import procrastinate
from pydantic import BaseModel
from sqlalchemy import select

from relay.config import Settings
from relay.continuity import service as continuity
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import capsules, interviews, runs
from relay.intelligence import service as svc
from relay.intelligence.models import AgentRun, AgentRunEvent, Claim
from relay.intelligence.registry import capability
from relay.policy.permissions import Permission, authorize
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

Reopen = Callable[[], AbstractAsyncContextManager[WorkspaceAccess]]

AI_REASONS = {
    "off": "AI is switched off for this workspace, so the rule-based findings above stand alone.",
    "not_configured": "No AI provider is configured, so the rule-based findings above stand alone.",
}


class AutopilotIn(StrictInput):
    # Who the handover brief is for. Without one, Autopilot stops before drafting the brief.
    recipient_user_id: uuid.UUID | None = None


class Step(BaseModel):
    key: str
    tool: str
    label: str
    status: str  # running | done | skipped | failed
    summary: str = ""
    items: list[str] = []
    calls: dict[str, int] = {}


@dataclass
class _Plan:
    case_id: uuid.UUID
    run_id: uuid.UUID
    steps: list[str]
    recipient: uuid.UUID | None
    opening: list[Step] = field(default_factory=list)


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


async def start(
    access: WorkspaceAccess,
    case_id: uuid.UUID,
    data: AutopilotIn,
    settings: Settings,
    jobs: procrastinate.App,
    reopen: Reopen,
) -> AsyncIterator[str]:
    """Server-sent events: one `step` per tool call (sent as `running`, then settled), then
    `done` with the pending proposals. A run the stream lost (closed tab) is resumed."""
    authorize(access, Permission.AI_RUN)
    case = await continuity._load(access, case_id)
    active = await access.session.scalar(
        select(AgentRun).where(
            AgentRun.case_id == case_id,
            AgentRun.capability == runs.ANALYSIS,
            AgentRun.state.in_(runs.ACTIVE),
        )
    )
    if active is not None and active.checkpoint.get("driver") != "autopilot":
        raise ApiError(
            409, "analysis_running", "An analysis is already running for this case; open it below."
        )
    run = active or await runs.start_analysis(access, case_id, settings, None, driver="autopilot")
    pool, _ = await runs.load_pool(access.session, run)
    sources = Counter(i.source_system for i in pool.items)
    kinds = Counter(i.source_type for i in pool.items)
    findings = list(
        await access.session.scalars(
            select(Claim).where(Claim.run_id == run.id, Claim.capability == "deterministic")
        )
    )
    names = await continuity._member_names(access)
    person = names.get(case.affected_person_id) if case.affected_person_id else None
    plan = _Plan(case_id, run.id, list(run.checkpoint.get("steps", [])), data.recipient_user_id)
    plan.opening = [
        Step(
            key="case",
            tool="get_case",
            label="Read the case",
            status="done",
            summary=f"{case.title}" + (f" · {person}" if person else ""),
            items=[f"{n} {k.replace('_', ' ')}" for k, n in kinds.most_common(6)],
        ),
        Step(
            key="evidence",
            tool="collect_evidence",
            label="Gathered the evidence you can see",
            status="done",
            summary=f"{len(pool.items)} records from {len(sources)} source"
            + ("s" if len(sources) != 1 else ""),
            items=[f"{s}: {n}" for s, n in sources.most_common()]
            + [f"{s} sync was partial" for s in pool.partial_sources],
        ),
        Step(
            key="rules",
            tool="continuity_rules",
            label="Checked continuity rules",
            status="done",
            summary=f"{len(findings)} finding" + ("s" if len(findings) != 1 else ""),
            items=[c.text for c in findings[:6]],
        ),
    ]
    reason = AI_REASONS.get(str(run.checkpoint.get("ai")))
    if reason:
        plan.opening.append(
            Step(key="ai", tool="ai_review", label="AI review", status="skipped", summary=reason)
        )
    return _drive(plan, settings, jobs, reopen)


async def _drive(
    plan: _Plan, settings: Settings, jobs: procrastinate.App, reopen: Reopen
) -> AsyncIterator[str]:
    for step in plan.opening:
        yield _sse("step", step.model_dump())
    try:
        for name in plan.steps:
            spec = capability(name)
            step = Step(key=name, tool=name, label=spec.title, status="running")
            yield _sse("step", step.model_dump())
            async with reopen() as access:
                run = await access.session.get(AgentRun, plan.run_id, with_for_update=True)
                if run is None or run.state not in runs.ACTIVE:
                    break
                if runs.checkpoint_step(run) != name:
                    continue  # done in an earlier, interrupted Autopilot session
                if runs._now() - (run.started_at or run.created_at) > runs.RUN_TIME_LIMIT:
                    runs.finish(run, "timed_out", "run_time_limit")
                    break
                went_on = await runs.run_step(access.session, run, settings)
                await access.session.flush()
                event = await access.session.scalar(
                    select(AgentRunEvent)
                    .where(AgentRunEvent.run_id == run.id, AgentRunEvent.step == name)
                    .order_by(AgentRunEvent.created_at.desc())
                    .limit(1)
                )
                yield _sse("step", _settled(step, event).model_dump())
                if not went_on:
                    break
        async with reopen() as access:
            run = await access.session.get(AgentRun, plan.run_id, with_for_update=True)
            if run is not None and run.state in runs.ACTIVE:
                failed = run.checkpoint.get("failed_steps", [])
                all_failed = bool(failed) and len(failed) == len(plan.steps)
                runs.finish(run, "failed" if all_failed else runs.settled_state(run))
            for extra in await _follow_ups(access, plan, settings, jobs):
                yield _sse("step", extra.model_dump())
            proposals = await svc.case_proposals(access, plan.case_id)
            state = run.state if run else "failed"
        pending = [p for p in proposals if p.status == "pending"]
        yield _sse(
            "done",
            {
                "run_id": str(plan.run_id),
                "state": state,
                "proposals": [
                    {"id": str(p.id), "title": p.title, "type": p.type, "confidence": p.confidence}
                    for p in pending[:12]
                ],
                "pending": len(pending),
            },
        )
    except ApiError as denied:  # e.g. access removed while Autopilot was running
        yield _sse("error", {"message": denied.detail})


def _settled(step: Step, event: AgentRunEvent | None) -> Step:
    if event is None or event.code == "skipped_disabled":
        return step.model_copy(
            update={"status": "skipped", "summary": "Switched off for this workspace."}
        )
    if event.code != "step_completed":
        return step.model_copy(
            update={"status": "failed", "summary": _failure(event.code), "items": []}
        )
    d = event.detail
    calls = Counter(d.get("tool_calls", []))
    parts = [f"{d.get('claims', 0)} cited points", f"{d.get('proposals', 0)} proposals"]
    if d.get("rejected"):
        parts.append(f"{d['rejected']} uncited dropped")
    return step.model_copy(
        update={"status": "done", "summary": " · ".join(parts), "calls": dict(calls)}
    )


def _failure(code: str) -> str:
    return {
        "monthly_budget_exhausted": "Skipped: this month's AI budget is used up.",
        "timeout": "The model took too long; the steps before it are kept.",
        "rate_limited": "The AI provider is busy right now; try again in a minute.",
    }.get(code, "The model could not finish this step; the steps before it are kept.")


async def _follow_ups(
    access: WorkspaceAccess, plan: _Plan, settings: Settings, jobs: procrastinate.App
) -> list[Step]:
    """Queue the exit interview and, given a recipient, the handover brief."""
    out = []
    interview = await interviews.generate(access, plan.case_id, settings, jobs)
    out.append(
        Step(
            key="interview",
            tool="draft_interview",
            label="Drafted exit-interview questions",
            status="done",
            summary="Queued: questions for the gaps only the leaver can fill."
            if interview.state in runs.ACTIVE
            else "Rule-based questions ready.",
        )
    )
    if plan.recipient is not None:
        await capsules.generate(
            access,
            plan.case_id,
            capsules.CapsuleIn(recipient_user_id=plan.recipient),
            settings,
            jobs,
        )
        out.append(
            Step(
                key="brief",
                tool="draft_handover_brief",
                label="Started the handover brief",
                status="done",
                summary="Drafting for the recipient, from the reviewed evidence.",
            )
        )
    return out
