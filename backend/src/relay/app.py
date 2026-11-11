import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay import health
from relay.audit import service as audit
from relay.automation import api as automation_api
from relay.catalog import api as catalog_api
from relay.catalog import assets_api, knowledge_api
from relay.config import Settings
from relay.continuity import api as continuity_api
from relay.demo import api as demo_api
from relay.directory import api as directory_api
from relay.identity import members_api, profile
from relay.identity.tokens import WorkOSTokenVerifier
from relay.identity.workos_api import WorkOSClient
from relay.imports import api as imports_api
from relay.insights import api as insights_api
from relay.integrations import api as integrations_api
from relay.integrations.github import api as github_api
from relay.integrations.github.client import GitHubClient
from relay.integrations.linear import api as linear_api
from relay.integrations.linear.client import LinearClient
from relay.integrations.notion import api as notion_api
from relay.integrations.notion.client import NotionClient
from relay.intelligence import api as intelligence_api
from relay.jobs import outbox
from relay.jobs.app import create_job_app
from relay.notifications import api as notifications_api
from relay.platform import workspaces
from relay.policy.permissions import PermissionDenied
from relay.risks import api as risks_api
from relay.search import api as search_api
from relay.shared.db import create_engine, create_session_factory, unit_of_work
from relay.shared.errors import api_error_response, register_error_handlers
from relay.shared.observability import RequestContextMiddleware

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


async def _embedded_worker(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession], http: httpx.AsyncClient
) -> None:
    """The job worker inside the API process, for single-instance hosting without a
    separate worker service. Jobs are idempotent, so a restart mid-job retries safely."""
    jobs = create_job_app(
        settings, session_factory, outbox.JobContext(http=http, settings=settings)
    )
    async with jobs.open_async():
        await jobs.run_worker_async(
            concurrency=settings.worker_concurrency,
            shutdown_graceful_timeout=settings.worker_shutdown_seconds,
            install_signal_handlers=False,
        )


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
        app.state.linear = LinearClient(resolved, http)
        app.state.notion = NotionClient(resolved, http)
        app.state.jobs = create_job_app(
            resolved, session_factory, outbox.JobContext(http=http, settings=resolved)
        )
        worker = (
            asyncio.create_task(_embedded_worker(resolved, session_factory, http))
            if resolved.embedded_worker
            else None
        )
        try:
            yield
        finally:
            if worker is not None:
                worker.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await worker
            await http.aclose()
            await engine.dispose()

    # The schema and interactive docs are for development; production exposes neither.
    docs = resolved.environment != "production"
    app = FastAPI(
        title="Relay API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    register_error_handlers(app)
    app.add_middleware(RequestContextMiddleware)
    app.add_exception_handler(PermissionDenied, _handle_permission_denied)
    app.include_router(health.router)
    app.include_router(integrations_api.router)
    app.include_router(demo_api.router)  # before `workspaces` so /sample is not an id
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
    app.include_router(linear_api.router)
    app.include_router(linear_api.callback)
    app.include_router(notion_api.router)
    app.include_router(notion_api.callback)
    app.include_router(insights_api.router)
    app.include_router(automation_api.router)
    app.include_router(intelligence_api.router)
    app.include_router(search_api.router)
    return app
