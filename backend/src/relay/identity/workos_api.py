"""Minimal server-side WorkOS User Management client.

Endpoints (WorkOS API reference, checked 2026-11-08):
- GET  /user_management/users/{id}                 → verified email for invitation binding
- POST /user_management/invitations                → sends the invitation email
- POST /user_management/invitations/{id}/revoke
"""

import logging
from dataclasses import dataclass

import httpx

from relay.config import Settings

logger = logging.getLogger(__name__)


class WorkOSUnavailableError(Exception):
    """WorkOS is not configured or did not answer; the caller decides how to degrade."""


@dataclass(frozen=True, slots=True)
class WorkOSUser:
    id: str
    email: str
    email_verified: bool
    display_name: str | None


class WorkOSClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._base = settings.workos_api_base_url.rstrip("/")
        self._key = settings.workos_api_key.get_secret_value() if settings.workos_api_key else None
        self._http = http

    @property
    def configured(self) -> bool:
        return self._key is not None

    async def _request(self, method: str, path: str, json: object = None) -> dict[str, object]:
        if self._key is None:
            raise WorkOSUnavailableError("RELAY_WORKOS_API_KEY is not configured")
        try:
            response = await self._http.request(
                method,
                f"{self._base}{path}",
                json=json,
                headers={"Authorization": f"Bearer {self._key}"},
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise WorkOSUnavailableError(f"WorkOS request failed: {type(exc).__name__}") from exc
        if not isinstance(data, dict):
            raise WorkOSUnavailableError("unexpected WorkOS response")
        return data

    async def get_user(self, user_id: str) -> WorkOSUser:
        data = await self._request("GET", f"/user_management/users/{user_id}")
        names = [data.get("first_name"), data.get("last_name")]
        return WorkOSUser(
            id=str(data["id"]),
            email=str(data["email"]).lower(),
            email_verified=data.get("email_verified") is True,
            display_name=" ".join(str(n) for n in names if n) or None,
        )

    async def send_invitation(self, email: str, expires_in_days: int) -> str | None:
        """Best effort: returns the WorkOS invitation id, or None if the email wasn't sent."""
        try:
            data = await self._request(
                "POST",
                "/user_management/invitations",
                {"email": email, "expires_in_days": expires_in_days},
            )
        except WorkOSUnavailableError:
            logger.warning("invitation email not sent", exc_info=True)
            return None
        return str(data["id"])

    async def revoke_invitation(self, invitation_id: str) -> None:
        try:
            await self._request("POST", f"/user_management/invitations/{invitation_id}/revoke")
        except WorkOSUnavailableError:
            logger.warning("WorkOS invitation %s not revoked", invitation_id, exc_info=True)
