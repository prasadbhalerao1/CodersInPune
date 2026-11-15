"""Startup configuration validation: misconfiguration fails fast with a clear message."""

from typing import Any

import pytest
from pydantic import ValidationError

from relay.config import Settings

BASE = {
    "database_url": "postgresql+psycopg://relay_app:x@db:5432/relay",
    "workos_client_id": "client_TEST",
}
PROD = {
    **BASE,
    "environment": "production",
    "frontend_base_url": "https://relay.example.com",
    "workos_api_key": "sk_live_x",
}


def make(**values: Any) -> Settings:
    return Settings(_env_file=None, **values)  # ignore backend/.env


def test_local_defaults_are_valid() -> None:
    assert make(**BASE).environment == "local"


def test_valid_production_configuration() -> None:
    assert make(**PROD).environment == "production"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"frontend_base_url": "http://relay.example.com"}, "https://"),
        ({"workos_api_key": None}, "RELAY_WORKOS_API_KEY"),
        (
            {"linear_client_id": "id", "linear_client_secret": "secret"},
            "RELAY_INTEGRATION_ENCRYPTION_KEY",
        ),
        ({"notion_client_id": "id"}, "Notion: set both"),
        ({"resend_api_key": "re_x"}, "RELAY_EMAIL_FROM"),
        ({"github_app_id": "1"}, "GitHub: set"),
    ],
)
def test_production_misconfiguration_is_rejected(
    overrides: dict[str, object], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        make(**{**PROD, **overrides})


def test_partial_integration_config_is_rejected_even_locally() -> None:
    with pytest.raises(ValidationError, match="Linear: set both"):
        make(**BASE, linear_client_secret="secret")


def test_blank_values_mean_unset() -> None:
    settings = make(**BASE, resend_api_key="", github_app_id="", github_private_key="")
    assert settings.resend_api_key is None
    assert settings.github_private_key is None
