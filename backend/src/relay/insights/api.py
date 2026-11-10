import uuid

from fastapi import APIRouter

from relay.identity.workspace_access import CurrentWorkspace
from relay.insights import metrics
from relay.insights import service as svc

router = APIRouter(prefix="/workspaces/{workspace_id}/insights", tags=["insights"])


@router.get("")
async def insights(
    access: CurrentWorkspace,
    department_id: uuid.UUID | None = None,
    criticality: svc.Criticality | None = None,
) -> svc.InsightsView:
    return await svc.insights(access, department_id=department_id, criticality=criticality)


@router.get("/metrics")
async def trend_metrics(access: CurrentWorkspace, days: int = 90) -> metrics.MetricsView:
    return await metrics.compute(access, days=days)


@router.get("/snapshots")
async def snapshots(access: CurrentWorkspace) -> list[metrics.SnapshotView]:
    return await metrics.snapshots(access)


@router.post("/snapshots", status_code=201)
async def take_snapshot(access: CurrentWorkspace, days: int = 90) -> metrics.SnapshotView:
    return await metrics.take_snapshot(access, days=days)
