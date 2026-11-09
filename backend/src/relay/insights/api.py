import uuid

from fastapi import APIRouter

from relay.identity.workspace_access import CurrentWorkspace
from relay.insights import service as svc

router = APIRouter(prefix="/workspaces/{workspace_id}/insights", tags=["insights"])


@router.get("")
async def insights(
    access: CurrentWorkspace,
    department_id: uuid.UUID | None = None,
    criticality: svc.Criticality | None = None,
) -> svc.InsightsView:
    return await svc.insights(access, department_id=department_id, criticality=criticality)
