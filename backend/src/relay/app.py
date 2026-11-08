import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from relay import health
from relay.audit import service as audit
from relay.catalog import api as catalog_api
from relay.catalog import assets_api, knowledge_api
from relay.config import Settings
from relay.continuity import api as continuity_api
from relay.directory import api as directory_api
from relay.identity import members_api, profile
from relay.identity.tokens import WorkOSTokenVerifier
from relay.identity.workos_api import WorkOSClient
from relay.imports import api as imports_api
from relay.integrations.github import api as github_api
from relay.integrations.github.client import GitHubClient
from relay.jobs import outbox
from relay.jobs.app import create_job_app
from relay.notifications import api as notifications_api
from relay.platform import workspaces
from relay.policy.permissions import PermissionDenied
from relay.risks import api as risks_api
from relay.shared.db import create_engine, create_session_factory, unit_of_work
from relay.shared.errors import api_error_response, register_error_handlers

logger = logging.getLogger(__name__)


async def _handle_permission_denied(request: Request, exc: Exception) -> JSONResponse:
    """Record the denial in its own transaction: the request's transaction rolled back."""
    assert isinstance(exc, PermissionDenied)
    try:
        async with unit_of_work(
            request.app.state.session_factory, exc.tenant_id, exc.workos_user_id
        ) as session:
            audit.record(
                session,
                tenant_id=exc.tenant_id,
                action="authorization.denied",
                actor_user_id=exc.user_id,
                details={"permission": exc.permission, "role": exc.role},
            )
    except Exception:
        logger.exception("could not record authorization denial")
    return api_error_response(exc)


def create_app(
    settings: Settings | None = None,
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Build the API. `http_transport` lets tests stub every outbound HTTP call
    (WorkOS JWKS/API, GitHub) without network access."""
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(resolved)
        http = httpx.AsyncClient(transport=http_transport, timeout=15.0)
        session_factory = create_session_factory(engine)
        app.state.settings = resolved
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.token_verifier = WorkOSTokenVerifier(resolved, http)
        # Not opened: the API only defers jobs on its own transaction's connection.
        app.state.http = http
        app.state.workos = WorkOSClient(resolved, http)
        app.state.github = GitHubClient(resolved, http)
        app.state.jobs = create_job_app(
            resolved, session_factory, outbox.JobContext(http=http, settings=resolved)
        )
        try:
            yield
        finally:
            await http.aclose()
            await engine.dispose()

    app = FastAPI(title="Relay API", version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)
    app.add_exception_handler(PermissionDenied, _handle_permission_denied)
    app.include_router(health.router)
    app.include_router(workspaces.router)
    app.include_router(catalog_api.router)
    app.include_router(assets_api.router)
    app.include_router(knowledge_api.router)
    app.include_router(imports_api.router)
    app.include_router(notifications_api.router)
    app.include_router(notifications_api.admin)
    app.include_router(directory_api.router)
    app.include_router(risks_api.router)
    app.include_router(continuity_api.router)
    app.include_router(profile.router)
    app.include_router(members_api.router)
    app.include_router(members_api.me)
    app.include_router(github_api.router)
    app.include_router(github_api.callback)
    return app
