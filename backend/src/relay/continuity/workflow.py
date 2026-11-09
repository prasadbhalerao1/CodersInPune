"""Case coordination around the core engine: manual moves, blockers, reopening, declines,
participants, departure splits and saved list views.

Every status change goes through `lifecycle.move`; every command here is authorised inside
the service and audited in the same transaction.
"""

import uuid
from datetime import datetime, timedelta
from typing import Literal

import procrastinate
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import delete, func, select, update

from relay.continuity import lifecycle
from relay.continuity import service as cases
from relay.continuity.models import (
    CaseBlocker,
    CaseParticipant,
    CaseReadinessCriterion,
    CaseScopeItem,
    CaseTask,
    ContinuityCase,
)
from relay.directory.models import Person
from relay.governance.models import SavedView
from relay.identity.workspace_access import WorkspaceAccess
from relay.notifications import service as notifications
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import LongText, Name, StrictInput
from relay.shared.errors import ApiError

# How long a blocker may sit before it is escalated, by case priority.
ESCALATE_AFTER = {
    "urgent": timedelta(hours=4),
    "high": timedelta(hours=24),
    "normal": timedelta(hours=72),
    "low": timedelta(days=7),
}
ManualStatus = Literal[
    "investigating", "awaiting_input", "planning", "awaiting_review", "executing", "verification"
]


class TransitionIn(StrictInput):
    to: ManualStatus
    reason: LongText | None = None


class ReasonIn(StrictInput):
    reason: LongText


class BlockerIn(StrictInput):
    description: LongText
    owner_user_id: uuid.UUID | None = None
    escalate_at: AwareDatetime | None = None


class ResolveBlockerIn(StrictInput):
    resolution: LongText


class ParticipantIn(StrictInput):
    user_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    role: Literal["approver", "verifier", "reviewer", "contributor", "observer"]
    why: Name


class ParticipantView(BaseModel):
    """Everyone involved, derived from the case plus explicit additions, with why."""

    key: str
    kind: Literal["user", "person"]
    subject_id: uuid.UUID
    name: str
    roles: list[str]
    why: list[str]
    participant_ids: list[uuid.UUID]


class SavedViewIn(StrictInput):
    page: Literal["cases", "responsibilities", "assets", "knowledge"]
    name: Name
    query: LongText


class SavedViewView(BaseModel):
    id: uuid.UUID
    page: str
    name: str
    query: str
    created_at: datetime


# ---------------------------------------------------------------- status


async def transition(
    access: WorkspaceAccess, case_id: uuid.UUID, data: TransitionIn
) -> cases.CaseDetail:
    case = await cases._for_change(access, case_id, cases.OPEN)
    if data.to not in lifecycle.MANUAL.get(case.status, frozenset()):
        raise ApiError(
            409,
            "invalid_transition",
            f"Move from {case.status} to {data.to} with its own action (submit, approve, "
            "execute or complete), not directly.",
        )
    lifecycle.move(access, case, data.to, data.reason or None)
    cases._record(access, case, "case.status_changed", to=data.to)
    return await cases.get_case(access, case_id)


async def reopen(
    access: WorkspaceAccess, case_id: uuid.UUID, data: ReasonIn, jobs: procrastinate.App
) -> cases.CaseDetail:
    """The closure stays on the status history; ownership already applied is not undone."""
    case = await cases._for_change(access, case_id, ("completed", "cancelled"))
    lifecycle.move(access, case, "reopened", data.reason)
    case.outcome, case.closed_at = None, None
    case.reopen_count += 1
    cases._record(access, case, "case.reopened", reopen_count=case.reopen_count)
    await cases._notify_case_update(access, jobs, case, "reopened")
    return await cases.get_case(access, case_id)


# ---------------------------------------------------------------- blockers


