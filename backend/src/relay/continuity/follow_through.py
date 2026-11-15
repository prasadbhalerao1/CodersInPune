"""Did the handover take hold? A read-only check per responsibility in an executed case.

Verification at completion confirms the plan was applied. This looks afterwards at the
responsibility, not at the person: is the new holder recorded, has the work been reviewed
or shown recorded activity (any source, any actor) since they took it on, and are the
case's tasks for it closed. Nothing here scores or monitors an individual's output.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select

from relay.catalog.models import OwnershipAssignment, Responsibility
from relay.catalog.service import active_at
from relay.catalog.timeline import responsibility_timeline
from relay.continuity import service as cases
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible

# After this long with no review and no recorded activity, the new holder should be asked.
CHECK_IN_AFTER = timedelta(days=14)
EXECUTED = ("executing", "verification", "completed")

FollowState = Literal["not_in_place", "settling", "check_in", "settled"]

RULE = (
    "Settled: the new holder is recorded, the responsibility was reviewed or shows recorded "
    f"activity since they took it on, and the case's tasks for it are closed. Check in: "
    f"{CHECK_IN_AFTER.days} days without a review or any recorded activity, or open tasks "
    "past due. Activity counts events from any source and any person: this checks that the "
    "work is moving, not who did it."
)


class FollowThroughItem(BaseModel):
    scope_item_id: uuid.UUID
    responsibility_id: uuid.UUID
    responsibility_name: str
    criticality: str
    recipient_name: str | None
    state: FollowState
    holder_since: datetime | None
    reviewed_since: bool
    activity_since: int  # recorded events after the handover, ownership changes excluded
    last_activity_at: datetime | None
    open_tasks: int
    overdue_tasks: int


class FollowThroughView(BaseModel):
    applies: bool  # false until the case has been executed
    rule: str = RULE
    settled: int = 0
    items: list[FollowThroughItem] = []


async def case_follow_through(access: WorkspaceAccess, case_id: uuid.UUID) -> FollowThroughView:
    authorize(access, Permission.CASE_READ)
    detail = await cases.get_case(access, case_id)
    if detail.status not in EXECUTED:
        return FollowThroughView(applies=False)
    session, now = access.session, datetime.now(UTC)
    scope = [s for s in detail.scope if not s.hidden and s.recipient is not None]
    rids = [s.responsibility_id for s in scope]
    reviewed_at = dict(
        (
            await session.execute(
                select(Responsibility.id, Responsibility.last_reviewed_at).where(
                    visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
                    Responsibility.id.in_(rids),
                )
            )
        ).all()
    )
    holdings = (
        await session.scalars(
            select(OwnershipAssignment).where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
                OwnershipAssignment.responsibility_id.in_(rids),
                active_at(now),
            )
        )
    ).all()
    items = []
    for s in scope:
        assert s.recipient is not None
        since = min(
            (
                a.valid_from
                for a in holdings
                if a.responsibility_id == s.responsibility_id
                and a.role == s.role
                and s.recipient.id in (a.person_id, a.team_id)
            ),
            default=None,
        )
        tasks = [t for t in detail.tasks if t.scope_item_id == s.id and t.status == "open"]
        overdue = sum(1 for t in tasks if t.overdue)
        activity: list[datetime] = []
        reviewed = False
        if since is not None:
            timeline = await responsibility_timeline(access, s.responsibility_id)
            activity = [
                e.occurred_at
                for e in timeline.events
                if e.occurred_at > since and e.category != "ownership_change"
            ]
            last_review = reviewed_at.get(s.responsibility_id)
            reviewed = last_review is not None and last_review > since
        state: FollowState
        if since is None:
            state = "not_in_place"
        elif (reviewed or activity) and not tasks:
            state = "settled"
        elif overdue or (not reviewed and not activity and now - since >= CHECK_IN_AFTER):
            state = "check_in"
        else:
            state = "settling"
        items.append(
            FollowThroughItem(
                scope_item_id=s.id,
                responsibility_id=s.responsibility_id,
                responsibility_name=s.responsibility_name,
                criticality=s.criticality,
                recipient_name=s.recipient.name,
                state=state,
                holder_since=since,
                reviewed_since=reviewed,
                activity_since=len(activity),
                last_activity_at=max(activity, default=None),
                open_tasks=len(tasks),
                overdue_tasks=overdue,
            )
        )
    return FollowThroughView(
        applies=True, settled=sum(1 for i in items if i.state == "settled"), items=items
    )
