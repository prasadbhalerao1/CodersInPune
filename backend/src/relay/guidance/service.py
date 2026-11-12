"""Product guidance: what a member should learn next, worked out from the workspace itself.

Tours unlock in the order a workspace grows (people → responsibilities → evidence → history
→ simulation → handover → transfer), and only when the records they demonstrate exist.
A provider counts as ready only after its first sync finished and none of its sync jobs
are still queued or retrying: OAuth success alone is not readiness. Turning automatic
guidance off silences prompts, never the tours themselves.
"""

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.catalog.models import KnowledgeItem, OwnershipAssignment, Responsibility
from relay.continuity.models import ContinuityCase
from relay.directory.models import Person
from relay.identity.models import GuidanceState
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations import connectors
from relay.intelligence.models import Capsule, CapsuleAck
from relay.jobs.models import OutboxEvent
from relay.policy.permissions import Permission, authorize, role_allows
from relay.risks.models import RiskRecord
from relay.shared.api_types import StrictInput

TourId = Literal[
    "basics", "ownership", "integrations", "memory_replay", "what_if", "copilot", "recipient",
    "verify",
]  # fmt: skip
TOURS: tuple[TourId, ...] = TourId.__args__  # type: ignore[attr-defined]
IntegrationState = Literal[
    "not_connected", "sync_pending", "syncing", "retrying", "attention", "ready"
]
_SYNC = {
    "github": ("github.sync_requested", "installation_ref"),
    "linear": ("linear.sync_requested", "connection_ref"),
    "notion": ("notion.sync_requested", "connection_ref"),
}
_BROKEN = {
    "revoked",
    "paused",
    "permission_changed",
    "failed",
    "attention_required",
    "rate_limited",
}
_DONE_CASE = ("completed", "completed_with_exceptions")


class IntegrationView(BaseModel):
    provider: str
    state: IntegrationState
    detail: str


class ChecklistItem(BaseModel):
    key: str
    label: str
    essential: bool
    done: bool
    detail: str
    path: str


class TourView(BaseModel):
    id: TourId
    eligible: bool
    reason: str | None  # why it isn't available yet
    path: str | None  # where the tour starts
    completed: bool
    resume_step: int | None


class GuidanceView(BaseModel):
    enabled: bool
    checklist_dismissed: bool
    dismissed: list[str]
    checklist: list[ChecklistItem]
    integrations: list[IntegrationView]
    tours: list[TourView]
    suggested: TourId | None  # the next tour worth offering, only when guidance is on


class GuidanceUpdate(StrictInput):
    enabled: bool | None = None
    complete: TourId | None = None
    dismiss: str | None = Field(default=None, max_length=64, pattern=r"^[a-z0-9_:-]+$")
    progress: tuple[TourId, int] | None = None
    reset: bool = False


async def _state(access: WorkspaceAccess, *, for_update: bool = False) -> GuidanceState | None:
    stmt = select(GuidanceState).where(
        GuidanceState.tenant_id == access.tenant_id, GuidanceState.user_id == access.user_id
    )
    return await access.session.scalar(stmt.with_for_update() if for_update else stmt)


async def _count(session: AsyncSession, model: Any, *where: Any) -> int:
    return int(await session.scalar(select(func.count()).select_from(model).where(*where)) or 0)


async def _integration(session: AsyncSession, provider: str, now: datetime) -> IntegrationView:
    model = connectors.MODELS[provider]
    conn = await session.scalar(
        select(model).where(model.status != "disconnected").order_by(model.created_at.desc())
    )
    if conn is None:
        return IntegrationView(provider=provider, state="not_connected", detail="Not connected.")
    event, ref = _SYNC[provider]
    pending = list(
        await session.scalars(
            select(OutboxEvent.attempts).where(
                OutboxEvent.event_type == event,
                OutboxEvent.payload[ref].astext == str(conn.id),
                OutboxEvent.processed_at.is_(None),
                # periodic reconcile sweeps are scheduled ahead; they aren't work in progress
                OutboxEvent.payload["reconcile"].astext.is_(None),
            )
        )
    )
    first = conn.last_synced_at is None
    if any(a > 0 for a in pending):
        return IntegrationView(
            provider=provider, state="retrying", detail="A sync failed and is being retried."
        )
    if pending:
        detail = "Initial sync is running." if first else "A sync is queued or running."
        return IntegrationView(provider=provider, state="syncing", detail=detail)
    health, advice = connectors._health(conn, [], now)
    if health in _BROKEN:
        return IntegrationView(provider=provider, state="attention", detail=advice)
    if first:
        return IntegrationView(
            provider=provider, state="sync_pending", detail="Connected; the first sync hasn't run."
        )
    return IntegrationView(provider=provider, state="ready", detail="Synced and up to date.")


