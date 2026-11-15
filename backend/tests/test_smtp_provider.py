"""SMTP email provider: STARTTLS + login, error classification, stable Message-ID."""

import smtplib
from typing import Any

import pytest

from relay.config import Settings
from relay.notifications import email_provider
from relay.notifications.email_provider import EmailMessage, EmailSendError, SmtpProvider

pytestmark = pytest.mark.anyio


def settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "postgresql+psycopg://relay_app:x@db:5432/relay",
        "workos_client_id": "client_TEST",
        "smtp_host": "smtp.example.test",
        "smtp_username": "relay@example.test",
        "smtp_password": "app-password",
        "email_from": "Relay <relay@example.test>",
    }
    return Settings(_env_file=None, **{**base, **overrides})


class FakeSMTP:
    sent: list[Any] = []
    fail: Exception | None = None
    calls: list[str] = []

    def __init__(self, host: str, port: int, timeout: float, **_: Any) -> None:
        FakeSMTP.calls.append(f"connect {host}:{port}")

    def __enter__(self) -> FakeSMTP:
        return self

    def __exit__(self, *_: object) -> None:
        FakeSMTP.calls.append("quit")

    def starttls(self, context: Any) -> None:
        FakeSMTP.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        FakeSMTP.calls.append(f"login {user}")
        if FakeSMTP.fail:
            raise FakeSMTP.fail

    def send_message(self, message: Any) -> None:
        FakeSMTP.sent.append(message)


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeSMTP.sent, FakeSMTP.calls, FakeSMTP.fail = [], [], None
    monkeypatch.setattr("smtplib.SMTP", FakeSMTP)


MESSAGE = EmailMessage(
    to="ada@example.test", subject="Hi", html="<p>Hi</p>", text="Hi", idempotency_key="relay-1-g1"
)


async def test_sends_over_starttls_with_login_and_stable_message_id() -> None:
    provider = SmtpProvider(settings())
    first = await provider.send(MESSAGE)
    second = await provider.send(MESSAGE)  # a retry reuses the same id
    assert first == second == "<relay-1-g1@example.test>"
    assert FakeSMTP.calls[:3] == [
        "connect smtp.example.test:587",
        "starttls",
        "login relay@example.test",
    ]
    [sent, _] = FakeSMTP.sent
    assert (sent["To"], sent["Subject"]) == ("ada@example.test", "Hi")
    assert sent.get_body(("plain",)).get_content().strip() == "Hi"
    assert "app-password" not in str(sent)


async def test_errors_are_classified_without_secrets() -> None:
    provider = SmtpProvider(settings())
    FakeSMTP.fail = smtplib.SMTPAuthenticationError(535, b"bad credentials")
    with pytest.raises(EmailSendError) as auth:
        await provider.send(MESSAGE)
    assert (auth.value.code, auth.value.transient) == ("smtp_auth_failed", False)

    FakeSMTP.fail = smtplib.SMTPResponseException(421, b"try later")
    with pytest.raises(EmailSendError) as busy:
        await provider.send(MESSAGE)
    assert (busy.value.code, busy.value.transient) == ("smtp_421", True)

    FakeSMTP.fail = OSError("unreachable")
    with pytest.raises(EmailSendError) as down:
        await provider.send(MESSAGE)
    assert down.value.transient


def test_smtp_takes_precedence_and_requires_a_sender() -> None:
    import httpx

    configured = settings(resend_api_key="re_x")
    assert isinstance(email_provider.provider_for(configured, httpx.AsyncClient()), SmtpProvider)
    with pytest.raises(ValueError, match="RELAY_EMAIL_FROM"):
        settings(email_from=None)
    with pytest.raises(ValueError, match="RELAY_SMTP_PASSWORD"):
        settings(smtp_password=None)
