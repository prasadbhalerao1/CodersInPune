"""Code-defined AI capabilities. Workspaces can switch each off (and AI as a whole).

Every capability is read-only: its tools only read the run's evidence pool, and its
output becomes claims or proposals that people review. Unknown capabilities are refused.
"""

from dataclasses import dataclass
from typing import Final

# The only tools any capability may hold. All are read-only over the evidence pool.
READ_ONLY_TOOLS: Final = frozenset({"search_evidence", "get_evidence"})


@dataclass(frozen=True)
class Capability:
    name: str
    version: int
    title: str
    description: str
    produces: tuple[str, ...]
    tools: tuple[str, ...] = ("search_evidence", "get_evidence")
    timeout_seconds: float = 120.0
    token_budget: int = 60_000


CAPABILITIES: Final = {
    c.name: c
    for c in (
        Capability(
            "continuity_monitor",
            1,
            "Continuity Monitor",
            "Spots continuity risks in a case: missing owners, stale knowledge, open work.",
            ("finding", "missing"),
        ),
        Capability(
            "discovery",
            1,
            "Discovery",
            "Reconstructs project state, decisions and open questions from the evidence.",
            ("finding", "decision", "question", "work"),
        ),
        Capability(
            "impact_analyst",
            1,
            "Impact Analyst",
            "Finds dependencies and conflicts between sources and what breaks if no one acts.",
            ("dependency", "conflict"),
        ),
        Capability(
            "knowledge_steward",
            1,
            "Knowledge Steward",
            "Finds knowledge gaps and drafts knowledge for a person to review.",
            ("missing", "knowledge_draft"),
        ),
        Capability(
            "knowledge_interviewer",
            1,
            "Knowledge Interviewer",
            "Asks the departing owner targeted questions about what the evidence can't answer.",
            ("question",),
        ),
        Capability(
            "handover_planner",
            1,
            "Handover Planner",
            "Proposes tasks and readiness criteria for the handover.",
            ("task", "readiness_criterion", "exception"),
        ),
        Capability(
            "coordination",
            1,
            "Coordination",
            "Drafts messages to the people involved; a person posts them.",
            ("coordination_message",),
        ),
        Capability(
            "readiness_verifier",
            1,
            "Readiness Verifier",
            "Checks readiness criteria against the evidence and flags what is unproven.",
            ("finding", "missing"),
        ),
        Capability(
            "handover_generator",
            1,
            "Handover Generator",
            "Writes a role-specific handover capsule from reviewed, cited claims.",
            ("handover_content",),
            token_budget=80_000,
        ),
    )
}
# One "Analyse case" run: the deterministic step, then these capabilities in order.
ANALYSIS_STEPS: Final = ("discovery", "impact_analyst", "knowledge_steward", "handover_planner")


def capability(name: str) -> Capability:
    try:
        return CAPABILITIES[name]
    except KeyError:
        raise LookupError(f"unknown capability {name!r}") from None
