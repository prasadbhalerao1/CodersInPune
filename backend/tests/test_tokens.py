"""WorkOS access-token verification (unit level).

Real RS256 signing and verification; only the JWKS HTTP response is simulated
(see tests/tokens.py). These tests do not prove anything about real WorkOS tokens:
that requires the manual end-to-end check described in README.
"""

import time
from collections.abc import AsyncIterator

import httpx
import jwt
import pytest

from relay.identity.tokens import JwksUnavailableError, TokenVerificationError, WorkOSTokenVerifier
from tests.conftest import make_settings
from tests.tokens import JwksServer, SigningKey, make_token

pytestmark = pytest.mark.anyio


@pytest.fixture
def key() -> SigningKey:
    return SigningKey(kid="key-1")


@pytest.fixture
def jwks(key: SigningKey) -> JwksServer:
    return JwksServer(keys=[key])


@pytest.fixture
async def verifier(jwks: JwksServer) -> AsyncIterator[WorkOSTokenVerifier]:
    async with httpx.AsyncClient(transport=jwks.transport) as http:
        yield WorkOSTokenVerifier(make_settings(), http)


async def rejects(verifier: WorkOSTokenVerifier, token: str) -> None:
    with pytest.raises(TokenVerificationError):
        await verifier.verify(token)


async def test_valid_token_yields_identity(verifier: WorkOSTokenVerifier, key: SigningKey) -> None:
    identity = await verifier.verify(make_token(key, "user_01ABC"))
    assert identity.workos_user_id == "user_01ABC"
    assert identity.session_id is not None


async def test_expired_token_is_rejected(verifier: WorkOSTokenVerifier, key: SigningKey) -> None:
    await rejects(verifier, make_token(key, ttl=300, issued_offset=-3600))


async def test_wrong_issuer_is_rejected(verifier: WorkOSTokenVerifier, key: SigningKey) -> None:
    await rejects(verifier, make_token(key, issuer="https://api.workos.com/user_management/other"))


async def test_token_signed_by_another_key_with_same_kid_is_rejected(
    verifier: WorkOSTokenVerifier,
) -> None:
    forger = SigningKey(kid="key-1")
    await rejects(verifier, make_token(forger))


@pytest.mark.parametrize("claim", ["sub", "exp", "iat", "iss"])
async def test_missing_required_claim_is_rejected(
    verifier: WorkOSTokenVerifier, key: SigningKey, claim: str
) -> None:
    await rejects(verifier, make_token(key, omit=(claim,)))


async def test_unexpected_audience_is_rejected(
    verifier: WorkOSTokenVerifier, key: SigningKey
) -> None:
    await rejects(verifier, make_token(key, extra={"aud": "someone-else"}))


async def test_unsigned_and_symmetric_algorithms_are_rejected(
    verifier: WorkOSTokenVerifier, key: SigningKey
) -> None:
    unsigned = jwt.encode({"sub": "user_x"}, key="", algorithm="none", headers={"kid": "key-1"})
    await rejects(verifier, unsigned)
    # Algorithm confusion: HS256 "signed" with the public key as the shared secret.
    public_material = key.public_jwk()["n"].encode()
    confused = jwt.encode(
        {"sub": "user_x"}, key=public_material, algorithm="HS256", headers={"kid": "key-1"}
    )
    await rejects(verifier, confused)


async def test_malformed_token_is_rejected(verifier: WorkOSTokenVerifier) -> None:
    await rejects(verifier, "not-a-jwt")


async def test_key_rotation_is_picked_up_on_unknown_kid(
    verifier: WorkOSTokenVerifier,
    jwks: JwksServer,
    key: SigningKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await verifier.verify(make_token(key))
    rotated = SigningKey(kid="key-2")
    jwks.keys = [rotated]
    # Within the refresh cooldown an unknown kid is rejected without refetching ...
    await rejects(verifier, make_token(rotated))
    assert jwks.requests == 1
    # ... and once the cooldown has passed, the rotated key is fetched and accepted.
    real_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + 31)
    identity = await verifier.verify(make_token(rotated, "user_rotated"))
    assert identity.workos_user_id == "user_rotated"
    assert jwks.requests == 2


async def test_unknown_kids_do_not_cause_unbounded_jwks_fetches(
    verifier: WorkOSTokenVerifier, jwks: JwksServer, key: SigningKey
) -> None:
    await verifier.verify(make_token(key))
    for i in range(5):
        await rejects(verifier, make_token(key, kid=f"forged-{i}"))
    # One initial fetch + at most one cooldown-limited refresh.
    assert jwks.requests <= 2


async def test_jwks_outage_without_cached_keys_is_unavailable_not_invalid(
    verifier: WorkOSTokenVerifier, jwks: JwksServer, key: SigningKey
) -> None:
    jwks.available = False
    with pytest.raises(JwksUnavailableError):
        await verifier.verify(make_token(key))


async def test_cached_keys_survive_jwks_outage(
    verifier: WorkOSTokenVerifier, jwks: JwksServer, key: SigningKey
) -> None:
    await verifier.verify(make_token(key))
    jwks.available = False
    await verifier.verify(make_token(key))
