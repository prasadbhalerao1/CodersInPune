"""Return briefing for temporary coverage, assembled from recorded Relay data only.

For someone coming back: what was covered and by whom, what changed on those
responsibilities while they were away, what work happened, what people wrote down, and
whether ownership is back to normal. Deterministic; no generated text.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select

from relay.audit.models import AuditEvent
from relay.catalog import service as catalog
from relay.catalog.models import OwnershipAssignment, OwnershipAssignmentChange, Responsibility
from relay.continuity.collaboration import ActivityView, case_activity
from relay.continuity.models import CaseScopeItem, CaseTask, ContinuityCase
from relay.directory.models import Person
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.errors import ApiError

Restoration = Literal["not_started", "covering", "restored", "excepted"]


class BriefingItemView(BaseModel):
    responsibility_id: uuid.UUID
    responsibility_name: str
    criticality: str
    covered_by: str | None
    cover_ends_at: datetime | None
    restoration: Restoration
    original_owner_active: bool
    handover_notes: str | None
    exception_reason: str | None


class BriefingChangeView(BaseModel):
    changed_at: datetime
    responsibility_name: str
    change_type: str
    role: str
    assignee_name: str
    reason: str | None


class BriefingEventView(BaseModel):
    occurred_at: datetime
    responsibility_name: str
    action: str
    actor_name: str | None


class BriefingTaskView(BaseModel):
    title: str
    status: str
    assignee_name: str | None
    completed_at: datetime | None


class BriefingView(BaseModel):
    case_id: uuid.UUID
    title: str
    person_name: str | None
    period_start: datetime
    period_end: datetime
    returned: bool
    items: list[BriefingItemView]
    ownership_changes: list[BriefingChangeView]
    responsibility_events: list[BriefingEventView]
    tasks: list[BriefingTaskView]
    notes: list[ActivityView]


async def return_briefing(access: WorkspaceAccess, case_id: uuid.UUID) -> BriefingView:
    authorize(access, Permission.CASE_READ)
    session = access.session
    case = await session.scalar(
        select(ContinuityCase).where(
            ContinuityCase.id == case_id,
            visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
        )
    )
    if case is None:
        raise ApiError(404, "case_not_found", "Case not found.")
    if case.case_type != "coverage" or case.ends_at is None:
        raise ApiError(422, "not_coverage", "Return briefings exist for coverage cases only.")
    now = datetime.now(UTC)
    start, end = case.starts_at, min(case.ends_at, now)

    items = list(
        await session.scalars(
            select(CaseScopeItem)
            .where(CaseScopeItem.case_id == case.id)
            .order_by(CaseScopeItem.created_at)
        )
    )
    responsibility_ids = [i.responsibility_id for i in items]
    responsibilities = {
        r.id: r
        for r in await session.scalars(
            select(Responsibility).where(
                Responsibility.id.in_(responsibility_ids),
                visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
            )
        )
    }
    assignment_ids = [
        a for i in items for a in (i.applied_assignment_id, i.current_assignment_id) if a
    ]
    assignments = {
        a.id: a
        for a in await session.scalars(
            select(OwnershipAssignment).where(OwnershipAssignment.id.in_(assignment_ids))
        )
    }
    changes = (
        await session.execute(
            select(OwnershipAssignmentChange, OwnershipAssignment)
            .join(
                OwnershipAssignment,
                OwnershipAssignment.id == OwnershipAssignmentChange.assignment_id,
            )
            .where(
                OwnershipAssignmentChange.responsibility_id.in_(responsibility_ids),
                OwnershipAssignmentChange.changed_at >= start,
                OwnershipAssignmentChange.changed_at <= end,
                visible(
                    access, Permission.RESPONSIBILITY_READ, OwnershipAssignmentChange.tenant_id
                ),
            )
            .order_by(OwnershipAssignmentChange.changed_at)
        )
    ).all()
    assignees = await catalog.assignee_views(
        session, [*assignments.values(), *(a for _, a in changes)]
    )
    names = {
        user_id: name or email or "Member"
        for user_id, name, email in await session.execute(
            select(Membership.user_id, Membership.display_name, Membership.email).where(
                visible(access, Permission.MEMBER_READ, Membership.tenant_id)
            )
        )
    }
    events = await session.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.target_type == "responsibility",
            AuditEvent.target_id.in_(responsibility_ids),
            AuditEvent.occurred_at >= start,
            AuditEvent.occurred_at <= end,
            visible(access, Permission.CASE_READ, AuditEvent.tenant_id),
        )
        .order_by(AuditEvent.occurred_at)
    )
    tasks = await session.scalars(
        select(CaseTask).where(CaseTask.case_id == case.id).order_by(CaseTask.created_at)
    )
    person = await session.get(Person, case.affected_person_id) if case.affected_person_id else None

    def holder(assignment_id: uuid.UUID | None) -> OwnershipAssignment | None:
        return assignments.get(assignment_id) if assignment_id else None

    def is_active(a: OwnershipAssignment | None) -> bool:
        return a is not None and a.valid_from <= now and (a.valid_to is None or a.valid_to > now)

    def restoration(i: CaseScopeItem, cover: OwnershipAssignment | None) -> Restoration:
        if i.state == "excepted":
            return "excepted"
        if cover is None:
            return "not_started"
        return "covering" if is_active(cover) else "restored"

    briefing_items = []
    for i in items:
        cover = holder(i.applied_assignment_id)
        r = responsibilities.get(i.responsibility_id)
        briefing_items.append(
            BriefingItemView(
                responsibility_id=i.responsibility_id,
                responsibility_name=r.name if r else "Restricted responsibility",
                criticality=r.criticality if r else "standard",
                covered_by=assignees[cover.person_id or cover.team_id].name if cover else None,  # type: ignore[index]
                cover_ends_at=cover.valid_to if cover else None,
                restoration=restoration(i, cover),
                original_owner_active=is_active(holder(i.current_assignment_id)),
                handover_notes=i.handover_notes,
                exception_reason=i.exception_reason,
            )
        )
    notes = [
        a
        for a in await case_activity(access, case.id)
        if a.kind == "comment" and start <= a.occurred_at <= end
    ]
    return BriefingView(
        case_id=case.id,
        title=case.title,
        person_name=person.display_name if person else None,
        period_start=start,
        period_end=case.ends_at,
        returned=case.ends_at <= now or case.status == "completed",
        items=briefing_items,
        ownership_changes=[
            BriefingChangeView(
                changed_at=c.changed_at,
                responsibility_name=responsibilities[c.responsibility_id].name
                if c.responsibility_id in responsibilities
                else "Restricted responsibility",
                change_type=c.change_type,
                role=a.role,
                assignee_name=assignees[a.person_id or a.team_id].name,  # type: ignore[index]
                reason=c.reason,
            )
            for c, a in changes
        ],
        responsibility_events=[
            BriefingEventView(
                occurred_at=e.occurred_at,
                responsibility_name=responsibilities[e.target_id].name,
                action=e.action,
                actor_name=names.get(e.actor_user_id) if e.actor_user_id else "Relay",
            )
            for e in events
            if e.target_id in responsibilities
        ],
        tasks=[
            BriefingTaskView(
                title=t.title,
                status=t.status,
                assignee_name=names.get(t.assignee_user_id) if t.assignee_user_id else None,
                completed_at=t.completed_at,
            )
            for t in tasks
        ],
        notes=sorted(notes, key=lambda a: a.occurred_at),
    )
