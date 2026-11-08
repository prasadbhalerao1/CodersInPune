"""Verification of WorkOS AuthKit access tokens (JWTs).

Checks, in order: header algorithm is allowlisted and a `kid` is present; the signing
key comes from the WorkOS JWKS; signature; `iss` equals the configured issuer; `exp`,
`iat` (and `nbf` if present) with small leeway; `aud` only if configured (a token that
carries an unexpected audience is rejected); `sub` is a non-empty string.

JWKS handling: keys are cached for `jwks_cache_seconds`. An unknown `kid` triggers a
refresh (key rotation), but at most once per `jwks_refresh_cooldown_seconds`, so forged
`kid` values cannot make Relay hammer WorkOS. If a refresh fails, cached keys keep
working until replaced; with no usable key the caller gets `JwksUnavailableError`.
"""

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import anyio
import httpx
import jwt

from relay.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    workos_user_id: str
    session_id: str | None
    expires_at: datetime


class TokenVerificationError(Exception):
    """The token is not acceptable. The message is for logs, never for clients."""


class JwksUnavailableError(Exception):
    """Signing keys could not be obtained; authentication cannot be decided."""


class WorkOSTokenVerifier:
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient) -> None:
        self._http = http_client
        self._jwks_url = settings.resolved_workos_jwks_url
        self._issuer = settings.resolved_workos_issuer
        self._audience = settings.workos_audience
        self._algorithms = list(settings.jwt_algorithms)
        self._leeway = settings.jwt_leeway_seconds
        self._cache_seconds = settings.jwks_cache_seconds
        self._cooldown_seconds = settings.jwks_refresh_cooldown_seconds
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None
        self._attempted_at: float | None = None
        self._lock = anyio.Lock()

    async def verify(self, token: str) -> VerifiedIdentity:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenVerificationError(f"malformed token: {exc}") from exc
        algorithm, kid = header.get("alg"), header.get("kid")
        if algorithm not in self._algorithms:
            raise TokenVerificationError(f"algorithm not allowed: {algorithm!r}")
        if not isinstance(kid, str) or not kid:
            raise TokenVerificationError("missing kid")

        key = await self._signing_key(kid)
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key=key,
                algorithms=self._algorithms,
                issuer=self._issuer,
                audience=self._audience,
                leeway=self._leeway,
                options={"require": ["exp", "iat", "iss", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenVerificationError(f"invalid token: {exc}") from exc

        subject, session_id = claims.get("sub"), claims.get("sid")
        if not isinstance(subject, str) or not 0 < len(subject) <= 255:
            raise TokenVerificationError("invalid sub claim")
        if session_id is not None and not isinstance(session_id, str):
            raise TokenVerificationError("invalid sid claim")
        return VerifiedIdentity(
            workos_user_id=subject,
            session_id=session_id,
            expires_at=datetime.fromtimestamp(int(claims["exp"]), UTC),
        )

    async def _signing_key(self, kid: str) -> jwt.PyJWK:
        if kid in self._keys and self._is_fresh():
            return self._keys[kid]
        async with self._lock:
            if kid in self._keys and self._is_fresh():
                return self._keys[kid]
            if self._may_refresh():
                await self._refresh()
            if kid in self._keys:
                return self._keys[kid]
        if self._fetched_at is None:
            raise JwksUnavailableError("no signing keys available")
        raise TokenVerificationError(f"unknown signing key: {kid!r}")

    def _is_fresh(self) -> bool:
        return (
            self._fetched_at is not None
            and time.monotonic() - self._fetched_at < self._cache_seconds
        )

    def _may_refresh(self) -> bool:
        return (
            self._attempted_at is None
            or time.monotonic() - self._attempted_at >= self._cooldown_seconds
            or not self._is_fresh()
        )

    async def _refresh(self) -> None:
        self._attempted_at = time.monotonic()
        try:
            response = await self._http.get(self._jwks_url)
            response.raise_for_status()
            jwk_set = jwt.PyJWKSet.from_dict(response.json())
        except httpx.HTTPError, ValueError, jwt.PyJWTError:
            logger.warning("WorkOS JWKS refresh failed", exc_info=True)
            return
        keys = {
            k.key_id: k
            for k in jwk_set.keys
            if k.key_id
            and k.public_key_use in (None, "sig")
            and k.algorithm_name in self._algorithms
        }
        if not keys:
            logger.warning("WorkOS JWKS contained no usable signing keys")
            return
        self._keys = keys
        self._fetched_at = time.monotonic()
