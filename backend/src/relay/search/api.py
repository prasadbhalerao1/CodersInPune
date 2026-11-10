from typing import Annotated

from fastapi import APIRouter, Query

from relay.identity.workspace_access import CurrentWorkspace
from relay.search import service as svc

router = APIRouter(prefix="/workspaces/{workspace_id}/search", tags=["search"])


@router.get("")
async def search(
    access: CurrentWorkspace,
    q: str = "",
    kind: Annotated[list[svc.Kind] | None, Query()] = None,
    full: bool = False,
) -> svc.SearchView:
    return await svc.search(access, q, kinds=list(kind) if kind else None, full=full)


@router.get("/experts")
async def experts(access: CurrentWorkspace, q: str = "") -> list[svc.ExpertView]:
    return await svc.experts(access, q)
