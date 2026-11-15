"""OAuth token grants: how a provider's `expires_in` becomes an expiry (unit level)."""

from datetime import UTC, datetime, timedelta

import pytest

from relay.shared.oauth import TokenGrant


def _expires(body_value: object) -> datetime | None:
    grant = TokenGrant.from_response({"access_token": "t", "expires_in": body_value})
    assert grant is not None
    return grant.expires_at


@pytest.mark.parametrize("value", [3600, 3600.0, "3600"])
def test_numeric_expires_in_becomes_an_expiry(value: object) -> None:
    """Strings are accepted too: some providers send `"expires_in": "3600"`, which used to
    leave the token with no expiry, so it was never refreshed ahead of time."""
    expires = _expires(value)
    assert expires is not None
    assert timedelta(seconds=3590) < expires - datetime.now(UTC) <= timedelta(seconds=3600)


@pytest.mark.parametrize("value", [None, True, False, 0, -5, "soon", "", [], {}])
def test_unusable_expires_in_means_no_expiry(value: object) -> None:
    """A bool is an int in Python: `True` used to become a 1-second expiry."""
    assert _expires(value) is None


def test_a_response_without_an_access_token_is_not_a_grant() -> None:
    assert TokenGrant.from_response({"expires_in": 60}) is None
