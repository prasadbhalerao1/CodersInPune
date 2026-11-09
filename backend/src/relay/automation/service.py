"""Automation Center v1: eight continuity templates that watch and nudge, never decide.

Each template finds matching subjects (responsibilities or cases) and either notifies
people in-app or opens a follow-up in My Work. Automations never change ownership,
approvals, cases or risks.

Scheduling: enabling a rule queues a run; every scheduled run queues the next one a day
later (a delayed outbox event that carries the time it was scheduled for, so disabling or
re-enabling a rule makes stale events no-ops). Runs are idempotent: every action is first
claimed in `automation_action` by (rule, dedupe key). Notifications dedupe per subject per
week; a follow-up is not reopened while one is still open for the same subject. A failed
run rolls back its actions, is recorded with its error class, and can be retried safely.
"""

import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import procrastinate
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.automation.models import (
    TEMPLATES,
    AutomationAction,
    AutomationRule,
    AutomationRun,
    FollowUp,
)
from relay.catalog.models import KnowledgeItem, OwnershipAssignment, Responsibility
from relay.catalog.service import active_at
from relay.continuity.models import OPEN_STATUSES, CaseTask, ContinuityCase
from relay.directory.models import Person, Team
from relay.governance import service as governance
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.jobs import outbox
from relay.jobs.models import OutboxEvent
from relay.notifications.models import Notification
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.risks.models import RiskRecord
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

RUN_EVENT = "automation.run_requested"
EVERY = timedelta(days=1)
NOTIFY_WINDOW = timedelta(days=7)
COVER_ENDING = timedelta(days=3)
ACCEPTANCE_EXPIRING = timedelta(days=7)
OPEN_CASES = OPEN_STATUSES
Template = Literal[
    "critical_without_backup",
    "no_primary_owner",
    "stale_knowledge",
    "archived_owner",
    "coverage_ending",
    "case_overdue",
    "task_overdue",
    "risk_acceptance_expiring",
]
Action = Literal["notify", "create_follow_up"]


@dataclass(frozen=True, slots=True)
class Match:
    key: str  # stable subject key within the template
    title: str
    responsibility_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None
    recipient: uuid.UUID | None = None  # a natural recipient (e.g. task assignee)


@dataclass(frozen=True, slots=True)
class Spec:
    title: str
    description: str
    follow_up: str
    find: Callable[[AsyncSession, datetime], Awaitable[list[Match]]]


# ---------------------------------------------------------------- template queries


async def _roles(
    session: AsyncSession, now: datetime
) -> dict[uuid.UUID, list[OwnershipAssignment]]:
    by: dict[uuid.UUID, list[OwnershipAssignment]] = defaultdict(list)
    for a in await session.scalars(select(OwnershipAssignment).where(active_at(now))):
        by[a.responsibility_id].append(a)
    return by


async def _active_responsibilities(session: AsyncSession) -> list[Responsibility]:
    return list(
        await session.scalars(
            select(Responsibility)
            .where(Responsibility.status == "active")
            .order_by(Responsibility.name)
        )
    )


async def _critical_without_backup(session: AsyncSession, now: datetime) -> list[Match]:
    roles = await _roles(session, now)
    return [
        Match(f"r:{r.id}", r.name, responsibility_id=r.id)
        for r in await _active_responsibilities(session)
        if r.criticality == "critical" and "backup" not in {a.role for a in roles[r.id]}
    ]


async def _no_primary_owner(session: AsyncSession, now: datetime) -> list[Match]:
    roles = await _roles(session, now)
    return [
        Match(f"r:{r.id}", r.name, responsibility_id=r.id)
        for r in await _active_responsibilities(session)
        if "primary" not in {a.role for a in roles[r.id]}
    ]


async def _stale_knowledge(session: AsyncSession, now: datetime) -> list[Match]:
    days = (await governance.current(session)).knowledge_review_days
    cutoff = now - timedelta(days=days)
    stale: set[uuid.UUID] = set()
    for item in await session.scalars(
        select(KnowledgeItem).where(KnowledgeItem.status == "active")
    ):
        unreviewed = item.origin != "person" and item.last_reviewed_at is None
        if unreviewed or (item.last_reviewed_at or item.created_at) < cutoff:
            stale.add(item.responsibility_id)
    return [
        Match(f"r:{r.id}", r.name, responsibility_id=r.id)
        for r in await _active_responsibilities(session)
        if r.id in stale and r.criticality in ("critical", "high")
    ]


