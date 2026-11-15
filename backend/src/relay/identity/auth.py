"""Authentication dependency: who is calling? (Not: what may they do.)"""

import logging
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from relay.identity.tokens import (
    JwksUnavailableError,
    TokenVerificationError,
    VerifiedIdentity,
    WorkOSTokenVerifier,
)
from relay.shared.errors import ApiError

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)
_CHALLENGE = {"WWW-Authenticate": 'Bearer realm="relay"'}


async def get_identity(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> VerifiedIdentity:
    if credentials is None:
        raise ApiError(401, "unauthenticated", "Authentication required.", _CHALLENGE)
    verifier: WorkOSTokenVerifier = request.app.state.token_verifier
    try:
        return await verifier.verify(credentials.credentials)
    except TokenVerificationError as exc:
        logger.info("rejected access token: %s", exc)
        raise ApiError(
            401, "invalid_token", "The access token is invalid or expired.", _CHALLENGE
        ) from exc
    except JwksUnavailableError as exc:
        logger.error("cannot verify access tokens: %s", exc)
        raise ApiError(
            503, "auth_unavailable", "Authentication is temporarily unavailable."
        ) from exc


Identity = Annotated[VerifiedIdentity, Depends(get_identity)]
