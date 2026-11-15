"""Email provider boundary: one small interface, two implementations (SMTP and Resend).

`send()` returns the provider's message id only once the provider has accepted the
message. Failures are classified as transient (timeouts, 429, 5xx: retry with backoff)
or permanent (other 4xx: do not retry). Error codes are short and never contain the API
key or message content. The same idempotency key is sent on every retry, so even a
retry after an unseen success cannot produce a second email.

SMTP (e.g. Gmail or Microsoft 365 with an app password) has no idempotency key; the
message carries a Message-ID derived from it instead, so a retry reuses the same id and
most mail systems collapse duplicates. Relay records each delivery once it is accepted.
"""

import asyncio
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
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


class SmtpProvider:
    """Standard SMTP submission (STARTTLS on 587 by default, or implicit TLS on 465)."""

    def __init__(self, settings: Settings) -> None:
        assert settings.smtp_host
        assert settings.email_from
        self._s = settings

    def _deliver(self, mime: MimeMessage) -> None:
        s = self._s
        context = ssl.create_default_context()
        timeout = 15.0
        assert s.smtp_host is not None
        if s.smtp_security == "ssl":
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                s.smtp_host, s.smtp_port, timeout=timeout, context=context
            )
        else:
            client = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=timeout)
        with client:
            if s.smtp_security == "starttls":
                client.starttls(context=context)
            if s.smtp_username and s.smtp_password:
                client.login(s.smtp_username, s.smtp_password.get_secret_value())
            client.send_message(mime)

    async def send(self, message: EmailMessage) -> str:
        mime = MimeMessage()
        mime["From"] = self._s.email_from
        mime["To"] = message.to
        mime["Subject"] = message.subject
        if self._s.email_reply_to:
            mime["Reply-To"] = self._s.email_reply_to
        domain = (self._s.email_from or "").rsplit("@", 1)[-1].strip("> ") or "relay"
        # Deterministic: a retry of the same delivery carries the same Message-ID.
        message_id = f"<{message.idempotency_key}@{domain}>"
        mime["Message-ID"] = message_id
        mime.set_content(message.text)
        mime.add_alternative(message.html, subtype="html")
        try:
            await asyncio.to_thread(self._deliver, mime)
        except smtplib.SMTPAuthenticationError as exc:
            raise EmailSendError("smtp_auth_failed", transient=False) from exc
        except smtplib.SMTPRecipientsRefused as exc:
            raise EmailSendError("rejected_recipient", transient=False) from exc
        except smtplib.SMTPResponseException as exc:
            code = int(exc.smtp_code)
            raise EmailSendError(f"smtp_{code}", transient=code < 500) from exc
        except (TimeoutError, OSError, smtplib.SMTPException) as exc:
            raise EmailSendError(f"network_{type(exc).__name__}", transient=True) from exc
        return message_id


def email_configured(settings: Settings | None) -> bool:
    return bool(
        settings and settings.email_from and (settings.smtp_host or settings.resend_api_key)
    )


def provider_for(settings: Settings, http: httpx.AsyncClient) -> EmailProvider | None:
    """SMTP when configured, otherwise Resend; None means email is off."""
    if not email_configured(settings):
        return None
    if settings.smtp_host:
        return SmtpProvider(settings)
    return ResendProvider(settings, http)