async def _archived_owner(session: AsyncSession, now: datetime) -> list[Match]:
    archived_people = set(
        await session.scalars(select(Person.id).where(Person.status == "archived"))
    )
    archived_teams = set(await session.scalars(select(Team.id).where(Team.status == "archived")))
    roles = await _roles(session, now)
    return [
        Match(f"r:{r.id}", r.name, responsibility_id=r.id)
        for r in await _active_responsibilities(session)
        if any(a.person_id in archived_people or a.team_id in archived_teams for a in roles[r.id])
    ]


async def _coverage_ending(session: AsyncSession, now: datetime) -> list[Match]:
    ending = {
        a.responsibility_id: a.valid_to
        for a in await session.scalars(
            select(OwnershipAssignment).where(
                OwnershipAssignment.role == "temporary",
                OwnershipAssignment.valid_from <= now,
                OwnershipAssignment.valid_to > now,
                OwnershipAssignment.valid_to <= now + COVER_ENDING,
            )
        )
    }
    return [
        Match(f"r:{r.id}:{ending[r.id]}", r.name, responsibility_id=r.id)
        for r in await _active_responsibilities(session)
        if r.id in ending
    ]


async def _case_overdue(session: AsyncSession, now: datetime) -> list[Match]:
    return [
        Match(f"c:{c.id}", c.title, case_id=c.id, recipient=c.coordinator_user_id)
        for c in await session.scalars(
            select(ContinuityCase)
            .where(ContinuityCase.status.in_(OPEN_CASES), ContinuityCase.ends_at < now)
            .order_by(ContinuityCase.ends_at)
        )
    ]


async def _task_overdue(session: AsyncSession, now: datetime) -> list[Match]:
    rows = await session.execute(
        select(CaseTask, ContinuityCase)
        .join(ContinuityCase, ContinuityCase.id == CaseTask.case_id)
        .where(
            CaseTask.status == "open",
            CaseTask.due_at < now,
            ContinuityCase.status.in_(OPEN_CASES),
        )
        .order_by(CaseTask.due_at)
    )
    return [
        Match(f"t:{t.id}", f"{c.title}: {t.title}", case_id=c.id, recipient=c.coordinator_user_id)
        for t, c in rows
    ]


async def _risk_acceptance_expiring(session: AsyncSession, now: datetime) -> list[Match]:
    names = {r.id: r.name for r in await _active_responsibilities(session)}
    matches: list[Match] = []
    for record in await session.scalars(
        select(RiskRecord).where(
            RiskRecord.status == "accepted",
            RiskRecord.accepted_until > now,
            RiskRecord.accepted_until <= now + ACCEPTANCE_EXPIRING,
        )
    ):
        try:
            rid = uuid.UUID(record.risk_key.split(":", 1)[1])
        except IndexError, ValueError:
            continue
        if rid in names:  # responsibility-level risks only; person risks have no subject page
            matches.append(
                Match(
                    f"k:{record.risk_key}:{record.accepted_until}",
                    f"{names[rid]}: {record.title}",
                    responsibility_id=rid,
                )
            )
    return matches


SPECS: dict[str, Spec] = {
    "critical_without_backup": Spec(
        "Critical responsibility without a backup",
        "A critical responsibility has nobody designated to cover it.",
        "Assign a backup",
        _critical_without_backup,
    ),
    "no_primary_owner": Spec(
        "Responsibility without a primary owner",
        "Nobody is currently accountable for an active responsibility.",
        "Assign a primary owner",
        _no_primary_owner,
    ),
    "stale_knowledge": Spec(
        "Knowledge overdue for review",
        "A critical or high responsibility has knowledge past the review interval, "
        "or imported pages nobody has reviewed.",
        "Review knowledge",
        _stale_knowledge,
    ),
    "archived_owner": Spec(
        "Archived person or team still holds a role",
        "Someone who left (or a retired team) still owns or covers a responsibility.",
        "Replace the archived owner",
        _archived_owner,
    ),
    "coverage_ending": Spec(
        "Temporary cover ending soon",
        "Temporary cover ends within 3 days; confirm the owner is back or extend it.",
        "Confirm cover hand-back",
        _coverage_ending,
    ),
    "case_overdue": Spec(
        "Continuity case past its end date",
        "An open case is past its planned end. Notifies its coordinator by default.",
        "Close or extend the case",
        _case_overdue,
    ),
    "task_overdue": Spec(
        "Overdue case task (escalation)",
        "A case task is overdue. Escalates to the case coordinator by default.",
        "Unblock an overdue task",
        _task_overdue,
    ),
    "risk_acceptance_expiring": Spec(
        "Risk acceptance expiring",
        "An accepted risk expires within 7 days; decide again before it reopens.",
        "Re-decide an accepted risk",
        _risk_acceptance_expiring,
    ),
}
assert set(SPECS) == set(TEMPLATES)


