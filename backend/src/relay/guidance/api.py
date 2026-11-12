from fastapi import APIRouter

from relay.guidance import service as svc
from relay.identity.workspace_access import CurrentWorkspace

router = APIRouter(prefix="/workspaces/{workspace_id}/guidance", tags=["guidance"])


@router.get("")
async def guidance(access: CurrentWorkspace) -> svc.GuidanceView:
    """The checklist, integration readiness and tours for the signed-in member."""
    return await svc.guidance(access)


@router.patch("")
async def update_guidance(access: CurrentWorkspace, body: svc.GuidanceUpdate) -> svc.GuidanceView:
    """Switch automatic guidance, record tour progress or completion, dismiss a tip, or reset."""
    return await svc.update(access, body)
