"""The public product guide states every role's purpose exactly as the registry does."""

import re
from pathlib import Path

from relay.policy.permissions import ROLE_PERMISSIONS, ROLE_PURPOSE

GUIDE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "docs" / "page.tsx"


def test_every_role_has_a_purpose_and_the_guide_matches() -> None:
    assert set(ROLE_PURPOSE) == set(ROLE_PERMISSIONS)
    guide = " ".join(GUIDE.read_text(encoding="utf-8").split())
    for role, purpose in ROLE_PURPOSE.items():
        assert f'"{role}"' in guide, role
        assert purpose in guide, role


def test_the_guide_permission_table_matches_the_registry() -> None:
    guide = " ".join(GUIDE.read_text(encoding="utf-8").split())
    rows = re.findall(r'\[ ?"[^"]+", "([a-z_]+\.[a-z_]+)", "([a-z_* ]+)",? ?\]', guide)
    assert len(rows) >= 15
    for permission, holders in rows:
        held = {r for r in holders.split() if not r.endswith("*")}
        expected = {r for r, perms in ROLE_PERMISSIONS.items() if permission in perms}
        assert held == expected, permission