# ---------------------------------------------------------------- views


class RunView(BaseModel):
    id: uuid.UUID
    trigger: str
    status: str
    matched: int
    actions: int
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class RuleView(BaseModel):
    template: str
    title: str
    description: str
    enabled: bool
    action: str
    assignee_user_id: uuid.UUID | None
    assignee_name: str | None
    last_run_at: datetime | None
    last_status: str
    last_error: str | None
    next_run_at: datetime | None
    open_follow_ups: int
    runs: list[RunView]


class RuleUpdate(StrictInput):
    enabled: bool | None = None
    action: Action | None = None
    assignee_user_id: uuid.UUID | None = None


class FollowUpView(BaseModel):
    id: uuid.UUID
    template: str
    title: str
    detail: str | None
    responsibility_id: uuid.UUID | None
    case_id: uuid.UUID | None
    assignee_user_id: uuid.UUID | None
    status: str
    created_at: datetime


def _now() -> datetime:
    return datetime.now(UTC)


async def _member_names(access: WorkspaceAccess) -> dict[uuid.UUID, str]:
    rows = await access.session.execute(
        select(Membership.user_id, func.coalesce(Membership.display_name, Membership.email))
    )
    return {user_id: name or "Member" for user_id, name in rows}


async def list_rules(access: WorkspaceAccess) -> list[RuleView]:
    authorize(access, Permission.AUTOMATION_MANAGE)
    mine = visible(access, Permission.AUTOMATION_MANAGE, AutomationRule.tenant_id)
    rules = {
        r.template: r for r in await access.session.scalars(select(AutomationRule).where(mine))
    }
    runs: dict[uuid.UUID, list[AutomationRun]] = defaultdict(list)
    for run in await access.session.scalars(
        select(AutomationRun)
        .where(visible(access, Permission.AUTOMATION_MANAGE, AutomationRun.tenant_id))
        .order_by(AutomationRun.started_at.desc())
        .limit(400)
    ):
        if len(runs[run.rule_id]) < 10:
            runs[run.rule_id].append(run)
    open_follow_ups = dict(
        (
            await access.session.execute(
                select(FollowUp.rule_id, func.count())
                .where(
                    visible(access, Permission.AUTOMATION_MANAGE, FollowUp.tenant_id),
                    FollowUp.status == "open",
                )
                .group_by(FollowUp.rule_id)
            )
        ).all()
    )
    names = await _member_names(access)
    views: list[RuleView] = []
    for template in TEMPLATES:
        spec, rule = SPECS[template], rules.get(template)
        views.append(
            RuleView(
                template=template,
                title=spec.title,
                description=spec.description,
                enabled=bool(rule and rule.enabled),
                action=rule.action if rule else "notify",
                assignee_user_id=rule.assignee_user_id if rule else None,
                assignee_name=names.get(rule.assignee_user_id)
                if rule and rule.assignee_user_id
                else None,
                last_run_at=rule.last_run_at if rule else None,
                last_status=rule.last_status if rule else "never",
                last_error=rule.last_error if rule else None,
                next_run_at=rule.next_run_at if rule and rule.enabled else None,
                open_follow_ups=open_follow_ups.get(rule.id, 0) if rule else 0,
                runs=[
                    RunView(
                        id=r.id,
                        trigger=r.trigger,
                        status=r.status,
                        matched=r.matched,
                        actions=r.actions,
                        error=r.error,
                        started_at=r.started_at,
                        finished_at=r.finished_at,
                    )
                    for r in (runs[rule.id] if rule else [])
                ],
            )
        )
    return views


async def _rule(access: WorkspaceAccess, template: str) -> AutomationRule:
    if template not in SPECS:
        raise ApiError(404, "template_not_found", "Automation not found.")
    rule = await access.session.scalar(
        select(AutomationRule)
        .where(
            AutomationRule.template == template,
            visible(access, Permission.AUTOMATION_MANAGE, AutomationRule.tenant_id),
        )
        .with_for_update()
    )
    if rule is None:
        rule = AutomationRule(
            id=uuid.uuid7(),
            tenant_id=access.tenant_id,
            template=template,
            enabled=False,
            action="notify",
            last_status="never",
            updated_by=access.user_id,
        )
        access.session.add(rule)
        await access.session.flush()
    return rule


