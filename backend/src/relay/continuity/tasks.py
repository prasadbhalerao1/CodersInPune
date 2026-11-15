"""Task coordination: reassignment and due-date changes with history, comments and
clarification requests, safe bulk actions, and supervised rehearsal checklists.

Every change writes an append-only task event in the same transaction; reassignment and
due-date changes need the case manager, comments need case.comment, and the person a
clarification was asked of may answer it.
"""

import uuid
from datetime import datetime
from typing import Literal

import procrastinate
from pydantic import AwareDatetime, BaseModel
from sqlalchemy import func, select

from relay.catalog import service as catalog
from relay.continuity import service as cases
from relay.continuity.models import CaseReadinessCriterion, CaseTask, CaseTaskEvent
from relay.identity.workspace_access import WorkspaceAccess
from relay.notifications import service as notifications
from relay.policy.permissions import Permission, authorize
from relay.shared.api_types import LongText, StrictInput
from relay.shared.errors import ApiError


class TaskChange(StrictInput):
    """Reassign (member or team) and/or move the due date. Reassigning needs a reason."""

    assignee_user_id: uuid.UUID | None = None
    assignee_team_id: uuid.UUID | None = None
    due_at: AwareDatetime | None = None
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    reason: LongText | None = None


class TaskMessageIn(StrictInput):
    body: LongText
    kind: Literal["comment", "clarification"] = "comment"
    # For a clarification: who must answer (defaults to the assignee).
    ask_user_id: uuid.UUID | None = None


class BulkIn(StrictInput):
    task_ids: list[uuid.UUID]
    action: Literal["complete", "reassign"]
    assignee_user_id: uuid.UUID | None = None
    reason: LongText | None = None


class BulkResult(BaseModel):
    done: list[uuid.UUID]
    skipped: dict[str, str]  # task id -> why it was left alone


class StepIn(StrictInput):
    done: bool


class TaskEventView(BaseModel):
    kind: str
    body: str | None
    detail: dict[str, str | None]
    actor_name: str | None
    created_at: datetime


class TaskDetail(BaseModel):
    task: cases.TaskView
    events: list[TaskEventView]
    can_answer: bool


def _event(
    access: WorkspaceAccess,
    task: CaseTask,
    kind: str,
    body: str | None = None,
    **detail: str | None,
) -> None:
    access.session.add(
        CaseTaskEvent(
            tenant_id=access.tenant_id,
            task_id=task.id,
            kind=kind,
            body=body,
            detail=detail,
            actor_user_id=access.user_id,
        )
    )


async def _task(access: WorkspaceAccess, case_id: uuid.UUID, task_id: uuid.UUID) -> CaseTask:
    task = await access.session.get(CaseTask, task_id, with_for_update=True)
    if task is None or task.case_id != case_id:
        raise ApiError(404, "task_not_found", "Task not found.")
    return task


async def change_task(
    access: WorkspaceAccess,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    data: TaskChange,
    jobs: procrastinate.App,
) -> TaskDetail:
    case = await cases._for_change(access, case_id, cases.OPEN)
    task = await _task(access, case_id, task_id)
    changes = data.model_dump(exclude_unset=True)
    names = await cases._member_names(access)
    if {"assignee_user_id", "assignee_team_id"} & changes.keys():
        user, team = changes.get("assignee_user_id"), changes.get("assignee_team_id")
        if user and team:
            raise ApiError(422, "one_assignee", "Assign a member or a team, not both.")
        if (user, team) != (task.assignee_user_id, task.assignee_team_id):
            if (task.assignee_user_id or task.assignee_team_id) and not data.reason:
                raise ApiError(422, "reason_required", "Say why the task is reassigned.")
            if user:
                await cases._require_member(access, user)
            if team:
                await catalog.require_assignee(access, catalog.Assignee(team_id=team))
            _event(
                access,
                task,
                "reassigned",
                data.reason,
                from_user=str(task.assignee_user_id) if task.assignee_user_id else None,
                to_user=str(user) if user else None,
                to_team=str(team) if team else None,
                to_name=names.get(user) if user else None,
            )
            task.assignee_user_id, task.assignee_team_id = user, team
    if "due_at" in changes and changes["due_at"] != task.due_at:
        _event(
            access,
            task,
            "due_changed",
            data.reason,
            from_due=task.due_at.isoformat() if task.due_at else None,
            to_due=data.due_at.isoformat() if data.due_at else None,
        )
        task.due_at = data.due_at
    if data.priority:
        task.priority = data.priority
    await access.session.flush()
    # Reminders are keyed by assignee and due date; earlier ones find them changed.
    await notifications.request_task_notifications(access.session, jobs, task, access.user_id)
    cases._record(
        access, case, "case.task_changed", task_id=str(task_id), fields=",".join(sorted(changes))
    )
    return await task_detail(access, case_id, task_id)


