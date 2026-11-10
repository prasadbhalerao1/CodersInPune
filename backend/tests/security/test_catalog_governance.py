"""Restricted responsibilities (service and database), stewardship, corrections, assets
and the deterministic risk additions."""

from collections.abc import AsyncIterator
from datetime import timedelta

import psycopg
import pytest

from tests.api import OWNER, Api, Ws, add_member, make_api
from tests.db import APP_URL, OWNER_URL, libpq_url
from tests.security.test_cases import iso, owned

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


@pytest.fixture
async def ws(api: Api) -> Ws:
    return Ws(api, await api.create_workspace(OWNER, "Acme"))


def visible_to(ws: Ws, sub: str) -> int:
    """Count responsibilities as the app role sees them for a principal: the row policy."""
    with psycopg.connect(libpq_url(APP_URL)) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, true)", (str(ws.id),))
        conn.execute("SELECT set_config('app.principal', %s, true)", (sub,))
        row = conn.execute("SELECT count(*) FROM catalog.responsibility").fetchone()
        assert row is not None
        return int(row[0])


def set_member_email(ws: Ws, email: str) -> None:
    with psycopg.connect(libpq_url(OWNER_URL), autocommit=True) as conn:
        conn.execute("SELECT set_config('app.tenant_id', %s, false)", (str(ws.id),))
        conn.execute(
            "UPDATE identity.membership SET email = %s WHERE tenant_id = %s AND role = 'member'",
            (email, ws.id),
        )


async def test_restricted_responsibilities_fail_closed(api: Api, ws: Ws) -> None:
    await add_member(api, ws.id, "user_member", "member")
    member = Ws(api, ws.id, "user_member")
    await ws.responsibility("Open")
    secret = await ws.call(
        "POST", "/responsibilities", 201, json={"name": "Payroll keys", "restricted": True}
    )
    rid = secret["id"]

    assert [r["name"] for r in await member.call("GET", "/responsibilities")] == ["Open"]
    await member.call("GET", f"/responsibilities/{rid}", 404)
    hits = (await member.call("GET", "/search", params={"q": "Payroll"}))["hits"]
    assert hits == []
    # The database itself hides it, whatever query the application makes.
    assert visible_to(ws, "user_member") == 1
    assert visible_to(ws, OWNER) == 2

    member_id = next(
        m["user_id"] for m in await ws.call("GET", "/members") if m["role"] == "member"
    )
    await ws.call("POST", f"/responsibilities/{rid}/access", 201, json={"user_id": member_id})
    assert (await member.call("GET", f"/responsibilities/{rid}"))["restricted"] is True
    await ws.call("DELETE", f"/responsibilities/{rid}/access/{member_id}")
    await member.call("GET", f"/responsibilities/{rid}", 404)

    # A current holder sees what they hold.
    holder = await ws.call(
        "POST", "/people", 201, json={"display_name": "Mem", "email": "mem@acme.test"}
    )
    set_member_email(ws, "mem@acme.test")
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "person_id": holder["id"]},
    )
    assert (await member.call("GET", f"/responsibilities/{rid}"))["name"] == "Payroll keys"


async def test_stewardship_correction_assets_and_risks(ws: Ws) -> None:
    kinds = await ws.call(
        "POST", "/responsibilities/types", 201, json={"name": "Finance", "review_cadence_days": 30}
    )
    team = await ws.call("POST", "/teams", 201, json={"name": "Platform"})
    person = await ws.person("Asha")
    created = await ws.call(
        "POST",
        "/responsibilities",
        201,
        json={
            "name": "Billing",
            "criticality": "critical",
            "type_id": kinds[0]["id"],
            "escalation_path": "Page platform on-call, then the CFO",
            "procedures": ["Month-end close"],
            "access_prerequisites": ["Stripe admin"],
            "needs_verification": True,
        },
    )
    rid = created["id"]
    await ws.call("PUT", f"/teams/{team['id']}/members/{person}", 204)
    assert created["type_name"] == "Finance"
    assert created["procedures"] == ["Month-end close"]
    assert created["effective_review_days"] == 30
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "primary", "team_id": team["id"]},
    )
    await ws.call(
        "POST",
        f"/responsibilities/{rid}/assignments",
        201,
        json={"role": "backup", "person_id": person},
    )
    flagged = await ws.call("GET", "/responsibilities", params={"needs_verification": "true"})
    assert [r["id"] for r in flagged] == [rid]
    await ws.call("POST", f"/responsibilities/{rid}/review", 204, params={"verified": "true"})
    assert (await ws.call("GET", f"/responsibilities/{rid}"))["needs_verification"] is False

    # Risk additions: backup = primary, team-owned critical without a contact, lone asset.
    vendor = await ws.call(
        "POST",
        "/assets",
        201,
        json={
            "name": "Stripe",
            "asset_type": "vendor",
            "criticality": "high",
            "tags": ["payments"],
            "metadata": {"contract_renewal": "2027-01-01"},
        },
    )
    risks = {r["rule"]: r for r in await ws.call("GET", "/risks")}
    assert {"backup_is_primary", "team_without_contact", "unstewarded_asset"} <= risks.keys()
    lone = risks["unstewarded_asset"]
    assert lone["asset_name"] == "Stripe"
    assert lone["severity"] == "high"
    still = await ws.call(
        "POST", "/risks/decision", 409, json={"key": lone["key"], "action": "resolve"}
    )
    assert still["code"] == "condition_present"
    await ws.call("POST", "/risks/decision", 422, json={"key": lone["key"], "action": "dismiss"})
    await ws.call("POST", "/risks/decision", json={"key": lone["key"], "action": "remediate"})
    await ws.call("POST", f"/responsibilities/{rid}/assets", 204, json={"asset_id": vendor["id"]})
    rules = {r["rule"] for r in await ws.call("GET", "/risks")}
    assert "unstewarded_asset" not in rules

    await ws.call(
        "POST",
        "/assets",
        422,
        json={"name": "X", "asset_type": "vendor", "metadata": {"runbook_url": "x"}},
    )
    tagged = await ws.call("GET", "/assets", params={"tag": "payments", "stewarded": "true"})
    assert [a["name"] for a in tagged] == ["Stripe"]
    dep = await ws.call(
        "POST",
        f"/responsibilities/{rid}/dependencies",
        201,
        json={"depends_on_asset_id": vendor["id"], "relationship": "depends_on"},
    )
    assert dep["dependencies"][0]["target_name"] == "Stripe"

    # Backdated correction: allowed with a reason, kept in history; overlaps still refused.
    other = await owned(ws, "Ledger", person)
    detail = await ws.call("GET", f"/responsibilities/{other}")
    assignment = detail["assignments"][0]["id"]
    await ws.call(
        "POST",
        f"/responsibilities/{other}/assignments/{assignment}/correct",
        422,
        json={"valid_from": iso(timedelta(days=-30))},
    )
    await ws.call(
        "POST",
        f"/responsibilities/{other}/assignments/{assignment}/correct",
        json={"valid_from": iso(timedelta(days=-30)), "reason": "Started last month"},
    )
    history = await ws.call("GET", f"/responsibilities/{other}/history")
    assert history[0]["change_type"] == "corrected"
    assert history[0]["reason"] == "Started last month"