async def _queue(
    session: AsyncSession,
    jobs: procrastinate.App,
    rule: AutomationRule,
    trigger: Literal["schedule", "manual", "retry"],
    at: datetime | None = None,
) -> None:
    payload: dict[str, str] = {"rule_id": str(rule.id), "trigger": trigger}
    if trigger == "schedule":
        rule.next_run_at = at or _now()
        payload["scheduled_for"] = rule.next_run_at.isoformat()
    await outbox.emit(
        session,
        jobs,
        tenant_id=rule.tenant_id,
        event_type=RUN_EVENT,
        payload=payload,
        schedule_at=at,
    )


async def update_rule(
    access: WorkspaceAccess, template: str, data: RuleUpdate, jobs: procrastinate.App
) -> RuleView:
    authorize(access, Permission.AUTOMATION_MANAGE)
    rule = await _rule(access, template)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("assignee_user_id") is not None:
        member = await access.session.scalar(
            select(Membership.id).where(
                Membership.user_id == changes["assignee_user_id"], Membership.status == "active"
            )
        )
        if member is None:
            raise ApiError(422, "assignee_not_member", "Choose an active member of this workspace.")
    was_enabled = rule.enabled
    if data.action is not None:
        rule.action = data.action
    if "assignee_user_id" in changes:
        rule.assignee_user_id = data.assignee_user_id
    if data.enabled is not None:
        rule.enabled = data.enabled
    rule.updated_by, rule.updated_at = access.user_id, func.now()
    if rule.enabled and not was_enabled:
        await _queue(access.session, jobs, rule, "schedule")  # first run right away
    if not rule.enabled:
        rule.next_run_at = None  # pending scheduled events become no-ops
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="automation.updated",
        actor_user_id=access.user_id,
        target_type="automation_rule",
        target_id=rule.id,
        details={
            "template": template,
            "enabled": rule.enabled,
            "action": rule.action,
            "assignee_user_id": str(rule.assignee_user_id) if rule.assignee_user_id else None,
        },
    )
    await access.session.flush()
    return next(v for v in await list_rules(access) if v.template == template)


async def run_rule(
    access: WorkspaceAccess, template: str, jobs: procrastinate.App, *, retry: bool = False
) -> None:
    authorize(access, Permission.AUTOMATION_MANAGE)
    rule = await _rule(access, template)
    if retry and rule.last_status != "failed":
        raise ApiError(409, "nothing_to_retry", "The last run didn't fail.")
    await _queue(access.session, jobs, rule, "retry" if retry else "manual")
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="automation.run_requested",
        actor_user_id=access.user_id,
        target_type="automation_rule",
        target_id=rule.id,
        details={"template": template, "trigger": "retry" if retry else "manual"},
    )


# ---------------------------------------------------------------- execution


async def _default_recipients(session: AsyncSession) -> list[uuid.UUID]:
    return sorted(
        user_id
        for user_id, role in await session.execute(
            select(Membership.user_id, Membership.role).where(Membership.status == "active")
        )
        if role_allows(role, Permission.RESPONSIBILITY_MANAGE)
    )


async def _claim(
    session: AsyncSession, rule: AutomationRule, run: AutomationRun, key: str
) -> uuid.UUID | None:
    return await session.scalar(
        insert(AutomationAction)
        .values(tenant_id=rule.tenant_id, rule_id=rule.id, run_id=run.id, dedupe_key=key)
        .on_conflict_do_nothing(index_elements=["tenant_id", "rule_id", "dedupe_key"])
        .returning(AutomationAction.id)
    )


