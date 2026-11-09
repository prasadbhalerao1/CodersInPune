"""Per-user rate limits for authentication-sensitive and expensive endpoints.

A sliding window kept in process memory, keyed by the verified WorkOS user and a bucket
name. Relay runs one API process per deployment (deploy/README.md), so this is exact
there; with several replicas each enforces its own window (a looser, still useful limit).
No Redis: the Decision Register rules out new infrastructure without a trigger.

Usage: `@router.post(..., dependencies=[rate_limit("imports", 20, 60)])`.
"""

import math
import time
from collections import deque
from typing import Any

from fastapi import Depends

from relay.identity.auth import Identity
from relay.shared.errors import ApiError

_MAX_KEYS = 50_000
_hits: dict[tuple[str, str], deque[float]] = {}


def _check(key: tuple[str, str], limit: int, window: float, now: float) -> float | None:
    """Record a hit; return seconds to wait if the limit is exceeded, else None."""
    hits = _hits.get(key)
    if hits is None:
        if len(_hits) >= _MAX_KEYS:  # bounded memory: drop the oldest windows
            for stale in list(_hits)[: _MAX_KEYS // 10]:
                del _hits[stale]
        hits = _hits[key] = deque()
    while hits and hits[0] <= now - window:
        hits.popleft()
    if len(hits) >= limit:
        return hits[0] + window - now
    hits.append(now)
    return None


def rate_limit(bucket: str, limit: int, window_seconds: float) -> Any:
    async def dependency(identity: Identity) -> None:
        wait = _check((bucket, identity.workos_user_id), limit, window_seconds, time.monotonic())
        if wait is not None:
            raise ApiError(
                429,
                "rate_limited",
                "Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": str(max(1, math.ceil(wait)))},
            )

    return Depends(dependency)


def reset() -> None:
    """Tests only."""
    _hits.clear()
