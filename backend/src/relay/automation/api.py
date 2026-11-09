import uuid

from fastapi import APIRouter

from relay.automation import service as svc
from relay.governance import service as governance
from relay.identity.workspace_access import CurrentWorkspace
from relay.jobs.outbox import Jobs
from relay.shared.rate_limit import rate_limit

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["automation"])


@router.get("/automations")
async def rules(access: CurrentWorkspace) -> list[svc.RuleView]:
    return await svc.list_rules(access)


@router.patch("/automations/{template}")
async def update(
    access: CurrentWorkspace, template: str, body: svc.RuleUpdate, jobs: Jobs
) -> svc.RuleView:
    return await svc.update_rule(access, template, body, jobs)


@router.post(
    "/automations/{template}/run",
    status_code=202,
    dependencies=[rate_limit("automation_run", 30, 600)],
)
async def run(access: CurrentWorkspace, template: str, jobs: Jobs) -> None:
    await svc.run_rule(access, template, jobs)


@router.post(
    "/automations/{template}/retry",
    status_code=202,
    dependencies=[rate_limit("automation_run", 30, 600)],
)
async def retry(access: CurrentWorkspace, template: str, jobs: Jobs) -> None:
    await svc.run_rule(access, template, jobs, retry=True)


@router.get("/follow-ups")
async def follow_ups(access: CurrentWorkspace, mine: bool = True) -> list[svc.FollowUpView]:
    return await svc.list_follow_ups(access, mine=mine)


@router.post("/follow-ups/{follow_up_id}/complete", status_code=204)
async def complete(access: CurrentWorkspace, follow_up_id: uuid.UUID) -> None:
    await svc.complete_follow_up(access, follow_up_id)


@router.get("/policy")
async def policy(access: CurrentWorkspace) -> governance.PolicyView:
    return await governance.get_policy(access)


@router.patch("/policy")
async def update_policy(
    access: CurrentWorkspace, body: governance.PolicyUpdate
) -> governance.PolicyView:
    return await governance.update_policy(access, body)
