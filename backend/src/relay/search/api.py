from fastapi import APIRouter

from relay.identity.workspace_access import CurrentWorkspace
from relay.search import service as svc

router = APIRouter(prefix="/workspaces/{workspace_id}/search", tags=["search"])


@router.get("")
async def search(access: CurrentWorkspace, q: str = "") -> svc.SearchView:
    return await svc.search(access, q)
