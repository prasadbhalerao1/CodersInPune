import asyncio
import hmac
import logging
from typing import Literal

from fastapi import APIRouter, Header, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
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
            await conn.execute(select(1))
        database: CheckStatus = "ok"
    except Exception:
        # Details go to logs only; the endpoint is unauthenticated.
        logger.warning("readiness check failed: database unavailable", exc_info=True)
        database = "unavailable"
    if database != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="unavailable", checks={"database": database})
    return HealthResponse(status="ok", checks={"database": database})


# Alert when a count crosses its threshold. Each name is an actionable condition with a
# runbook entry (docs/runbooks/incident-response.md#alerts); counts never identify a tenant.
THRESHOLDS: dict[str, tuple[str, int]] = {
    "worker_down": ("worker_heartbeat_age_s", 300),
    "queue_backlog": ("oldest_ready_age_s", 900),
    "jobs_failing": ("jobs_failed_1h", 5),
    "events_failing": ("events_failing", 3),
    "connector_unhealthy": ("connectors_unhealthy", 1),
    "email_failing": ("emails_failed_24h", 3),
    "ai_failing": ("ai_runs_failed_24h", 3),
    "ai_budget_exhausted": ("ai_budget_exhausted_24h", 1),
}


class OpsResponse(BaseModel):
    status: Literal["ok", "alert", "unavailable"]
    alerts: list[str] = []
    counts: dict[str, int | None] = {}


@router.get("/ops", responses={503: {"model": OpsResponse}})
async def ops(
    request: Request, response: Response, authorization: str | None = Header(default=None)
) -> OpsResponse:
    """Operator view for the uptime monitor: aggregate counts and the alerts they raise."""
    token = request.app.state.settings.ops_token
    supplied = (authorization or "").removeprefix("Bearer ")
    if token is None or not hmac.compare_digest(
        supplied.encode(), token.get_secret_value().encode()
    ):
        response.status_code = status.HTTP_404_NOT_FOUND
        return OpsResponse(status="unavailable")
    engine: AsyncEngine = request.app.state.engine
    try:
        async with asyncio.timeout(10), engine.connect() as conn:
            counts: dict[str, int | None] = (
                await conn.scalar(select(func.platform.ops_summary())) or {}
            )
            await conn.commit()
    except Exception:
        logger.warning("ops summary failed: database unavailable", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return OpsResponse(status="unavailable", alerts=["database_unavailable"])
    alerts = [
        name
        for name, (key, limit) in THRESHOLDS.items()
        if ((value := counts.get(key)) is None and name == "worker_down")
        or (value is not None and value >= limit)
    ]
    return OpsResponse(status="alert" if alerts else "ok", alerts=alerts, counts=counts)