async def add_blocker(
    access: WorkspaceAccess, case_id: uuid.UUID, data: BlockerIn, jobs: procrastinate.App
) -> cases.CaseDetail:
    case = await cases._for_change(access, case_id, cases.OPEN)
    await cases._require_active_member(access, data.owner_user_id, "blocker owner")
    escalate_at = data.escalate_at or cases._now() + ESCALATE_AFTER[case.priority]
    blocker = CaseBlocker(
        tenant_id=access.tenant_id,
        case_id=case_id,
        description=data.description,
        owner_user_id=data.owner_user_id,
        escalate_at=escalate_at,
        created_by=access.user_id,
    )
    access.session.add(blocker)
    await access.session.flush()
    if case.status != "blocked":
        lifecycle.move(access, case, "blocked", data.description[:200])
    cases._record(access, case, "case.blocker_added", blocker_id=str(blocker.id))
    await notifications.request_blocker_escalation(
        access.session, jobs, case, blocker, access.user_id
    )
    return await cases.get_case(access, case_id)


async def resolve_blocker(
    access: WorkspaceAccess, case_id: uuid.UUID, blocker_id: uuid.UUID, data: ResolveBlockerIn
) -> cases.CaseDetail:
    case = await cases._for_change(access, case_id, cases.OPEN)
    blocker = await access.session.get(CaseBlocker, blocker_id, with_for_update=True)
    if blocker is None or blocker.case_id != case_id:
        raise ApiError(404, "blocker_not_found", "Blocker not found.")
    if blocker.resolved_at is not None:
        raise ApiError(409, "already_resolved", "That blocker is already resolved.")
    blocker.resolution, blocker.resolved_by, blocker.resolved_at = (
        data.resolution,
        access.user_id,
        func.now(),
    )
    await access.session.flush()
    remaining = await access.session.scalar(
        select(func.count())
        .select_from(CaseBlocker)
        .where(CaseBlocker.case_id == case_id, CaseBlocker.resolved_at.is_(None))
    )
    if not remaining and case.status == "blocked" and case.blocked_from:
        lifecycle.move(access, case, case.blocked_from, "Every blocker resolved")
    cases._record(access, case, "case.blocker_resolved", blocker_id=str(blocker_id))
    return await cases.get_case(access, case_id)


# ---------------------------------------------------------------- incoming owner


async def decline(
    access: WorkspaceAccess,
    case_id: uuid.UUID,
    item_id: uuid.UUID,
    data: ReasonIn,
    jobs: procrastinate.App,
) -> cases.CaseDetail:
    """The incoming person declines: the assignment decision is open again."""
    authorize(access, Permission.CASE_READ)
    case = await cases._load(access, case_id, lock=True)
    if case.status not in cases.EDITABLE:
        raise ApiError(409, "invalid_state", "The plan can no longer change.")
    item = await access.session.get(CaseScopeItem, item_id, with_for_update=True)
    if item is None or item.case_id != case_id:
        raise ApiError(404, "scope_item_not_found", "Scope item not found.")
    if item.recipient_person_id is None or item.recipient_person_id not in (
        await cases.my_person_ids(access)
    ):
        raise ApiError(403, "not_recipient", "Only the incoming person can decline.")
    item.recipient_person_id = None
    item.declined_at, item.declined_by, item.decline_reason = (
        func.now(),
        access.user_id,
        data.reason,
    )
    cases._plan_changed(access, case)
    cases._record(access, case, "case.assignment_declined", scope_item_id=str(item_id))
    await cases._notify_case_update(access, jobs, case, "declined")
    return await cases.get_case(access, case_id)


# ---------------------------------------------------------------- departure split


