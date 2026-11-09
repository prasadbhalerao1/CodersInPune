import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from relay.continuity import briefing, collaboration, impact, tasks, workflow
from relay.continuity import service as svc
from relay.identity.workspace_access import CurrentWorkspace
from relay.jobs.outbox import Jobs

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["continuity"])
Detail = svc.CaseDetail


@router.get("/my-work")
async def my_work(access: CurrentWorkspace) -> svc.MyWorkView:
    return await svc.my_work(access)


@router.get("/cases")
async def list_cases(
    access: CurrentWorkspace, filters: Annotated[svc.CaseFilter, Query()]
) -> list[svc.CaseSummary]:
    return await svc.list_cases(access, filters=filters)


@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_case(access: CurrentWorkspace, body: svc.CaseIn, jobs: Jobs) -> Detail:
    return await svc.create_case(access, body, jobs)


@router.get("/cases/{case_id}")
async def get_case(access: CurrentWorkspace, case_id: uuid.UUID) -> Detail:
    return await svc.get_case(access, case_id)


@router.patch("/cases/{case_id}")
async def update_case(
    access: CurrentWorkspace, case_id: uuid.UUID, body: svc.CaseUpdate, jobs: Jobs
) -> Detail:
    return await svc.update_case(access, case_id, body, jobs)


@router.get("/cases/{case_id}/history")
async def history(access: CurrentWorkspace, case_id: uuid.UUID) -> list[svc.HistoryView]:
    return await svc.case_history(access, case_id)


@router.post("/cases/{case_id}/scope", status_code=status.HTTP_201_CREATED)
async def add_scope(access: CurrentWorkspace, case_id: uuid.UUID, body: svc.ScopeItemIn) -> Detail:
    return await svc.add_scope_item(access, case_id, body)


@router.patch("/cases/{case_id}/scope/{item_id}")
async def update_scope(
    access: CurrentWorkspace, case_id: uuid.UUID, item_id: uuid.UUID, body: svc.ScopeItemUpdate
) -> Detail:
    return await svc.update_scope_item(access, case_id, item_id, body)


@router.delete("/cases/{case_id}/scope/{item_id}")
async def remove_scope(access: CurrentWorkspace, case_id: uuid.UUID, item_id: uuid.UUID) -> Detail:
    return await svc.remove_scope_item(access, case_id, item_id)


@router.post("/cases/{case_id}/submit")
async def submit(access: CurrentWorkspace, case_id: uuid.UUID, jobs: Jobs) -> Detail:
    return await svc.submit_case(access, case_id, jobs)


@router.post("/cases/{case_id}/decisions", status_code=status.HTTP_201_CREATED)
async def decide(
    access: CurrentWorkspace, case_id: uuid.UUID, body: svc.DecisionIn, jobs: Jobs
) -> Detail:
    return await svc.decide(access, case_id, body, jobs)


@router.post("/cases/{case_id}/execute")
async def execute(access: CurrentWorkspace, case_id: uuid.UUID, jobs: Jobs) -> Detail:
    return await svc.execute_case(access, case_id, jobs)


@router.post("/cases/{case_id}/extend")
async def extend(access: CurrentWorkspace, case_id: uuid.UUID, body: svc.ExtendIn) -> Detail:
    return await svc.extend_coverage(access, case_id, body)


@router.post("/cases/{case_id}/complete")
async def complete(
    access: CurrentWorkspace, case_id: uuid.UUID, jobs: Jobs, body: svc.CompleteIn | None = None
) -> Detail:
    return await svc.complete_case(access, case_id, jobs, body)


@router.post("/cases/{case_id}/cancel")
async def cancel(access: CurrentWorkspace, case_id: uuid.UUID, jobs: Jobs) -> Detail:
    return await svc.cancel_case(access, case_id, jobs)


@router.post("/cases/{case_id}/tasks", status_code=status.HTTP_201_CREATED)
async def add_task(
    access: CurrentWorkspace, case_id: uuid.UUID, body: svc.TaskIn, jobs: Jobs
) -> Detail:
    return await svc.add_task(access, case_id, body, jobs)


@router.patch("/cases/{case_id}/tasks/{task_id}")
async def update_task(
    access: CurrentWorkspace, case_id: uuid.UUID, task_id: uuid.UUID, body: svc.TaskUpdate
) -> Detail:
    return await svc.update_task(access, case_id, task_id, body)


@router.post("/cases/{case_id}/criteria", status_code=status.HTTP_201_CREATED)
async def add_criterion(
    access: CurrentWorkspace, case_id: uuid.UUID, body: svc.CriterionIn
) -> Detail:
    return await svc.add_criterion(access, case_id, body)


@router.patch("/cases/{case_id}/criteria/{criterion_id}")
async def update_criterion(
    access: CurrentWorkspace, case_id: uuid.UUID, criterion_id: uuid.UUID, body: svc.CriterionUpdate
) -> Detail:
    return await svc.update_criterion(access, case_id, criterion_id, body)


@router.post("/cases/{case_id}/emergency")
async def set_emergency(
    access: CurrentWorkspace, case_id: uuid.UUID, body: svc.EmergencyIn, jobs: Jobs
) -> Detail:
    return await svc.set_emergency(access, case_id, body, jobs)


@router.get("/cases/{case_id}/activity")
async def activity(
    access: CurrentWorkspace, case_id: uuid.UUID
) -> list[collaboration.ActivityView]:
    return await collaboration.case_activity(access, case_id)


