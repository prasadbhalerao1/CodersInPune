import uuid

from fastapi import APIRouter, status

from relay.catalog import knowledge as svc
from relay.identity.workspace_access import CurrentWorkspace

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["knowledge"])


@router.get("/knowledge")
async def overview(
    access: CurrentWorkspace, q: str | None = None, freshness: svc.Freshness | None = None
) -> svc.KnowledgeOverviewView:
    return await svc.knowledge_overview(access, q=q, freshness=freshness)


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
