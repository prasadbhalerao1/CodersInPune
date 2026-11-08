"""Background worker: `uv run relay-worker`. One process, restricted app role."""

import asyncio
import logging
import sys

import httpx

from relay.config import Settings
from relay.jobs import outbox
from relay.jobs.app import create_job_app
from relay.shared.db import create_engine, create_session_factory


async def run() -> None:
    settings = Settings()
    engine = create_engine(settings)
    http = httpx.AsyncClient(timeout=15.0)
    ctx = outbox.JobContext(http=http, settings=settings)
    jobs = create_job_app(settings, create_session_factory(engine), ctx)
    try:
        async with jobs.open_async():
            await jobs.run_worker_async(concurrency=settings.worker_concurrency)
    finally:
        await http.aclose()
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    # psycopg async needs a selector loop on Windows (see relay/__main__.py).
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(run(), loop_factory=loop_factory)


if __name__ == "__main__":
    main()
