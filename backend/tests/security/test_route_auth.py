"""Every API route requires a verified identity, except an explicit public allowlist.

Walks the app's route table, so a newly added endpoint without the Identity /
CurrentWorkspace dependency fails here instead of shipping unauthenticated.
"""

import re
import uuid
from collections.abc import AsyncIterator

import pytest

from tests.api import Api, make_api
from tests.fakes import FakeExternal

pytestmark = pytest.mark.anyio

# Public by design: health probes, and the GitHub webhook (HMAC-signed instead).
PUBLIC = {"/health/live", "/health/ready", "/integrations/github/webhook"}


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api(FakeExternal()) as a:
        yield a


async def test_every_route_rejects_anonymous_requests(api: Api) -> None:
    paths = {p: ops for p, ops in api.app.openapi()["paths"].items() if p not in PUBLIC}
    operations = [(m.upper(), p) for p, ops in paths.items() for m in ops]
    assert len(operations) > 100  # the walk really covers the API
    exposed: list[str] = []
    for method, template in operations:
        path = re.sub(r"\{[^}]+\}", str(uuid.uuid4()), template)
        response = await api.client.request(method, path, json={})
        if response.status_code != 401:
            exposed.append(f"{method} {template} -> {response.status_code}")
    assert exposed == []


async def test_a_forged_token_is_rejected(api: Api) -> None:
    response = await api.client.get(
        "/workspaces", headers={"Authorization": "Bearer eyJhbGciOiJub25lIn0.e30."}
    )
    assert response.status_code == 401