@router.post("/cases/{case_id}/comments", status_code=status.HTTP_201_CREATED)
async def add_comment(
    access: CurrentWorkspace, case_id: uuid.UUID, body: collaboration.CommentIn, jobs: Jobs
) -> collaboration.ActivityView:
    return await collaboration.add_comment(access, case_id, body, jobs)


@router.get("/cases/{case_id}/briefing")
async def return_briefing(access: CurrentWorkspace, case_id: uuid.UUID) -> briefing.BriefingView:
    return await briefing.return_briefing(access, case_id)


@router.post("/cases/{case_id}/transition")
async def transition(
    access: CurrentWorkspace, case_id: uuid.UUID, body: workflow.TransitionIn
) -> Detail:
    return await workflow.transition(access, case_id, body)


@router.post("/cases/{case_id}/reopen")
async def reopen(
    access: CurrentWorkspace, case_id: uuid.UUID, body: workflow.ReasonIn, jobs: Jobs
) -> Detail:
    return await workflow.reopen(access, case_id, body, jobs)


@router.post("/cases/{case_id}/blockers", status_code=status.HTTP_201_CREATED)
async def add_blocker(
    access: CurrentWorkspace, case_id: uuid.UUID, body: workflow.BlockerIn, jobs: Jobs
) -> Detail:
    return await workflow.add_blocker(access, case_id, body, jobs)


@router.post("/cases/{case_id}/blockers/{blocker_id}/resolve")
async def resolve_blocker(
    access: CurrentWorkspace,
    case_id: uuid.UUID,
    blocker_id: uuid.UUID,
    body: workflow.ResolveBlockerIn,
) -> Detail:
    return await workflow.resolve_blocker(access, case_id, blocker_id, body)


@router.post("/cases/{case_id}/scope/{item_id}/decline")
async def decline(
    access: CurrentWorkspace,
    case_id: uuid.UUID,
    item_id: uuid.UUID,
    body: workflow.ReasonIn,
    jobs: Jobs,
) -> Detail:
    return await workflow.decline(access, case_id, item_id, body, jobs)


@router.post("/cases/{case_id}/split")
async def split(access: CurrentWorkspace, case_id: uuid.UUID, body: list[uuid.UUID]) -> Detail:
    return await workflow.split(access, case_id, body)


@router.get("/cases/{case_id}/participants")
async def participants(
    access: CurrentWorkspace, case_id: uuid.UUID
) -> list[workflow.ParticipantView]:
    return await workflow.participants(access, case_id)


@router.post("/cases/{case_id}/participants", status_code=status.HTTP_201_CREATED)
async def add_participant(
    access: CurrentWorkspace, case_id: uuid.UUID, body: workflow.ParticipantIn
) -> list[workflow.ParticipantView]:
    return await workflow.add_participant(access, case_id, body)


@router.delete("/cases/{case_id}/participants/{participant_id}")
async def remove_participant(
    access: CurrentWorkspace, case_id: uuid.UUID, participant_id: uuid.UUID
) -> list[workflow.ParticipantView]:
    return await workflow.remove_participant(access, case_id, participant_id)


@router.get("/saved-views")
async def saved_views(
    access: CurrentWorkspace, page: Literal["cases", "responsibilities", "assets", "knowledge"]
) -> list[workflow.SavedViewView]:
    return await workflow.saved_views(access, page)


@router.post("/saved-views", status_code=status.HTTP_201_CREATED)
async def save_view(
    access: CurrentWorkspace, body: workflow.SavedViewIn
) -> list[workflow.SavedViewView]:
    return await workflow.save_view(access, body)


@router.delete("/saved-views/{view_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_view(access: CurrentWorkspace, view_id: uuid.UUID) -> None:
    await workflow.delete_view(access, view_id)


@router.get("/cases/{case_id}/impact")
async def case_impact(access: CurrentWorkspace, case_id: uuid.UUID) -> impact.ImpactView:
    return await impact.case_impact(access, case_id)


@router.get("/cases/{case_id}/tasks/{task_id}")
async def task_detail(
    access: CurrentWorkspace, case_id: uuid.UUID, task_id: uuid.UUID
) -> tasks.TaskDetail:
    return await tasks.task_detail(access, case_id, task_id)


@router.post("/cases/{case_id}/tasks/{task_id}/change")
async def change_task(
    access: CurrentWorkspace,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    body: tasks.TaskChange,
    jobs: Jobs,
) -> tasks.TaskDetail:
    return await tasks.change_task(access, case_id, task_id, body, jobs)


@router.post("/cases/{case_id}/tasks/{task_id}/messages", status_code=status.HTTP_201_CREATED)
async def task_message(
    access: CurrentWorkspace,
    case_id: uuid.UUID,
    task_id: uuid.UUID,
    body: tasks.TaskMessageIn,
    jobs: Jobs,
) -> tasks.TaskDetail:
    return await tasks.post_message(access, case_id, task_id, body, jobs)


@router.post("/cases/{case_id}/tasks/bulk")
async def bulk_tasks(
    access: CurrentWorkspace, case_id: uuid.UUID, body: tasks.BulkIn
) -> tasks.BulkResult:
    return await tasks.bulk(access, case_id, body)


@router.patch("/cases/{case_id}/criteria/{criterion_id}/steps/{index}")
async def set_step(
    access: CurrentWorkspace,
    case_id: uuid.UUID,
    criterion_id: uuid.UUID,
    index: int,
    body: tasks.StepIn,
) -> Detail:
    return await tasks.set_step(access, case_id, criterion_id, index, body)
