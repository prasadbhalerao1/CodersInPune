"""Sample workspace: one-step synthetic organisation for new users and judges."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from tests.api import OWNER, Api, make_api
from tests.fakes import FakeExternal

pytestmark = pytest.mark.anyio


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(FakeExternal()) as a:
        yield a


def _headers(api: Api, sub: str, key: str) -> dict[str, str]:
    return {**api.as_user(sub), "Idempotency-Key": key}


async def test_sample_is_seeded_and_owned_by_the_caller(api: Api) -> None:
    created = await api.client.post("/workspaces/sample", headers=_headers(api, OWNER, "sample-1"))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "Northwind Labs (demo)"
    assert body["role"] == "owner"

    workspace = body["id"]
    listing = await api.client.get("/workspaces", headers=api.as_user(OWNER))
    assert workspace in [w["id"] for w in listing.json()]
    # Seeded content is visible through the normal, permission-checked APIs.
    responsibilities = await api.client.get(
        f"/workspaces/{workspace}/responsibilities", headers=api.as_user(OWNER)
    )
    assert responsibilities.status_code == 200
    assert len(responsibilities.json()) > 0


async def test_replaying_the_key_returns_the_same_sample_without_reseeding(api: Api) -> None:
    first = await api.client.post("/workspaces/sample", headers=_headers(api, OWNER, "sample-2"))
    again = await api.client.post("/workspaces/sample", headers=_headers(api, OWNER, "sample-2"))
    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    listing = await api.client.get("/workspaces", headers=api.as_user(OWNER))
    assert [w["name"] for w in listing.json()].count("Northwind Labs (demo)") == 1


async def test_another_user_cannot_see_someone_elses_sample(api: Api) -> None:
    created = await api.client.post("/workspaces/sample", headers=_headers(api, OWNER, "sample-3"))
    workspace = created.json()["id"]
    await api.create_workspace("user_other", "Other's own")  # provisions user_other
    other = await api.client.get(f"/workspaces/{workspace}", headers=api.as_user("user_other"))
    assert other.status_code == 404
    assert other.json()["code"] == "workspace_not_found"


async def test_sample_requires_authentication_and_an_idempotency_key(api: Api) -> None:
    anonymous = await api.client.post("/workspaces/sample", headers={"Idempotency-Key": "k-anon1"})
    assert anonymous.status_code == 401
    no_key = await api.client.post("/workspaces/sample", headers=api.as_user(OWNER))
    assert no_key.status_code == 422


async def test_samples_are_rate_limited_per_user(api: Api) -> None:
    for i in range(3):
        ok = await api.client.post(
            "/workspaces/sample", headers=_headers(api, OWNER, f"limit-{i}-key")
        )
        assert ok.status_code == 201
    blocked = await api.client.post(
        "/workspaces/sample", headers=_headers(api, OWNER, "limit-4-key")
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "rate_limited"


async def test_samples_can_be_turned_off() -> None:
    async with make_api(FakeExternal(), sample_workspaces=False) as api:
        response = await api.client.post(
            "/workspaces/sample", headers=_headers(api, OWNER, "sample-off")
        )
        assert response.status_code == 404
        assert response.json()["code"] == "not_found"


async def test_sample_powers_the_round_three_features(api: Api) -> None:
    created = await api.client.post("/workspaces/sample", headers=_headers(api, OWNER, "sample-r3"))
    ws = f"/workspaces/{created.json()['id']}"

    async def get(path: str) -> Any:
        response = await api.client.get(ws + path, headers=api.as_user(OWNER))
        assert response.status_code == 200, response.text
        return response.json()

    # The owner is the recipient of an approved handover: My Work leads with it.
    handovers = (await get("/my-work"))["handovers"]
    assert [(h["case_title"], h["status"]) for h in handovers] == [
        ("Arjun Rao is leaving Platform", "approved")
    ]
    resps = {r["name"]: r["id"] for r in await get("/responsibilities")}
    timeline = await get(f"/responsibilities/{resps['Production deployments']}/timeline")
    categories = {e["category"] for e in timeline["events"]}
    assert {"incident", "bug_fix", "ownership_change", "decision"} <= categories
    assert any(e["linked_events"] for e in timeline["events"])

    people = {p["display_name"]: p["id"] for p in await get("/people")}
    alone = await get(f"/simulation?person_id={people['Arjun Rao']}")
    assert resps["Production deployments"] in alone["uncovered_responsibilities"]
    assert {w["source"] for w in alone["open_work_without_cover"]} >= {"GitHub", "Relay task"}
    options = await get(f"/simulation/candidates?person_id={people['Arjun Rao']}&days=14")
    top = options["candidates"][0]
    assert top["person"]["name"] == "Dev Patel"
    assert "Planned recipient of Production deployments in an open handover" in top["signals"]
    covered = await get(
        f"/simulation?person_id={people['Arjun Rao']}&backup_id={people['Dev Patel']}"
    )
    assert covered["uncovered_responsibilities"] == []
    # Work in a responsibility the backup now covers is no longer stalled.
    assert {w["source"] for w in covered["open_work_without_cover"]} == {"Relay task"}
    assert covered["readiness_score"] > alone["readiness_score"]