async def _act(
    session: AsyncSession,
    rule: AutomationRule,
    run: AutomationRun,
    matches: list[Match],
    now: datetime,
) -> int:
    actions = 0
    defaults: list[uuid.UUID] | None = None
    if rule.action == "create_follow_up":
        open_keys = {
            (f.responsibility_id, f.case_id, f.detail)
            for f in await session.scalars(
                select(FollowUp).where(FollowUp.rule_id == rule.id, FollowUp.status == "open")
            )
        }
        for m in matches:
            if (m.responsibility_id, m.case_id, m.key) in open_keys:
                continue
            claimed = await _claim(session, rule, run, f"follow_up:{m.key}:{run.id}")
            if claimed is None:
                continue
            follow_up = FollowUp(
                id=uuid.uuid7(),
                tenant_id=rule.tenant_id,
                rule_id=rule.id,
                title=f"{SPECS[rule.template].follow_up}: {m.title}"[:300],
                detail=m.key,
                responsibility_id=m.responsibility_id,
                case_id=m.case_id,
                assignee_user_id=rule.assignee_user_id or m.recipient,
            )
            session.add(follow_up)
            await session.flush()
            action = await session.get(AutomationAction, claimed)
            assert action is not None
            action.follow_up_id = follow_up.id
            actions += 1
        return actions
    window = int(now.timestamp() // NOTIFY_WINDOW.total_seconds())
    for m in matches:
        key = f"notify:{m.key}:{window}"
        if await _claim(session, rule, run, key) is None:
            continue  # already notified about this subject this week
        if rule.assignee_user_id or m.recipient:
            recipients = [u for u in (rule.assignee_user_id or m.recipient,) if u is not None]
        else:
            defaults = defaults if defaults is not None else await _default_recipients(session)
            recipients = defaults
        rows = [
            {
                "tenant_id": rule.tenant_id,
                "recipient_user_id": user_id,
                "kind": "automation",
                "detail": rule.template,
                "case_id": m.case_id,
                "responsibility_id": m.responsibility_id,
                "dedupe_key": f"automation:{rule.id}:{key}:{user_id}",
            }
            for user_id in recipients
            if user_id is not None
        ]
        if rows:
            await session.execute(
                insert(Notification)
                .values(rows)
                .on_conflict_do_nothing(index_elements=["tenant_id", "dedupe_key"])
            )
            actions += 1
    return actions


async def handle_run(session: AsyncSession, event: OutboxEvent, ctx: outbox.JobContext) -> None:
    rule = await session.get(
        AutomationRule, uuid.UUID(event.payload["rule_id"]), with_for_update=True
    )
    if rule is None:
        return
    trigger = event.payload["trigger"]
    if trigger == "schedule":
        scheduled = event.payload.get("scheduled_for")
        current = rule.next_run_at.isoformat() if rule.next_run_at else None
        if not rule.enabled or scheduled != current:
            return  # disabled or rescheduled since: a stale event
    now = _now()
    run = AutomationRun(
        id=uuid.uuid7(), tenant_id=rule.tenant_id, rule_id=rule.id, trigger=trigger, status="ok"
    )
    session.add(run)
    await session.flush()
    try:
        async with session.begin_nested():
            matches = await SPECS[rule.template].find(session, now)
            run.matched = len(matches)
            run.actions = await _act(session, rule, run, matches, now)
    except Exception as exc:  # recorded; the rolled-back actions are retried safely later
        run.status, run.error = "failed", f"{type(exc).__name__}: the run was rolled back"
    run.finished_at = func.now()
    rule.last_run_at, rule.last_status = now, run.status
    rule.last_error = run.error
    if trigger == "schedule" and rule.enabled and ctx.jobs is not None:
        await _queue(session, ctx.jobs, rule, "schedule", at=now + EVERY)


outbox.register(RUN_EVENT, handle_run)


# ---------------------------------------------------------------- follow-ups


async def list_follow_ups(access: WorkspaceAccess, *, mine: bool) -> list[FollowUpView]:
    authorize(access, Permission.CASE_READ)
    conditions = [
        visible(access, Permission.CASE_READ, FollowUp.tenant_id),
        FollowUp.status == "open",
    ]
    if mine:
        conditions.append(FollowUp.assignee_user_id == access.user_id)
    else:
        authorize(access, Permission.AUTOMATION_MANAGE)
    rows = await access.session.execute(
        select(FollowUp, AutomationRule.template)
        .join(AutomationRule, AutomationRule.id == FollowUp.rule_id)
        .where(*conditions)
        .order_by(FollowUp.created_at.desc())
        .limit(200)
    )
    return [
        FollowUpView(
            id=f.id,
            template=template,
            title=f.title,
            detail=None,
            responsibility_id=f.responsibility_id,
            case_id=f.case_id,
            assignee_user_id=f.assignee_user_id,
            status=f.status,
            created_at=f.created_at,
        )
        for f, template in rows
    ]


async def complete_follow_up(access: WorkspaceAccess, follow_up_id: uuid.UUID) -> None:
    authorize(access, Permission.CASE_READ)
    follow_up = await access.session.scalar(
        select(FollowUp)
        .where(
            FollowUp.id == follow_up_id, visible(access, Permission.CASE_READ, FollowUp.tenant_id)
        )
        .with_for_update()
    )
    if follow_up is None:
        raise ApiError(404, "follow_up_not_found", "Follow-up not found.")
    if follow_up.assignee_user_id != access.user_id:
        authorize(access, Permission.AUTOMATION_MANAGE)
    if follow_up.status == "done":
        return
    follow_up.status, follow_up.completed_by, follow_up.completed_at = (
        "done",
        access.user_id,
        func.now(),
    )
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="automation.follow_up_completed",
        actor_user_id=access.user_id,
        target_type="follow_up",
        target_id=follow_up.id,
    )
