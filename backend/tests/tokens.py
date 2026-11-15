"""Test signing keys and a JWKS endpoint double.

Tokens are real RS256 JWTs signed with freshly generated RSA keys, so verification code
paths (signature, claims, key selection) run for real. Only the HTTP response that would
come from WorkOS's JWKS endpoint is simulated.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

CLIENT_ID = "client_test"
ISSUER = f"https://api.workos.com/user_management/{CLIENT_ID}"
JWKS_PATH = f"/sso/jwks/{CLIENT_ID}"


@dataclass
class SigningKey:
    kid: str
    private_key: rsa.RSAPrivateKey = field(
        default_factory=lambda: rsa.generate_private_key(public_exponent=65537, key_size=2048)
    )

    def public_jwk(self) -> dict[str, Any]:
        jwk: dict[str, Any] = RSAAlgorithm.to_jwk(self.private_key.public_key(), as_dict=True)
        return {**jwk, "kid": self.kid, "alg": "RS256", "use": "sig"}


@dataclass
class JwksServer:
    keys: list[SigningKey]
    available: bool = True
    requests: int = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests += 1
        if request.url.path != JWKS_PATH or not self.available:
            return httpx.Response(503)
        return httpx.Response(200, json={"keys": [k.public_jwk() for k in self.keys]})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)


def make_token(
    key: SigningKey,
    sub: str | None = None,
    *,
    issuer: str = ISSUER,
    ttl: int = 300,
    issued_offset: int = 0,
    kid: str | None = None,
    algorithm: str = "RS256",
    extra: dict[str, Any] | None = None,
    omit: tuple[str, ...] = (),
) -> str:
    now = int(time.time()) + issued_offset
    claims: dict[str, Any] = {
        "sub": sub or f"user_{uuid.uuid4().hex}",
        "sid": f"session_{uuid.uuid4().hex}",
        "iss": issuer,
        "iat": now,
        "exp": now + ttl,
        **(extra or {}),
    }
    for name in omit:
        claims.pop(name, None)
    return jwt.encode(claims, key.private_key, algorithm=algorithm, headers={"kid": kid or key.kid})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
