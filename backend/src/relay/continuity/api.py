import uuid
from typing import Literal

from fastapi import APIRouter, status

from relay.continuity import briefing, collaboration
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
    access: CurrentWorkspace, status: Literal["open", "closed"] | None = None
) -> list[svc.CaseSummary]:
    return await svc.list_cases(access, status=status)


@router.post("/cases", status_code=status.HTTP_201_CREATED)
async def create_case(access: CurrentWorkspace, body: svc.CaseIn) -> Detail:
    return await svc.create_case(access, body)


@router.get("/cases/{case_id}")
async def get_case(access: CurrentWorkspace, case_id: uuid.UUID) -> Detail:
    return await svc.get_case(access, case_id)


@router.patch("/cases/{case_id}")
async def update_case(access: CurrentWorkspace, case_id: uuid.UUID, body: svc.CaseUpdate) -> Detail:
    return await svc.update_case(access, case_id, body)


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
async def complete(access: CurrentWorkspace, case_id: uuid.UUID, jobs: Jobs) -> Detail:
    return await svc.complete_case(access, case_id, jobs)


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