async def split(
    access: WorkspaceAccess, case_id: uuid.UUID, item_ids: list[uuid.UUID]
) -> cases.CaseDetail:
    """Move responsibilities out of a departure into child transfer cases, one each, so
    they can be planned, approved and executed independently."""
    case = await cases._for_change(access, case_id, cases.EDITABLE)
    if case.case_type != "departure":
        raise ApiError(409, "not_departure", "Only departures can be split.")
    items = [
        i
        for i in await cases._scope(access.session, case_id)
        if i.id in set(item_ids) and i.state == "planned"
    ]
    if not items:
        raise ApiError(422, "nothing_to_split", "Choose planned responsibilities to split off.")
    names = await cases.responsibility_names(access, [i.responsibility_id for i in items])
    for item in items:
        child = ContinuityCase(
            id=uuid.uuid7(),
            tenant_id=access.tenant_id,
            case_type="transfer",
            status="draft",
            title=f"{names.get(item.responsibility_id, 'Responsibility')} — {case.title}"[:200],
            reason=case.reason,
            affected_person_id=case.affected_person_id,
            starts_at=case.starts_at,
            priority=case.priority,
            due_at=case.due_at,
            time_zone=case.time_zone,
            accountable_manager_user_id=case.accountable_manager_user_id,
            parent_case_id=case.id,
            initiator_user_id=access.user_id,
            coordinator_user_id=access.user_id,
        )
        access.session.add(child)
        await access.session.flush()
        lifecycle.record_created(access, child, f"Split from “{case.title}”")
        # Criteria and tasks belong to the item; they follow it to the child case.
        await access.session.execute(
            update(CaseReadinessCriterion)
            .where(CaseReadinessCriterion.scope_item_id == item.id)
            .values(case_id=child.id)
        )
        await access.session.execute(
            update(CaseTask).where(CaseTask.scope_item_id == item.id).values(case_id=child.id)
        )
        item.case_id = child.id
        cases._record(access, child, "case.created", case_type="transfer", split_from=str(case.id))
    cases._plan_changed(access, case)
    cases._record(access, case, "case.split", children=len(items))
    return await cases.get_case(access, case_id)


# ---------------------------------------------------------------- participants


async def participants(access: WorkspaceAccess, case_id: uuid.UUID) -> list[ParticipantView]:
    detail = await cases.get_case(access, case_id)
    case = await cases._load(access, case_id)
    names = await cases._member_names(access)
    found: dict[str, ParticipantView] = {}

    def add(
        kind: Literal["user", "person"],
        subject: uuid.UUID | None,
        name: str | None,
        role: str,
        why: str,
        participant_id: uuid.UUID | None = None,
    ) -> None:
        if subject is None:
            return
        key = f"{kind}:{subject}"
        view = found.setdefault(
            key,
            ParticipantView(
                key=key,
                kind=kind,
                subject_id=subject,
                name=name or "Unknown",
                roles=[],
                why=[],
                participant_ids=[],
            ),
        )
        if role not in view.roles:
            view.roles.append(role)
        if why not in view.why:
            view.why.append(why)
        if participant_id:
            view.participant_ids.append(participant_id)

    add(
        "user",
        case.initiator_user_id,
        names.get(case.initiator_user_id),
        "initiator",
        "Started the case",
    )
    add(
        "user",
        case.coordinator_user_id,
        names.get(case.coordinator_user_id),
        "coordinator",
        "Coordinates the case",
    )
    if case.accountable_manager_user_id:
        add(
            "user",
            case.accountable_manager_user_id,
            detail.accountable_manager_name,
            "accountable_manager",
            "Accountable for the outcome",
        )
    if case.delegate_approver_user_id:
        add(
            "user",
            case.delegate_approver_user_id,
            detail.delegate_approver_name,
            "approver",
            "Delegated approver for this case",
        )
    if case.affected_person_id:
        why = {
            "departure": "Leaving; hands over what they hold",
            "coverage": "Away; their responsibilities are covered",
            "onboarding": "Joining; receives the responsibilities in scope",
        }.get(case.case_type, "Outgoing owner")
        role = "incoming" if case.case_type == "onboarding" else "outgoing"
        add("person", case.affected_person_id, detail.affected_person_name, role, why)
    for item in detail.scope:
        if item.recipient and item.recipient.type == "person":
            add(
                "person",
                item.recipient.id,
                item.recipient.name,
                "incoming",
                f"Receives “{item.responsibility_name}”",
            )
    for approval in detail.approvals:
        add(
            "user",
            approval.approver_user_id,
            approval.approver_name,
            "approver",
            f"{approval.decision.capitalize()} plan v{approval.plan_version}",
        )
    for task in detail.tasks:
        if task.assignee_user_id and task.status != "cancelled":
            add(
                "user", task.assignee_user_id, task.assignee_name, "assignee", f"Task: {task.title}"
            )
    explicit = list(
        await access.session.scalars(
            select(CaseParticipant)
            .where(CaseParticipant.case_id == case_id)
            .order_by(CaseParticipant.added_at)
        )
    )
    people = dict(
        (
            await access.session.execute(
                select(Person.id, Person.display_name).where(
                    Person.id.in_([p.person_id for p in explicit if p.person_id])
                )
            )
        ).all()
    )
    for p in explicit:
        if p.user_id:
            add("user", p.user_id, names.get(p.user_id), p.role, p.why, p.id)
        else:
            add("person", p.person_id, people.get(p.person_id), p.role, p.why, p.id)  # type: ignore[arg-type]
    return list(found.values())


