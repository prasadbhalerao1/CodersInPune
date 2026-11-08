"""Outbox producer and consumer.

Producer (`emit`): inserts the outbox row and defers the Procrastinate job on the *same*
psycopg connection, inside the caller's transaction (Procrastinate's documented
`configure(connection=...)` external-connection deferral). Both commit or neither does, so
there is no post-commit delivery gap and no cross-tenant sweep is needed.

Consumer (`process`): runs as `relay_app` with the job's tenant as context. It locks the
event row, skips it if already processed (duplicate delivery), runs the handler, marks the
event processed and records the outcome, all in one transaction.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any

import httpx
import procrastinate
from fastapi import Depends, Request
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.audit import service as audit
from relay.config import Settings
from relay.jobs.models import OutboxEvent
from relay.shared.db.session import unit_of_work

logger = logging.getLogger(__name__)

PROCESS_TASK = "relay.process_outbox_event"


@dataclass(frozen=True, slots=True)
class JobContext:
    """Services a handler may need (e.g. outbound HTTP); built once per worker."""

    http: httpx.AsyncClient | None = None
    settings: Settings | None = None


Handler = Callable[[AsyncSession, OutboxEvent, JobContext], Awaitable[None]]


async def _workspace_created(_session: AsyncSession, _event: OutboxEvent, _ctx: JobContext) -> None:
    # First consumer: no downstream work yet. Processing proves the pipeline end to end;
    # M1+ handlers (e.g. seeding defaults) attach here.
    return None


HANDLERS: dict[str, Handler] = {"workspace.created": _workspace_created}


def register(event_type: str, handler: Handler) -> None:
    """Register a handler for an event type (modules call this at import time)."""
    HANDLERS[event_type] = handler


async def emit(
    session: AsyncSession,
    jobs: procrastinate.App,
    *,
    tenant_id: uuid.UUID,
    event_type: str,
    payload: dict[str, Any],
    schedule_at: datetime | None = None,
) -> uuid.UUID:
    """`schedule_at` delays processing (e.g. reminders); the row commits with the caller."""
    if event_type not in HANDLERS:
        raise ValueError(f"no handler registered for {event_type!r}")
    event_id = uuid.uuid7()
    session.add(
        OutboxEvent(id=event_id, tenant_id=tenant_id, event_type=event_type, payload=payload)
    )
    await session.flush()
    connection = await (await session.connection()).get_raw_connection()
    await (
        jobs.tasks[PROCESS_TASK]
        .configure(connection=connection.driver_connection, schedule_at=schedule_at)
        .defer_async(tenant_id=str(tenant_id), event_id=str(event_id))
    )
    return event_id


async def process(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    ctx: JobContext | None = None,
) -> bool:
    """Process one event. Returns False if it was already processed or is not visible."""
    try:
        async with unit_of_work(factory, tenant_id) as session:
            event = await session.scalar(
                select(OutboxEvent).where(OutboxEvent.id == event_id).with_for_update()
            )
            if event is None:
                # Not in this tenant (or gone): never act on another tenant's event.
                logger.warning("outbox event %s not visible in tenant %s", event_id, tenant_id)
                return False
            if event.processed_at is not None:
                return False
            await HANDLERS[event.event_type](session, event, ctx or JobContext())
            event.processed_at = func.now()
            event.attempts += 1
            event.last_error_type = None
            audit.record(
                session,
                tenant_id=tenant_id,
                action="job.outbox_event.processed",
                actor_user_id=None,
                target_type="outbox_event",
                target_id=event_id,
                details={"event_type": event.event_type, "attempt": event.attempts},
            )
            return True
    except Exception as exc:
        await _record_failure(factory, tenant_id, event_id, exc)
        raise


async def _record_failure(
    factory: async_sessionmaker[AsyncSession],
    tenant_id: uuid.UUID,
    event_id: uuid.UUID,
    exc: Exception,
) -> None:
    error_type = type(exc).__name__
    try:
        async with unit_of_work(factory, tenant_id) as session:
            result = await session.execute(
                update(OutboxEvent)
                .where(OutboxEvent.id == event_id, OutboxEvent.processed_at.is_(None))
                .values(attempts=OutboxEvent.attempts + 1, last_error_type=error_type)
                .returning(OutboxEvent.event_type, OutboxEvent.attempts)
            )
            row = result.one_or_none()
            if row is not None:
                audit.record(
                    session,
                    tenant_id=tenant_id,
                    action="job.outbox_event.failed",
                    actor_user_id=None,
                    target_type="outbox_event",
                    target_id=event_id,
                    details={"event_type": row[0], "attempt": row[1], "error_type": error_type},
                )
    except Exception:
        logger.exception("could not record failure of outbox event %s", event_id)


def _jobs(request: Request) -> procrastinate.App:
    jobs: procrastinate.App = request.app.state.jobs
    return jobs


Jobs = Annotated[procrastinate.App, Depends(_jobs)]
