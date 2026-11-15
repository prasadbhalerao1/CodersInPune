import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from relay.automation import service as svc
from relay.governance import administration
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


@router.get("/policy/tiers")
async def policy_tiers(access: CurrentWorkspace) -> list[governance.TierView]:
    return await governance.list_tiers(access)


@router.put("/policy/tiers/{criticality}")
async def update_policy_tier(
    access: CurrentWorkspace, criticality: governance.Criticality, body: governance.TierUpdate
) -> list[governance.TierView]:
    return await governance.update_tier(access, criticality, body)


@router.get("/export")
async def export_workspace(access: CurrentWorkspace) -> dict[str, Any]:
    return await administration.export_workspace(access)


@router.get("/audit/export.csv", response_class=PlainTextResponse)
async def export_audit(access: CurrentWorkspace) -> str:
    return await administration.export_audit_csv(access)


@router.post("/retention/apply")
async def apply_retention(access: CurrentWorkspace) -> administration.RetentionResult:
    return await administration.apply_retention(access)


@router.post("/ownership/transfer", status_code=204)
async def transfer_ownership(access: CurrentWorkspace, body: administration.TransferIn) -> None:
    await administration.transfer_ownership(access, body)