async def guidance(access: WorkspaceAccess) -> GuidanceView:
    authorize(access, Permission.WORKSPACE_READ)
    session, base = access.session, f"/w/{access.tenant_id}"
    state = await _state(access)
    now = datetime.now(UTC)

    people = await _count(session, Person)
    resp = await session.scalar(
        select(Responsibility.id)
        .where(Responsibility.archived_at.is_(None))
        .order_by((Responsibility.criticality == "critical").desc(), Responsibility.created_at)
        .limit(1)
    )
    owned = await _count(session, OwnershipAssignment, OwnershipAssignment.valid_to.is_(None))
    knowledge = await _count(session, KnowledgeItem)
    risks = await _count(session, RiskRecord)
    integrations = [await _integration(session, p, now) for p in _SYNC]
    ready = [i for i in integrations if i.state == "ready"]
    capsule = await session.scalar(
        select(Capsule)
        .order_by((Capsule.recipient_user_id == access.user_id).desc(), Capsule.created_at.desc())
        .limit(1)
    )
    acked = await session.scalar(
        select(Capsule.id)
        .join(CapsuleAck, CapsuleAck.capsule_id == Capsule.id)
        .where(CapsuleAck.user_id == access.user_id)
        .limit(1)
    )
    done_case = await session.scalar(
        select(ContinuityCase.id).where(ContinuityCase.status.in_(_DONE_CASE)).limit(1)
    )

    checklist = [
        ChecklistItem(key="workspace", label="Workspace configured", essential=True, done=True,
                      detail="Your workspace exists.", path="/settings"),
        ChecklistItem(key="people", label="People and teams added", essential=True,
                      done=people > 0, detail=f"{people} people", path="/people"),
        ChecklistItem(key="responsibilities", label="First responsibilities created",
                      essential=True, done=resp is not None, detail="", path="/responsibilities"),
        ChecklistItem(key="ownership", label="Ownership established", essential=True,
                      done=owned > 0, detail=f"{owned} current assignments",
                      path="/responsibilities"),
        ChecklistItem(key="knowledge", label="Knowledge recorded", essential=True,
                      done=knowledge > 0, detail=f"{knowledge} items", path="/knowledge"),
        *(
            ChecklistItem(key=i.provider, label=f"{i.provider.title()} connected and synced",
                          essential=False, done=i.state == "ready", detail=i.detail,
                          path="/integrations")
            for i in integrations
        ),
        ChecklistItem(key="assessment", label="Initial continuity assessment", essential=True,
                      done=risks > 0 or (owned > 0 and knowledge > 0),
                      detail="Risks are evaluated from ownership and knowledge.", path="/risks"),
    ]  # fmt: skip

    resp_path = f"/responsibilities/{resp}/timeline" if resp else None
    simulate = role_allows(access.role, Permission.CONTINUITY_SIMULATE)
    capsule_path = f"/cases/{capsule.case_id}/capsules/{capsule.id}" if capsule else None
    rules: dict[TourId, tuple[bool, str | None, str | None]] = {
        "basics": (True, None, ""),
        "ownership": (resp is not None, "Create a responsibility first.", "/responsibilities"),
        "integrations": (
            bool(ready),
            "Connect GitHub, Linear or Notion and wait for the first sync to finish.",
            "/integrations",
        ),
        "memory_replay": (
            resp is not None and (knowledge > 0 or bool(ready)),
            "Needs a responsibility with recorded knowledge or synced history.",
            resp_path,
        ),
        "what_if": (
            simulate and owned > 0,
            "Needs ownership records and the owner, admin or continuity manager role."
            if not simulate
            else "Assign owners to responsibilities first.",
            "/simulator",
        ),
        "copilot": (capsule is not None, "Appears once a handover is prepared.", capsule_path),
        "recipient": (acked is not None, "Appears after you acknowledge a handover.", "/my-work"),
        "verify": (done_case is not None, "Appears after a case is executed.", "/cases"),
    }
    completed = set(state.completed if state else [])
    progress = state.progress if state else {}
    tours = [
        TourView(
            id=t,
            eligible=ok,
            reason=None if ok else why,
            path=f"{base}{path}" if ok and path is not None else None,
            completed=t in completed,
            resume_step=progress.get(t),
        )
        for t, (ok, why, path) in rules.items()
    ]
    enabled = state.enabled if state else True
    dismissed = list(state.dismissed if state else [])
    suggested = next(
        (t.id for t in tours if t.eligible and not t.completed and f"tour:{t.id}" not in dismissed),
        None,
    )
    for item in checklist:
        item.path = f"{base}{item.path}"
    return GuidanceView(
        enabled=enabled,
        checklist_dismissed="checklist" in dismissed,
        dismissed=dismissed,
        checklist=checklist,
        integrations=integrations,
        tours=tours,
        suggested=suggested if enabled else None,
    )


async def update(access: WorkspaceAccess, body: GuidanceUpdate) -> GuidanceView:
    authorize(access, Permission.WORKSPACE_READ)
    state = await _state(access, for_update=True)
    if state is None:
        state = GuidanceState(
            id=uuid.uuid7(), tenant_id=access.tenant_id, user_id=access.user_id,
            enabled=True, completed=[], dismissed=[], progress={},
        )  # fmt: skip
        access.session.add(state)
    if body.reset:
        state.completed, state.progress = [], {}
        state.dismissed = [d for d in state.dismissed if not d.startswith("tour:")]
    if body.enabled is not None:
        state.enabled = body.enabled
    if body.complete is not None:
        state.completed = sorted({*state.completed, body.complete})
        state.progress = {k: v for k, v in state.progress.items() if k != body.complete}
    if body.progress is not None:
        tour, step = body.progress
        state.progress = {**state.progress, tour: max(0, min(step, 20))}
    if body.dismiss is not None and body.dismiss not in state.dismissed:
        state.dismissed = [*state.dismissed, body.dismiss][-100:]
    state.updated_at = datetime.now(UTC)
    await access.session.flush()
    return await guidance(access)
