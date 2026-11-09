import uuid

from fastapi import APIRouter, Request

from relay.identity.workspace_access import CurrentWorkspace
from relay.intelligence import capsules, interviews, runs
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


@router.post(
    "/cases/{case_id}/interview", status_code=202, dependencies=[rate_limit("ai_run", 20, 600)]
)
async def generate_interview(
    access: CurrentWorkspace, case_id: uuid.UUID, request: Request, jobs: Jobs
) -> svc.RunView:
    return await interviews.generate(access, case_id, request.app.state.settings, jobs)


@router.get("/cases/{case_id}/interview")
async def interview(
    access: CurrentWorkspace, case_id: uuid.UUID, request: Request
) -> interviews.InterviewView:
    return await interviews.interview(access, case_id, request.app.state.settings)


@router.patch("/ai/questions/{question_id}", status_code=204)
async def answer_question(
    access: CurrentWorkspace, question_id: uuid.UUID, body: interviews.AnswerIn
) -> None:
    await interviews.answer(access, question_id, body)


@router.post("/ai/questions/{question_id}/review", status_code=204)
async def review_question(access: CurrentWorkspace, question_id: uuid.UUID) -> None:
    await interviews.review(access, question_id)


@router.post("/ai/questions/{question_id}/to-knowledge", status_code=201)
async def question_to_knowledge(
    access: CurrentWorkspace, question_id: uuid.UUID
) -> svc.ProposalView:
    return await interviews.to_knowledge(access, question_id)


@router.get("/cases/{case_id}/capsules")
async def case_capsules(
    access: CurrentWorkspace, case_id: uuid.UUID
) -> list[capsules.CapsuleSummary]:
    return await capsules.list_for_case(access, case_id)


@router.post(
    "/cases/{case_id}/capsules", status_code=201, dependencies=[rate_limit("ai_run", 20, 600)]
)
async def generate_capsule(
    access: CurrentWorkspace,
    case_id: uuid.UUID,
    body: capsules.CapsuleIn,
    request: Request,
    jobs: Jobs,
) -> capsules.CapsuleView:
    return await capsules.generate(access, case_id, body, request.app.state.settings, jobs)


@router.get("/ai/capsules/{capsule_id}")
async def capsule(
    access: CurrentWorkspace, capsule_id: uuid.UUID, version: int | None = None
) -> capsules.CapsuleView:
    return await capsules.view(access, capsule_id, version)


@router.patch("/ai/capsules/{capsule_id}")
async def edit_capsule(
    access: CurrentWorkspace, capsule_id: uuid.UUID, body: capsules.CapsuleEdit
) -> capsules.CapsuleView:
    return await capsules.edit(access, capsule_id, body)


@router.post("/ai/capsules/{capsule_id}/approve")
async def approve_capsule(access: CurrentWorkspace, capsule_id: uuid.UUID) -> capsules.CapsuleView:
    return await capsules.approve(access, capsule_id)


@router.post("/ai/capsules/{capsule_id}/acknowledge")
async def acknowledge_capsule(
    access: CurrentWorkspace, capsule_id: uuid.UUID
) -> capsules.CapsuleView:
    return await capsules.acknowledge(access, capsule_id)


@router.get("/ai/capsules/{capsule_id}/versions")
async def capsule_versions(
    access: CurrentWorkspace, capsule_id: uuid.UUID
) -> list[capsules.VersionView]:
    return await capsules.versions(access, capsule_id)