async def add_participant(
    access: WorkspaceAccess, case_id: uuid.UUID, data: ParticipantIn
) -> list[ParticipantView]:
    case = await cases._for_change(access, case_id, (*cases.OPEN, *lifecycle.CLOSED))
    if (data.user_id is None) == (data.person_id is None):
        raise ApiError(422, "one_subject", "Choose a member or a person.")
    await cases._require_active_member(access, data.user_id, "participant")
    if data.person_id is not None:
        person = await access.session.scalar(
            select(Person.id).where(
                Person.id == data.person_id,
                visible(access, Permission.DIRECTORY_READ, Person.tenant_id),
            )
        )
        if person is None:
            raise ApiError(422, "person_not_found", "That person does not exist.")
    access.session.add(
        CaseParticipant(
            tenant_id=access.tenant_id,
            case_id=case_id,
            user_id=data.user_id,
            person_id=data.person_id,
            role=data.role,
            why=data.why,
            added_by=access.user_id,
        )
    )
    cases._record(access, case, "case.participant_added", role=data.role)
    return await participants(access, case_id)


async def remove_participant(
    access: WorkspaceAccess, case_id: uuid.UUID, participant_id: uuid.UUID
) -> list[ParticipantView]:
    case = await cases._for_change(access, case_id, (*cases.OPEN, *lifecycle.CLOSED))
    removed = await access.session.execute(
        delete(CaseParticipant).where(
            CaseParticipant.id == participant_id, CaseParticipant.case_id == case_id
        )
    )
    if not removed.rowcount:  # type: ignore[attr-defined]
        raise ApiError(404, "participant_not_found", "Participant not found.")
    cases._record(access, case, "case.participant_removed")
    return await participants(access, case_id)


# ---------------------------------------------------------------- saved views


async def saved_views(access: WorkspaceAccess, page: str) -> list[SavedViewView]:
    rows = await access.session.scalars(
        select(SavedView)
        .where(SavedView.user_id == access.user_id, SavedView.page == page)
        .order_by(SavedView.name)
    )
    return [SavedViewView.model_validate(r, from_attributes=True) for r in rows]


async def save_view(access: WorkspaceAccess, data: SavedViewIn) -> list[SavedViewView]:
    """Views are personal: only the owner sees or deletes them."""
    exists = await access.session.scalar(
        select(SavedView.id).where(
            SavedView.user_id == access.user_id,
            SavedView.page == data.page,
            SavedView.name == data.name,
        )
    )
    if exists:
        raise ApiError(409, "view_exists", "You already have a view with that name.")
    access.session.add(
        SavedView(
            tenant_id=access.tenant_id,
            user_id=access.user_id,
            page=data.page,
            name=data.name,
            query=data.query.lstrip("?"),
        )
    )
    await access.session.flush()
    return await saved_views(access, data.page)


async def delete_view(access: WorkspaceAccess, view_id: uuid.UUID) -> None:
    removed = await access.session.execute(
        delete(SavedView).where(SavedView.id == view_id, SavedView.user_id == access.user_id)
    )
    if not removed.rowcount:  # type: ignore[attr-defined]
        raise ApiError(404, "view_not_found", "Saved view not found.")
