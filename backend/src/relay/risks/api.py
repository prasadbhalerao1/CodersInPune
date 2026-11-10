from typing import Literal

from fastapi import APIRouter

from relay.identity.workspace_access import CurrentWorkspace
from relay.jobs.outbox import Jobs
from relay.risks import service as svc

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["risks"])

_FILTERS: dict[str, tuple[svc.RiskStatus, ...] | None] = {
    "active": svc.ACTIVE,
    "accepted": ("accepted",),
    "all": None,
}


@router.get("/risks")
async def list_risks(
    access: CurrentWorkspace, status: Literal["active", "accepted", "all"] = "active"
) -> list[svc.RiskView]:
    return await svc.compute_risks(access, statuses=_FILTERS[status])


@router.get("/risks/resolved")
async def resolved(access: CurrentWorkspace) -> list[svc.ResolvedRiskView]:
    return await svc.resolved_risks(access)


@router.post("/risks/decision")
async def decide(access: CurrentWorkspace, body: svc.RiskDecisionIn) -> svc.RiskView:
    return await svc.decide_risk(access, body)


@router.post("/risks/assign")
async def assign(access: CurrentWorkspace, body: svc.RiskAssignIn) -> svc.RiskView:
    return await svc.assign_risk(access, body)


@router.post("/risks/case")
async def open_case(access: CurrentWorkspace, body: svc.RiskCaseIn, jobs: Jobs) -> svc.RiskView:
    return await svc.open_case_for_risk(access, body, jobs)


@router.get("/overview")
async def overview(access: CurrentWorkspace) -> svc.OverviewView:
    return await svc.overview(access)
