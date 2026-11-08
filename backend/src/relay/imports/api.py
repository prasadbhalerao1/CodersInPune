from fastapi import APIRouter

from relay.identity.workspace_access import CurrentWorkspace
from relay.imports import service as svc

router = APIRouter(prefix="/workspaces/{workspace_id}/imports", tags=["imports"])


@router.post("/preview")
async def preview(access: CurrentWorkspace, body: svc.ImportIn) -> svc.ImportResultView:
    return await svc.preview_import(access, body)


@router.post("/commit")
async def commit(access: CurrentWorkspace, body: svc.ImportIn) -> svc.ImportResultView:
    return await svc.commit_import(access, body)
