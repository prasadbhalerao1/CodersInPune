import uuid

from fastapi import APIRouter, Request

from relay.identity.workspace_access import CurrentWorkspace
from relay.intelligence import runs
from relay.intelligence import service as svc
from relay.jobs.outbox import Jobs
from relay.shared.rate_limit import rate_limit

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["intelligence"])


@router.post(
    "/cases/{case_id}/analysis",
    status_code=202,
    dependencies=[rate_limit("ai_run", 20, 600)],
)
async def analyse(
    access: CurrentWorkspace, case_id: uuid.UUID, request: Request, jobs: Jobs
) -> svc.RunView:
    run = await runs.start_analysis(access, case_id, request.app.state.settings, jobs)
    return svc.run_view(run)


@router.get("/cases/{case_id}/analysis")
async def analysis(
    access: CurrentWorkspace, case_id: uuid.UUID, request: Request
) -> svc.AnalysisView:
    return await svc.get_analysis(access, case_id, request.app.state.settings)


@router.post("/ai/runs/{run_id}/cancel")
async def cancel(access: CurrentWorkspace, run_id: uuid.UUID) -> svc.RunView:
    return svc.run_view(await runs.cancel_run(access, run_id))


@router.patch("/ai/claims/{claim_id}", status_code=204)
async def review_claim(
    access: CurrentWorkspace, claim_id: uuid.UUID, body: svc.ClaimReview
) -> None:
    await svc.review_claim(access, claim_id, body)


@router.post("/ai/proposals/{proposal_id}/accept")
async def accept(
    access: CurrentWorkspace,
    proposal_id: uuid.UUID,
    jobs: Jobs,
    body: svc.ProposalEdit | None = None,
) -> svc.ProposalView:
    return await svc.accept_proposal(access, proposal_id, body, jobs)


@router.post("/ai/proposals/{proposal_id}/reject", status_code=204)
async def reject(
    access: CurrentWorkspace, proposal_id: uuid.UUID, body: svc.ProposalReject
) -> None:
    await svc.reject_proposal(access, proposal_id, body)


@router.get("/ai")
async def overview(access: CurrentWorkspace, request: Request) -> svc.AiAdminView:
    return await svc.admin_overview(access, request.app.state.settings)


@router.patch("/ai", status_code=204)
async def update_settings(access: CurrentWorkspace, body: svc.AiSettingsUpdate) -> None:
    await svc.update_settings(access, body)


@router.patch("/ai/capabilities/{name}", status_code=204)
async def update_capability(
    access: CurrentWorkspace, name: str, body: svc.CapabilityUpdate
) -> None:
    await svc.update_capability(access, name, body)


@router.get("/ai/runs")
async def list_runs(access: CurrentWorkspace) -> list[svc.RunView]:
    return await svc.list_runs(access)


@router.get("/ai/runs/{run_id}")
async def get_run(access: CurrentWorkspace, run_id: uuid.UUID) -> svc.RunDetail:
    return await svc.get_run(access, run_id)
