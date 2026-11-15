"""Sample workspace endpoint: explore Relay on a synthetic organisation in one step.

The caller becomes the owner of a new "Northwind Labs (demo)" workspace populated by the
same seed as `relay-demo-seed`. Nothing real is read or written: the people are synthetic
members who cannot sign in, and the connector rows are never synced.
"""

import logging

from fastapi import APIRouter, Request, Response, status

from relay.demo import seed
from relay.identity.auth import Identity
from relay.platform.workspaces import IdempotencyKey, WorkspaceView
from relay.shared.errors import ApiError
from relay.shared.rate_limit import rate_limit

log = logging.getLogger(__name__)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post(
    "/sample",
    status_code=status.HTTP_201_CREATED,
    # Seeding runs every real service (rules, audit, outbox), so it is the most expensive
    # write a user can trigger; three a day is plenty for exploring.
    dependencies=[rate_limit("workspace_sample", 3, 86_400)],
)
async def create_sample_workspace(
    identity: Identity,
    idempotency_key: IdempotencyKey,
    request: Request,
    response: Response,
) -> WorkspaceView:
    settings = request.app.state.settings
    if not settings.sample_workspaces:
        raise ApiError(404, "not_found", "Sample workspaces are not available here.")
    try:
        workspace, created = await seed.seed_workspace(
            identity.workos_user_id,
            settings,
            request.app.state.session_factory,
            request.app.state.jobs,
            idempotency_key,
        )
    except ApiError:
        raise
    except Exception as error:
        # The workspace row is committed before the catalogue is seeded, so a failure here
        # can leave a partly filled sample. Say so instead of pretending nothing happened.
        log.exception("sample workspace seeding failed")
        raise ApiError(
            500,
            "sample_incomplete",
            "The sample workspace could not be fully set up. "
            "Delete it from its settings page and try again.",
        ) from error
    if not created:
        response.status_code = status.HTTP_200_OK
    return workspace
