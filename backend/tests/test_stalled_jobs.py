"""A job left `doing` by a dead worker is requeued by the periodic recovery task."""

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

    jobs = create_job_app(settings, session_factory)
    async with jobs.open_async():
        await jobs.tasks["relay.retry_stalled_jobs"].func(timestamp=0)

    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        status = conn.execute(
            "SELECT status FROM procrastinate_jobs WHERE id = %s", (job,)
        ).fetchone()[0]  # type: ignore[index]
        workers = conn.execute(
            "SELECT count(*) FROM procrastinate_workers WHERE id = %s", (dead,)
        ).fetchone()[0]  # type: ignore[index]
        conn.execute("DELETE FROM procrastinate_jobs WHERE id = %s", (job,))
    assert status == "todo"
    assert workers == 0  # the dead worker is pruned
