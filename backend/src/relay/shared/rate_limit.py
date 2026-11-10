"""Per-user rate limits for authentication-sensitive and expensive endpoints.

Counters live in PostgreSQL (`platform.rate_limit_hit`, migration 0038), so every API
replica enforces the same limit; no Redis (the Decision Register rules out new
infrastructure without a trigger). Fixed windows keyed by bucket and verified WorkOS user:
a burst can reach twice the limit across a window boundary, which these coarse abuse
limits tolerate.

Usage: `@router.post(..., dependencies=[rate_limit("imports", 20, 60)])`.
"""

from typing import Any

from fastapi import Depends, Request
from sqlalchemy import func, select

from relay.identity.auth import Identity
from relay.shared.errors import ApiError


def rate_limit(bucket: str, limit: int, window_seconds: int) -> Any:
    async def dependency(identity: Identity, request: Request) -> None:
        async with request.app.state.engine.connect() as conn:
            wait = await conn.scalar(
                select(
                    func.platform.rate_limit_hit(
                        bucket, identity.workos_user_id, limit, window_seconds
                    )
                )
            )
            await conn.commit()
        if wait:
            raise ApiError(
                429,
                "rate_limited",
                "Too many requests. Please wait a moment and try again.",
                headers={"Retry-After": str(wait)},
            )

    return Depends(dependency)
