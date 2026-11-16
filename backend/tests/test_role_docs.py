"""The public product guide states every role's purpose exactly as the registry does."""

from pathlib import Path

from relay.policy.permissions import ROLE_PERMISSIONS, ROLE_PURPOSE

GUIDE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "docs" / "page.tsx"


def test_every_role_has_a_purpose_and_the_guide_matches() -> None:
    assert set(ROLE_PURPOSE) == set(ROLE_PERMISSIONS)
    guide = " ".join(GUIDE.read_text(encoding="utf-8").split())
    for role, purpose in ROLE_PURPOSE.items():
        assert f'"{role}"' in guide, role
        assert purpose in guide, role