async def post_message(
    access: WorkspaceAccess,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    data: TaskMessageIn,
    jobs: procrastinate.App,
) -> TaskDetail:
    authorize(access, Permission.CASE_COMMENT)
    case = await cases._load(access, case_id, lock=True)
    if case.status not in cases.OPEN:
        raise ApiError(409, "invalid_state", "The case is closed.")
    task = await _task(access, case_id, task_id)
    if data.kind == "clarification":
        asked = data.ask_user_id or task.assignee_user_id
        if asked is None:
            raise ApiError(422, "ask_whom", "Choose who should answer.")
        await cases._require_member(access, asked)
        task.needs_input_from_user_id = asked
        _event(access, task, "clarification_requested", data.body, asked=str(asked))
        await notifications.request(
            access.session,
            jobs,
            tenant_id=access.tenant_id,
            kind="case_update",
            case_id=case_id,
            task_id=task.id,
            recipients=[asked],
            actor_user_id=access.user_id,
            detail="clarification",
            dedupe=f"clarification:{task.id}:{uuid.uuid7()}",
        )
    elif task.needs_input_from_user_id == access.user_id:
        # The person asked replies: the clarification is answered.
        task.needs_input_from_user_id = None
        _event(access, task, "clarification_answered", data.body)
    else:
        _event(access, task, "comment", data.body)
    return await task_detail(access, case_id, task_id)


async def task_detail(
    access: WorkspaceAccess, case_id: uuid.UUID, task_id: uuid.UUID
) -> TaskDetail:
    authorize(access, Permission.CASE_READ)
    await cases._load(access, case_id)
    await access.session.flush()
    task = await access.session.get(CaseTask, task_id)
    if task is None or task.case_id != case_id:
        raise ApiError(404, "task_not_found", "Task not found.")
    await access.session.refresh(task)
    names = await cases._member_names(access)
    events = await access.session.scalars(
        select(CaseTaskEvent)
        .where(CaseTaskEvent.task_id == task_id)
        .order_by(CaseTaskEvent.created_at, CaseTaskEvent.id)
    )
    return TaskDetail(
        task=(await cases.task_views(access, [task], names))[0],
        events=[
            TaskEventView(
                kind=e.kind,
                body=e.body,
                detail=e.detail,
                actor_name=names.get(e.actor_user_id),
                created_at=e.created_at,
            )
            for e in events
        ],
        can_answer=task.needs_input_from_user_id == access.user_id,
    )


async def bulk(access: WorkspaceAccess, case_id: uuid.UUID, data: BulkIn) -> BulkResult:
    """Only where safe: open tasks with nothing open they depend on; others are skipped and
    reported, never forced."""
    case = await cases._for_change(access, case_id, cases.OPEN)
    if data.action == "reassign":
        if not data.assignee_user_id or not data.reason:
            raise ApiError(422, "reason_required", "Choose the new assignee and say why.")
        await cases._require_member(access, data.assignee_user_id)
    tasks = list(
        await access.session.scalars(
            select(CaseTask)
            .where(CaseTask.id.in_(data.task_ids), CaseTask.case_id == case_id)
            .with_for_update()
        )
    )
    waiting = await cases.open_dependencies(access.session, [t.id for t in tasks])
    done: list[uuid.UUID] = []
    skipped: dict[str, str] = {
        str(i): "not a task in this case" for i in set(data.task_ids) - {t.id for t in tasks}
    }
    for task in tasks:
        if task.status != "open":
            skipped[str(task.id)] = f"already {task.status}"
        elif data.action == "complete" and waiting.get(task.id):
            skipped[str(task.id)] = "waits for " + ", ".join(waiting[task.id])
        elif data.action == "complete":
            task.status, task.completed_at, task.completed_by = "done", func.now(), access.user_id
            task.needs_input_from_user_id = None
            _event(access, task, "completed", data.reason, bulk="true")
            done.append(task.id)
        else:
            _event(
                access,
                task,
                "reassigned",
                data.reason,
                from_user=str(task.assignee_user_id) if task.assignee_user_id else None,
                to_user=str(data.assignee_user_id),
                bulk="true",
            )
            task.assignee_user_id, task.assignee_team_id = data.assignee_user_id, None
            done.append(task.id)
    cases._record(access, case, f"case.tasks_bulk_{data.action}", count=len(done))
    return BulkResult(done=done, skipped=skipped)


async def set_step(
    access: WorkspaceAccess, case_id: uuid.UUID, criterion_id: uuid.UUID, index: int, data: StepIn
) -> cases.CaseDetail:
    """Tick a rehearsal step. Relay records who confirmed it; it performs nothing itself."""
    case = await cases._load(access, case_id, lock=True)
    if case.status not in cases.OPEN:
        raise ApiError(409, "invalid_state", "The case is closed.")
    criterion = await access.session.get(CaseReadinessCriterion, criterion_id, with_for_update=True)
    if criterion is None or criterion.case_id != case_id or criterion.criterion_type != "rehearsal":
        raise ApiError(404, "criterion_not_found", "Rehearsal not found.")
    # The incoming owner may tick steps they performed; otherwise managing the case is needed.
    if not await cases.is_scope_recipient(access, criterion.scope_item_id):
        authorize(access, Permission.CASE_MANAGE)
    if not 0 <= index < len(criterion.checklist):
        raise ApiError(404, "step_not_found", "Step not found.")
    names = await cases._member_names(access)
    steps = [dict(step) for step in criterion.checklist]
    steps[index] = {
        "step": steps[index]["step"],
        "done": data.done,
        "done_by": names.get(access.user_id) if data.done else None,
        "done_at": cases._now().isoformat() if data.done else None,
    }
    criterion.checklist = steps
    cases._record(
        access,
        case,
        "case.rehearsal_step",
        criterion_id=str(criterion_id),
        step=index,
        done=data.done,
    )
    return await cases.get_case(access, case_id)
