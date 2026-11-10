"""Background worker: `uv run relay-worker`. One process, restricted app role."""

import asyncio
import sys

import httpx

from relay.config import Settings
from relay.jobs import outbox
from relay.jobs.app import create_job_app
from relay.shared.db import create_engine, create_session_factory
from relay.shared.observability import configure_logging


async def run() -> None:
    settings = Settings()
    engine = create_engine(settings)
    http = httpx.AsyncClient(timeout=15.0)
    ctx = outbox.JobContext(http=http, settings=settings)
    jobs = create_job_app(settings, create_session_factory(engine), ctx)
    try:
        async with jobs.open_async():
            # SIGTERM/SIGINT stop fetching new jobs; running jobs get the grace period,
            # after which they are cancelled and retried by the outbox (idempotent handlers).
            await jobs.run_worker_async(
                concurrency=settings.worker_concurrency,
                shutdown_graceful_timeout=settings.worker_shutdown_seconds,
                install_signal_handlers=True,
            )
    finally:
        await http.aclose()
        await engine.dispose()


def main() -> None:
    configure_logging(Settings().json_logs)
    # psycopg async needs a selector loop on Windows (see relay/__main__.py).
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(run(), loop_factory=loop_factory)


if __name__ == "__main__":
    main()
