import uuid
from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import PlainTextResponse

from relay.catalog import knowledge as svc
from relay.catalog import knowledge_governance as gov
from relay.identity.workspace_access import CurrentWorkspace

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["knowledge"])


@router.get("/knowledge")
async def overview(
    access: CurrentWorkspace,
    q: str | None = None,
    freshness: svc.Freshness | None = None,
    origin: Literal["person", "notion", "ai"] | None = None,
    steward_user_id: uuid.UUID | None = None,
    review_state: Literal["draft", "verified", "disputed"] | None = None,
    visibility: svc.Visibility | None = None,
    team_id: uuid.UUID | None = None,
    kind: svc.Kind | None = None,
) -> svc.KnowledgeOverviewView:
    return await svc.knowledge_overview(
        access,
        q=q,
        freshness=freshness,
        origin=origin,
        steward_user_id=steward_user_id,
        review_state=review_state,
        visibility=visibility,
        team_id=team_id,
        kind=kind,
    )


@router.get("/responsibilities/{responsibility_id}/knowledge")
async def for_responsibility(
    access: CurrentWorkspace, responsibility_id: uuid.UUID
) -> list[svc.KnowledgeView]:
    return await svc.responsibility_knowledge(access, responsibility_id)


@router.post("/responsibilities/{responsibility_id}/knowledge", status_code=status.HTTP_201_CREATED)
async def add(
    access: CurrentWorkspace, responsibility_id: uuid.UUID, body: svc.KnowledgeIn
) -> svc.KnowledgeView:
    return await svc.add_knowledge(access, responsibility_id, body)


@router.patch("/knowledge/{item_id}")
async def update(
    access: CurrentWorkspace, item_id: uuid.UUID, body: svc.KnowledgeUpdate
) -> svc.KnowledgeView:
    return await svc.update_knowledge(access, item_id, body)


@router.post("/knowledge/{item_id}/review")
async def review(access: CurrentWorkspace, item_id: uuid.UUID) -> svc.KnowledgeView:
    return await svc.review_knowledge(access, item_id)


@router.get("/cases/{case_id}/knowledge")
async def case_knowledge(
    access: CurrentWorkspace, case_id: uuid.UUID
) -> list[svc.CaseKnowledgeItemView]:
    return await svc.case_knowledge(access, case_id)


@router.post("/cases/{case_id}/knowledge", status_code=status.HTTP_201_CREATED)
async def record_handover(
    access: CurrentWorkspace, case_id: uuid.UUID, body: svc.HandoverIn
) -> list[svc.CaseKnowledgeItemView]:
    return await svc.record_handover(access, case_id, body)


@router.post("/knowledge/{item_id}/dispute")
async def dispute(
    access: CurrentWorkspace, item_id: uuid.UUID, body: gov.DisputeIn
) -> svc.KnowledgeView:
    return await gov.dispute(access, item_id, body)


@router.post("/knowledge/{item_id}/feedback", status_code=status.HTTP_201_CREATED)
async def feedback(
    access: CurrentWorkspace, item_id: uuid.UUID, body: gov.FeedbackIn
) -> gov.GovernanceView:
    return await gov.feedback(access, item_id, body)


@router.get("/knowledge/{item_id}/governance")
async def governance(access: CurrentWorkspace, item_id: uuid.UUID) -> gov.GovernanceView:
    return await gov.governance(access, item_id)


@router.get("/knowledge/{item_id}/compare")
async def compare(
    access: CurrentWorkspace, item_id: uuid.UUID, from_version: int, to_version: int
) -> gov.CompareView:
    return await gov.compare(access, item_id, from_version, to_version)


@router.get("/cases/{case_id}/export.md", response_class=PlainTextResponse)
async def export_case(access: CurrentWorkspace, case_id: uuid.UUID) -> str:
    return await gov.export_case_markdown(access, case_id)


@router.get("/knowledge/{item_id}")
async def get_knowledge(access: CurrentWorkspace, item_id: uuid.UUID) -> svc.KnowledgeView:
    return await svc.get_knowledge(access, item_id)
