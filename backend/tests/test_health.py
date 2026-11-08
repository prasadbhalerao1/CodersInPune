from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from relay.app import create_app
from relay.config import Settings
from tests.conftest import make_settings

pytestmark = pytest.mark.anyio


async def client_for(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app: FastAPI = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async for c in client_for(make_settings()):
        yield c


async def test_liveness_does_not_need_dependencies(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {}}


async def test_readiness_reports_database_ok(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok"}}


async def test_readiness_returns_503_without_leaking_details() -> None:
    unreachable = make_settings(
        database_url="postgresql+psycopg://relay_app:wrong@127.0.0.1:1/relay_test",
        db_ready_timeout_seconds=1.0,
    )
    async for client in client_for(unreachable):
        response = await client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "unavailable", "checks": {"database": "unavailable"}}
