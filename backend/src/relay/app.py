from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from relay import health
from relay.config import Settings
from relay.identity.tokens import WorkOSTokenVerifier
from relay.platform import workspaces
from relay.shared.db import create_engine, create_session_factory
from relay.shared.errors import register_error_handlers


def create_app(
    settings: Settings | None = None,
    jwks_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Build the API. `jwks_transport` lets tests serve a JWKS without network access."""
    resolved = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(resolved)
        http = httpx.AsyncClient(transport=jwks_transport, timeout=5.0)
        app.state.settings = resolved
        app.state.engine = engine
        app.state.session_factory = create_session_factory(engine)
        app.state.token_verifier = WorkOSTokenVerifier(resolved, http)
        try:
            yield
        finally:
            await http.aclose()
            await engine.dispose()

    app = FastAPI(title="Relay API", version="0.1.0", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(workspaces.router)
    return app
