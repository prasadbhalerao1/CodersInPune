"""Run the API: `uv run relay-api` (or `uv run python -m relay`).

psycopg's async driver cannot run on Windows' default ProactorEventLoop, so the
server is started on a SelectorEventLoop there. Linux/macOS use the default loop.
"""

import asyncio
import sys

import uvicorn

from relay.config import Settings
from relay.shared.observability import configure_logging


def main() -> None:
    settings = Settings()
    configure_logging(settings.json_logs)
    config = uvicorn.Config(
        "relay.app:create_app",
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        # SIGTERM: stop accepting connections, let in-flight requests finish.
        timeout_graceful_shutdown=20,
        server_header=False,
        access_log=False,  # replaced by relay.access (route templates, request ids)
        log_config=None,
    )
    server = uvicorn.Server(config)
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(server.serve(), loop_factory=loop_factory)


if __name__ == "__main__":
    main()
