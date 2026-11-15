"""Case status model: the allowed transitions, and the single place a status changes.

    draft / investigating / awaiting_input / reopened      (intake: scope is being found)
        --submit-->  planning  <-->  awaiting_review
        --approve--> ready_for_transfer
        --execute--> executing  <-->  verification
        --complete-> completed            (any open status --cancel--> cancelled)

- `blocked` can be entered from any open status (a blocker was raised) and only leads back
  to the status it was entered from (`blocked_from`) or to cancelled.
- `completed` / `cancelled` only lead to `reopened`; the closure (outcome, closed time)
  stays on the status-change row that recorded it.
- Gated moves (submit, approve, execute, complete, cancel, block, reopen) have their own
  commands with their own checks; `MANUAL` lists the moves a manager may make directly.
"""

from typing import Final

from relay.continuity.models import CaseStatusChange, ContinuityCase
from relay.identity.workspace_access import WorkspaceAccess
from relay.shared.errors import ApiError

INTAKE: Final = ("draft", "investigating", "awaiting_input", "reopened")
EDITABLE: Final = (*INTAKE, "planning", "awaiting_review", "ready_for_transfer")
APPROVABLE: Final = ("planning", "awaiting_review")
EXECUTABLE: Final = ("planning", "awaiting_review", "ready_for_transfer")
RUNNING: Final = ("executing", "verification")
CLOSED: Final = ("completed", "cancelled")

TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "draft": frozenset({"investigating", "awaiting_input", "planning"}),
    "investigating": frozenset({"awaiting_input", "planning"}),
    "awaiting_input": frozenset({"investigating", "planning"}),
    "reopened": frozenset({"investigating", "awaiting_input", "planning"}),
    "planning": frozenset({"awaiting_input", "awaiting_review", "ready_for_transfer", "executing"}),
    "awaiting_review": frozenset({"planning", "ready_for_transfer", "executing"}),
    "ready_for_transfer": frozenset({"planning", "executing"}),
    "executing": frozenset({"verification", "completed"}),
    "verification": frozenset({"executing", "completed"}),
    "completed": frozenset({"reopened"}),
    "cancelled": frozenset({"reopened"}),
}
MANUAL: Final[dict[str, frozenset[str]]] = {
    "draft": frozenset({"investigating", "awaiting_input"}),
    "investigating": frozenset({"awaiting_input"}),
    "awaiting_input": frozenset({"investigating"}),
    "reopened": frozenset({"investigating", "awaiting_input"}),
    "planning": frozenset({"awaiting_input", "awaiting_review"}),
    "awaiting_review": frozenset({"planning"}),
    "ready_for_transfer": frozenset({"planning"}),
    "executing": frozenset({"verification"}),
    "verification": frozenset({"executing"}),
}


def allowed(case: ContinuityCase, to: str) -> bool:
    if case.status == "blocked":
        return to in (case.blocked_from, "cancelled")
    if to == "cancelled":
        return case.status not in ("completed", "cancelled", *RUNNING)
    if to == "blocked":
        return case.status not in ("completed", "cancelled")
    return to in TRANSITIONS.get(case.status, frozenset())


def move(access: WorkspaceAccess, case: ContinuityCase, to: str, reason: str | None = None) -> None:
    """Change the status (caller holds the case row lock) and record who, when and why."""
    if not allowed(case, to):
        raise ApiError(409, "invalid_transition", f"A case can't move from {case.status} to {to}.")
    closure = case.status in ("completed", "cancelled")
    access.session.add(
        CaseStatusChange(
            tenant_id=access.tenant_id,
            case_id=case.id,
            from_status=case.status,
            to_status=to,
            reason=reason,
            # Reopening keeps the closure it replaces on record.
            outcome=case.outcome if closure else None,
            closed_at=case.closed_at if closure else None,
            actor_user_id=access.user_id,
        )
    )
    case.blocked_from = case.status if to == "blocked" else None
    case.status = to


def record_created(access: WorkspaceAccess, case: ContinuityCase, reason: str) -> None:
    access.session.add(
        CaseStatusChange(
            tenant_id=access.tenant_id,
            case_id=case.id,
            to_status=case.status,
            reason=reason,
            actor_user_id=access.user_id,
        )
    )
