"""Interactive AI calls: one model call inside the request, recorded as an agent run.

The handover copilot and the memory narrator answer while the person waits, so they don't
go through the queued run engine. They still honour the same controls (workspace kill
switch, per-capability toggle, monthly token budget), use the same read-only tools over
an in-memory evidence pool, and leave an `agent_run` row with usage and outcome so cost
and failures show on the AI administration page. Prompts and outputs are not stored here.
"""

import uuid
from dataclasses import dataclass

from relay.config import Settings
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import capabilities as caps
from relay.intelligence import runs
from relay.intelligence.evidence import Pool
from relay.intelligence.llm import LLMError
from relay.intelligence.models import AgentRun
from relay.intelligence.registry import capability

# Why there was no model answer, in words a person can act on.
REASONS = {
    "ai_not_configured": "AI is not configured on this server.",
    "ai_disabled": "AI is switched off for this workspace or this feature.",
    "monthly_budget_exhausted": "This workspace has used its monthly AI budget.",
    "timeout": "The AI provider took too long to answer.",
    "quota_exhausted": "The AI provider is rate-limiting requests; try again in a minute.",
}
DEFAULT_REASON = "The AI provider could not answer just now."


@dataclass
class Outcome[T]:
    output: T | None
    run_id: uuid.UUID | None
    reason: str | None  # code, set when output is None

    @property
    def message(self) -> str | None:
        return REASONS.get(self.reason or "", DEFAULT_REASON) if self.reason else None


async def call[T](
    access: WorkspaceAccess,
    settings: Settings,
    *,
    name: str,
    pool: Pool,
    extra: str,
    output_type: type[T],
    case_id: uuid.UUID | None = None,
) -> Outcome[T]:
    spec = capability(name)
    session = access.session
    gateway = runs.gateway_for(settings)
    if not gateway.configured:
        return Outcome(None, None, "ai_not_configured")
    if not await runs.ai_enabled(session, name):
        return Outcome(None, None, "ai_disabled")
    if await runs.monthly_tokens_left(session, settings) < spec.token_budget:
        return Outcome(None, None, "monthly_budget_exhausted")
    run = AgentRun(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        capability=name,
        capability_version=spec.version,
        case_id=case_id,
        requested_by=access.user_id,
        state="running",
        input_hash=pool.input_hash(),
        checkpoint={"steps": [name], "ai": "on", "interactive": True, "evidence": len(pool.items)},
        started_at=runs._now(),
    )
    session.add(run)
    await session.flush()
    try:
        result = await gateway.run(
            instructions=caps.instructions(name),
            prompt=caps.prompt(pool, "managers", extra),
            output_type=output_type,
            tools=[caps.TOOLS[t] for t in spec.tools],
            deps=pool,
            token_budget=spec.token_budget,
            time_limit=spec.timeout_seconds,
        )
    except LLMError as error:
        runs.finish(run, "timed_out" if error.code == "timeout" else "failed", error.code)
        await session.flush()
        return Outcome(None, run.id, error.code)
    runs.record_usage(run, result)
    runs.finish(run, "completed")
    run.step = 1
    await session.flush()
    return Outcome(result.output, run.id, None)
