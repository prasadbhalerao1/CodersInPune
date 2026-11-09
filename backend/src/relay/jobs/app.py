"""Procrastinate application. Execution mechanism only; the outbox is the source of truth."""

import dataclasses
import logging
import uuid

import procrastinate
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

# Imported for their side effects: modules register outbox handlers at import time, and
# relay.models completes the ORM metadata for cross-module foreign keys.
import relay.automation.service
import relay.integrations.github.service
import relay.integrations.github.webhooks
import relay.integrations.linear.service
import relay.integrations.notion.service
import relay.intelligence.capsules
import relay.intelligence.interviews
import relay.intelligence.runs
import relay.models
import relay.notifications.service
from relay.config import Settings
from relay.jobs import outbox

# Retries cover transient failures (DB restarts, deadlocks). After the last attempt the
# job is `failed` and can be retried manually (`procrastinate ... retry`); the outbox row
# stays unprocessed, so no work is lost.
RETRY = procrastinate.RetryStrategy(max_attempts=5, exponential_wait=2)
# Workers heartbeat every 10 s; one silent for this long is gone.
STALLED_AFTER = 120.0
logger = logging.getLogger(__name__)


def libpq_conninfo(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def create_job_app(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    ctx: outbox.JobContext | None = None,
) -> procrastinate.App:
    """Same restricted `relay_app` role as the API; jobs never bypass RLS."""
    app = procrastinate.App(
        connector=procrastinate.PsycopgConnector(
            conninfo=libpq_conninfo(settings.database_url),
            kwargs={"prepare_threshold": None},
        )
    )

    ctx = dataclasses.replace(ctx or outbox.JobContext(), jobs=app)

    @app.task(name=outbox.PROCESS_TASK, retry=RETRY)
    async def process_outbox_event(tenant_id: str, event_id: str) -> None:
        await outbox.process(session_factory, uuid.UUID(tenant_id), uuid.UUID(event_id), ctx)

    @app.periodic(cron="17 */6 * * *")
    @app.task(name="relay.github_reconcile", queueing_lock="github_reconcile")
    async def github_reconcile(timestamp: int) -> None:
        await relay.integrations.github.webhooks.reconcile(session_factory, app)

    @app.periodic(cron="*/5 * * * *")
    @app.task(
        name="relay.retry_stalled_jobs", queueing_lock="retry_stalled_jobs", pass_context=True
    )
    async def retry_stalled_jobs(context: procrastinate.JobContext, timestamp: int) -> None:
        """A worker that died mid-job (crash, OOM, SIGKILL) leaves its job `doing` forever.
        Requeue jobs whose worker stopped heartbeating; handlers are idempotent.

        Never the jobs of the worker running this task: after a long pause (e.g. the host
        slept) its own heartbeat can look stale while it is very much alive. Procrastinate
        prunes dead worker rows itself (`stalled_worker_timeout`)."""
        own = context.job.worker_id
        stalled = await app.job_manager.get_stalled_jobs(seconds_since_heartbeat=STALLED_AFTER)
        for job in stalled:
            if job.worker_id == own:
                continue
            logger.warning("retrying stalled job %s (%s)", job.id, job.task_name)
            await app.job_manager.retry_job(job)

    return app
