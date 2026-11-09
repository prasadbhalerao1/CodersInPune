from fastapi import APIRouter

from relay.identity.workspace_access import CurrentWorkspace
from relay.imports import service as svc
from relay.shared.rate_limit import rate_limit

router = APIRouter(prefix="/workspaces/{workspace_id}/imports", tags=["imports"])


@router.post("/preview", dependencies=[rate_limit("imports", 30, 600)])
async def preview(access: CurrentWorkspace, body: svc.ImportIn) -> svc.ImportResultView:
    return await svc.preview_import(access, body)


@router.post("/commit", dependencies=[rate_limit("imports", 30, 600)])
async def commit(access: CurrentWorkspace, body: svc.ImportIn) -> svc.ImportResultView:
    return await svc.commit_import(access, body)
