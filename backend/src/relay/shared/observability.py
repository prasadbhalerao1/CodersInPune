"""Request correlation, structured access logs and the versioned API prefix.

- Every request gets a correlation id: the caller's `X-Request-ID` when it is a safe
  token, otherwise a new one. It is returned in the response header and attached to every
  log record emitted while handling the request, so logs from the API, a job it queued
  and the browser's error report can be joined.
- One structured access-log line per request (method, route, status, duration). Bodies,
  query strings and headers are never logged: they can carry tokens or personal data.
- `/api/v1/...` is the versioned public path; it serves the same handlers as the
  unversioned path the web app uses today.
"""

import contextvars
import json
import logging
import re
import time
import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
VERSION_PREFIX = "/api/v1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
access_log = logging.getLogger("relay.access")


class CorrelationFilter(logging.Filter):
    """Adds `request_id` to every record (None outside a request)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        for key in ("method", "route", "status", "duration_ms"):
            if hasattr(record, key):
                entry[key] = getattr(record, key)
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info).splitlines()[-1]
        return json.dumps(entry)


def configure_logging(json_logs: bool, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(CorrelationFilter())
    handler.setFormatter(
        JsonFormatter() if json_logs else logging.Formatter("%(levelname)s %(name)s %(message)s")
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


class RequestContextMiddleware:
    """Pure ASGI (no buffering): correlation id, versioned prefix, access log."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope["path"]
        if path == VERSION_PREFIX or path.startswith(VERSION_PREFIX + "/"):
            scope = {**scope, "path": path[len(VERSION_PREFIX) :] or "/"}
        incoming = next(
            (v.decode() for k, v in scope.get("headers", []) if k == b"x-request-id"), ""
        )
        request_id = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex
        token = REQUEST_ID.set(request_id)
        started = time.monotonic()
        status = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message["headers"] = [
                    *message.get("headers", []),
                    (b"x-request-id", request_id.encode()),
                ]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            route = scope.get("route")
            access_log.info(
                "request",
                extra={
                    "method": scope["method"],
                    # The route template, never the concrete path (it can contain ids).
                    "route": getattr(route, "path", "unmatched"),
                    "status": status,
                    "duration_ms": round((time.monotonic() - started) * 1000, 1),
                },
            )
            REQUEST_ID.reset(token)
