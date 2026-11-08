import asyncio
import logging
from typing import Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

CheckStatus = Literal["ok", "unavailable"]


class HealthResponse(BaseModel):
    status: CheckStatus
    checks: dict[str, CheckStatus] = {}


@router.get("/live")
async def live() -> HealthResponse:
    """Process is up. Never touches dependencies."""
    return HealthResponse(status="ok")


@router.get("/ready", responses={503: {"model": HealthResponse}})
async def ready(request: Request, response: Response) -> HealthResponse:
    """Ready to serve traffic: the database answers within the configured timeout."""
    engine: AsyncEngine = request.app.state.engine
    timeout: float = request.app.state.settings.db_ready_timeout_seconds
    try:
        async with asyncio.timeout(timeout), engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        database: CheckStatus = "ok"
    except Exception:
        # Details go to logs only; the endpoint is unauthenticated.
        logger.warning("readiness check failed: database unavailable", exc_info=True)
        database = "unavailable"
    if database != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="unavailable", checks={"database": database})
    return HealthResponse(status="ok", checks={"database": database})
