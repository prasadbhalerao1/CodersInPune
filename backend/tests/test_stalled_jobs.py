"""A job left `doing` by a dead worker is requeued by the periodic recovery task."""

import procrastinate
import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from relay.config import Settings
from relay.jobs.app import create_job_app
from tests.db import OWNER_URL, libpq_url

pytestmark = pytest.mark.anyio


async def test_stalled_jobs_are_requeued(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        dead = conn.execute(
            "INSERT INTO procrastinate_workers (last_heartbeat) "
            "VALUES (now() - interval '1 hour') RETURNING id"
        ).fetchone()[0]  # type: ignore[index]
        job = conn.execute(
            "INSERT INTO procrastinate_jobs (queue_name, task_name, args, status, worker_id) "
            "VALUES ('default', 'relay.process_outbox_event', '{}', 'doing', %s) RETURNING id",
            (dead,),
        ).fetchone()[0]  # type: ignore[index]

    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        alive = conn.execute(
            "INSERT INTO procrastinate_workers (last_heartbeat) "
            "VALUES (now() - interval '1 hour') RETURNING id"
        ).fetchone()[0]  # type: ignore[index]
        own = conn.execute(
            "INSERT INTO procrastinate_jobs (queue_name, task_name, args, status, worker_id) "
            "VALUES ('default', 'relay.retry_stalled_jobs', '{}', 'doing', %s) RETURNING id",
            (alive,),
        ).fetchone()[0]  # type: ignore[index]

    jobs = create_job_app(settings, session_factory)
    async with jobs.open_async():
        [running] = list(await jobs.job_manager.list_jobs_async(id=own))
        context = procrastinate.JobContext(
            app=jobs, job=running, start_timestamp=0, abort_reason=lambda: None
        )
        await jobs.tasks["relay.retry_stalled_jobs"].func(context, timestamp=0)

    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        status = conn.execute(
            "SELECT status FROM procrastinate_jobs WHERE id = %s", (job,)
        ).fetchone()[0]  # type: ignore[index]
        own_status = conn.execute(
            "SELECT status FROM procrastinate_jobs WHERE id = %s", (own,)
        ).fetchone()[0]  # type: ignore[index]
        conn.execute("DELETE FROM procrastinate_jobs WHERE id = ANY(%s)", ([job, own],))
    assert status == "todo"
    # The worker running the recovery (paused, so its heartbeat looks stale) is left alone.
    assert own_status == "doing"
