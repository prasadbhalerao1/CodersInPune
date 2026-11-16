"""The judges' account list is validated before anything is created."""

import pytest

from relay.demo.seed import parse_accounts


def test_accounts_parse_into_roles() -> None:
    accounts = parse_accounts("owner:A@x.com, auditor:b@x.com")
    assert accounts == {"owner": "a@x.com", "auditor": "b@x.com"}


@pytest.mark.parametrize(
    "spec", ["", "admin:b@x.com", "wizard:a@x.com,owner:o@x.com", "owner:nope"]
)
def test_bad_account_lists_are_rejected(spec: str) -> None:
    with pytest.raises(ValueError):
        parse_accounts(spec)
