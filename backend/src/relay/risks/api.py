from fastapi import APIRouter

from relay.identity.workspace_access import CurrentWorkspace
from relay.risks import service as svc

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["risks"])


@router.get("/risks")
async def list_risks(access: CurrentWorkspace) -> list[svc.RiskView]:
    return await svc.compute_risks(access)


@router.get("/overview")
async def overview(access: CurrentWorkspace) -> svc.Overview:
    return await svc.overview(access)
