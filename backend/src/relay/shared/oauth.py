"""OAuth token grants shared by the Linear and Notion integrations.

Providers that issue short-lived access tokens also return `refresh_token` and
`expires_in`; long-lived tokens come without them. Both shapes are handled the same way:
store what was granted, refresh shortly before expiry or after a 401, and only report a
connection as revoked when the provider rejects the refresh itself.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from relay.config import Settings
from relay.shared import secrets as secret_box

REFRESH_MARGIN = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class TokenGrant:
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None

    @classmethod
    def from_response(cls, body: dict[str, Any]) -> TokenGrant | None:
        token = body.get("access_token")
        if not isinstance(token, str):
            return None
        refresh = body.get("refresh_token")
        expires_in = body.get("expires_in")
        return cls(
            access_token=token,
            refresh_token=refresh if isinstance(refresh, str) else None,
            expires_at=datetime.now(UTC) + timedelta(seconds=int(expires_in))
            if isinstance(expires_in, int | float)
            else None,
        )


class TokenHolder(Protocol):
    token_ciphertext: str | None
    refresh_token_ciphertext: str | None
    token_expires_at: datetime | None


def store(settings: Settings, holder: TokenHolder, grant: TokenGrant) -> None:
    holder.token_ciphertext = secret_box.encrypt(settings, grant.access_token)
    if grant.refresh_token is not None:  # some providers keep the old refresh token valid
        holder.refresh_token_ciphertext = secret_box.encrypt(settings, grant.refresh_token)
    holder.token_expires_at = grant.expires_at


def forget(holder: TokenHolder) -> None:
    holder.token_ciphertext = holder.refresh_token_ciphertext = None
    holder.token_expires_at = None


def expiring(holder: TokenHolder) -> bool:
    expires = holder.token_expires_at
    return expires is not None and expires - datetime.now(UTC) < REFRESH_MARGIN
