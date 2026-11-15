"""Interactive AI calls: one model call inside the request, recorded as an agent run.

The handover copilot and the memory narrator answer while the person waits, so they don't
go through the queued run engine. They still honour the same controls (workspace kill
switch, per-capability toggle, monthly token budget), use the same read-only tools over
an in-memory evidence pool, and leave an `agent_run` row with usage and outcome so cost
and failures show on the AI administration page. Prompts and outputs are not stored here.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from relay.config import Settings
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import capabilities as caps
from relay.intelligence import runs
from relay.intelligence.evidence import Pool
from relay.intelligence.llm import LLMError, LLMResult
from relay.intelligence.models import AgentRun
from relay.intelligence.registry import capability

# Why there was no model answer, in words a person can act on.
REASONS = {
    "ai_not_configured": "AI is not configured on this server.",
    "ai_disabled": "AI is switched off for this workspace or this feature.",
    "monthly_budget_exhausted": "This workspace has used its monthly AI budget.",
    "timeout": "The AI provider took too long to answer.",
    "quota_exhausted": "The AI provider is rate-limiting requests; try again in a minute.",
    "stream_interrupted": "The answer was cut off before it finished; ask again.",
}
DEFAULT_REASON = "The AI provider could not answer just now."


def reason_text(code: str | None) -> str | None:
    return REASONS.get(code, DEFAULT_REASON) if code else None


@dataclass
class Outcome[T]:
    output: T | None
    run_id: uuid.UUID | None
    reason: str | None  # code, set when output is None

    @property
    def message(self) -> str | None:
        return reason_text(self.reason)


async def unavailable(access: WorkspaceAccess, settings: Settings, name: str) -> str | None:
    """Why the model can't be called right now (a reason code), or None if it can."""
    if not runs.gateway_for(settings).configured:
        return "ai_not_configured"
    if not await runs.ai_enabled(access.session, name):
        return "ai_disabled"
    if await runs.monthly_tokens_left(access.session, settings) < capability(name).token_budget:
        return "monthly_budget_exhausted"
    return None


def start_run(
    access: WorkspaceAccess,
    *,
    name: str,
    pool: Pool,
    case_id: uuid.UUID | None = None,
    checkpoint: dict[str, object] | None = None,
) -> AgentRun:
    run = AgentRun(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        capability=name,
        capability_version=capability(name).version,
        case_id=case_id,
        requested_by=access.user_id,
        state="running",
        input_hash=pool.input_hash(),
        checkpoint={
            "steps": [name],
            "ai": "on",
            "interactive": True,
            "evidence": len(pool.items),
            **(checkpoint or {}),
        },
        started_at=runs._now(),
    )
    access.session.add(run)
    return run


def settle(run: AgentRun, result: LLMResult[Any] | None, error: str | None) -> None:
    if result is None:
        runs.finish(run, "timed_out" if error == "timeout" else "failed", error)
        return
    runs.record_usage(run, result)
    runs.finish(run, "completed")
    run.step = 1


async def call[T](
    access: WorkspaceAccess,
    settings: Settings,
    *,
    name: str,
    pool: Pool,
    extra: str,
    output_type: type[T],
    case_id: uuid.UUID | None = None,
    checkpoint: dict[str, object] | None = None,
) -> Outcome[T]:
    if reason := await unavailable(access, settings, name):
        return Outcome(None, None, reason)
    spec = capability(name)
    run = start_run(access, name=name, pool=pool, case_id=case_id, checkpoint=checkpoint)
    await access.session.flush()
    try:
        result = await runs.gateway_for(settings).run(
            instructions=caps.instructions(name),
            prompt=caps.prompt(pool, "managers", extra),
            output_type=output_type,
            tools=[caps.TOOLS[t] for t in spec.tools],
            deps=pool,
            token_budget=spec.token_budget,
            time_limit=spec.timeout_seconds,
        )
    except LLMError as error:
        settle(run, None, error.code)
        await access.session.flush()
        return Outcome(None, run.id, error.code)
    settle(run, result, None)
    await access.session.flush()
    return Outcome(result.output, run.id, None)


def stream(
    settings: Settings, *, name: str, pool: Pool, extra: str, answer_format: str
) -> AsyncIterator[str | LLMResult[str]]:
    """The model's plain-text answer as it is written (no database access while streaming).

    Call `unavailable` first, in the request's transaction; record the outcome afterwards
    with `start_run` + `settle` in a fresh unit of work.
    """
    spec = capability(name)
    return runs.gateway_for(settings).stream(
        instructions=f"{caps.instructions(name)}\n{answer_format}",
        prompt=caps.prompt(pool, "managers", extra),
        tools=[caps.TOOLS[t] for t in spec.tools],
        deps=pool,
        token_budget=spec.token_budget,
        time_limit=spec.timeout_seconds,
    )
