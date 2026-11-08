"""Email provider boundary: one small interface, one implementation (Resend).

`send()` returns the provider's message id only once the provider has accepted the
message. Failures are classified as transient (timeouts, 429, 5xx: retry with backoff)
or permanent (other 4xx: do not retry). Error codes are short and never contain the API
key or message content. The same idempotency key is sent on every retry, so even a
retry after an unseen success cannot produce a second email.
"""

from dataclasses import dataclass
from typing import Protocol

import httpx

from relay.config import Settings


@dataclass(frozen=True, slots=True)
class EmailMessage:
    to: str
    subject: str
    html: str
    text: str
    idempotency_key: str


class EmailSendError(Exception):
    def __init__(self, code: str, *, transient: bool) -> None:
        super().__init__(code)
        self.code = code
        self.transient = transient


class EmailProvider(Protocol):
    async def send(self, message: EmailMessage) -> str: ...


class ResendProvider:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        assert settings.resend_api_key is not None
        assert settings.email_from
        self._key = settings.resend_api_key
        self._from = settings.email_from
        self._reply_to = settings.email_reply_to
        self._base = settings.resend_api_base_url.rstrip("/")
        self._http = http

    async def send(self, message: EmailMessage) -> str:
        body: dict[str, object] = {
            "from": self._from,
            "to": [message.to],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
        }
        if self._reply_to:
            body["reply_to"] = self._reply_to
        try:
            response = await self._http.post(
                f"{self._base}/emails",
                json=body,
                headers={
                    "Authorization": f"Bearer {self._key.get_secret_value()}",
                    "Idempotency-Key": message.idempotency_key,
                },
                timeout=10.0,
            )
        except httpx.TimeoutException as exc:
            raise EmailSendError("timeout", transient=True) from exc
        except httpx.HTTPError as exc:
            raise EmailSendError(f"network_{type(exc).__name__}", transient=True) from exc
        if response.status_code == 429 or response.status_code >= 500:
            raise EmailSendError(f"provider_{response.status_code}", transient=True)
        if response.status_code >= 400:
            try:
                name = str(response.json().get("name", ""))[:60]
            except ValueError:
                name = ""
            raise EmailSendError(
                f"rejected_{response.status_code}" + (f"_{name}" if name else ""), transient=False
            )
        try:
            message_id = str(response.json()["id"])
        except (ValueError, KeyError, TypeError) as exc:
            raise EmailSendError("unexpected_response", transient=True) from exc
        return message_id


def email_configured(settings: Settings | None) -> bool:
    return bool(settings and settings.resend_api_key and settings.email_from)


def provider_for(settings: Settings, http: httpx.AsyncClient) -> EmailProvider | None:
    return ResendProvider(settings, http) if email_configured(settings) else None
