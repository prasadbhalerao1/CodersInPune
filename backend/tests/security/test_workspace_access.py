"""Authentication, membership-based tenant resolution and workspace creation.

API tests run the real FastAPI app against real PostgreSQL as `relay_app`. Tokens are
real RS256 JWTs; only the WorkOS JWKS response is simulated.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import anyio
import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError

from relay.app import create_app
from relay.identity import models as identity_models
from relay.identity.models import Membership, UserAccount
from relay.platform.workspaces import create_workspace
from relay.shared.db import unit_of_work
from relay.shared.db.session import establish_tenant_context
from tests.conftest import make_settings
from tests.db import count_rows
from tests.tokens import JwksServer, SigningKey, bearer, make_token

pytestmark = pytest.mark.anyio


@dataclass
class Api:
    app: FastAPI
    client: httpx.AsyncClient
    key: SigningKey

    def as_user(self, sub: str) -> dict[str, str]:
        return bearer(make_token(self.key, sub))

    async def create_workspace(self, sub: str, name: str, key: str | None = None) -> uuid.UUID:
        response = await self.client.post(
            "/workspaces",
            json={"name": name},
            headers={**self.as_user(sub), "Idempotency-Key": key or uuid.uuid4().hex},
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(response.json()["id"])

    async def set_membership_status(self, tenant: uuid.UUID, sub: str, status: str) -> None:
        """Simulates an admin action, executed through the app role under RLS.

        Runs with the member's principal only so their user id is resolvable; there is no
        membership-management API yet.
        """
        user_id = select(UserAccount.id).where(UserAccount.workos_user_id == sub).scalar_subquery()
        async with unit_of_work(self.app.state.session_factory, tenant, sub) as session:
            result = await session.execute(
                update(Membership)
                .where(Membership.tenant_id == tenant, Membership.user_id == user_id)
                .values(status=status)
            )
            assert result.rowcount == 1  # type: ignore[attr-defined]


@asynccontextmanager
async def make_api(**settings: object) -> AsyncIterator[Api]:
    key = SigningKey(kid="key-1")
    app = create_app(make_settings(**settings), JwksServer(keys=[key]).transport)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield Api(app, client, key)


@pytest.fixture
async def api() -> AsyncIterator[Api]:
    async with make_api() as a:
        yield a


# 1-2: authentication


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", "/workspaces"), ("POST", "/workspaces"), ("GET", f"/workspaces/{uuid.uuid4()}")],
)
async def test_protected_endpoints_require_authentication(api: Api, method: str, path: str) -> None:
    response = await api.client.request(method, path, json={"name": "x"})
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"
    assert response.headers["www-authenticate"].startswith("Bearer")


@pytest.mark.parametrize(
    "token_kind", ["expired", "foreign_key", "wrong_issuer", "garbage", "not_bearer"]
)
async def test_invalid_tokens_are_rejected(api: Api, token_kind: str) -> None:
    headers = {
        "expired": bearer(make_token(api.key, issued_offset=-3600)),
        "foreign_key": bearer(make_token(SigningKey(kid="key-1"))),
        "wrong_issuer": bearer(
            make_token(api.key, issuer="https://evil.example/user_management/x")
        ),
        "garbage": bearer("abc.def.ghi"),
        "not_bearer": {"Authorization": f"Basic {make_token(api.key)}"},
    }[token_kind]
    response = await api.client.get("/workspaces", headers=headers)
    assert response.status_code == 401


async def test_identity_headers_are_not_trusted(api: Api) -> None:
    owner = "user_owner"
    workspace = await api.create_workspace(owner, "Owned")
    response = await api.client.get(
        f"/workspaces/{workspace}",
        headers={"X-User-Id": owner, "X-WorkOS-User-Id": owner, "X-Tenant-Id": str(workspace)},
    )
    assert response.status_code == 401


# 3-7: membership-based tenant resolution


async def test_valid_identity_without_relay_user_cannot_access_workspace(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Owned")
    response = await api.client.get(f"/workspaces/{workspace}", headers=api.as_user("user_new"))
    assert response.status_code == 403
    assert response.json()["code"] == "user_not_provisioned"
    listing = await api.client.get("/workspaces", headers=api.as_user("user_new"))
    assert listing.json() == []


async def test_relay_user_without_membership_gets_not_found(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Owned")
    await api.create_workspace("user_other", "Other's own")  # provisions user_other
    for target in (workspace, uuid.uuid4()):  # existing and non-existent look identical
        response = await api.client.get(f"/workspaces/{target}", headers=api.as_user("user_other"))
        assert response.status_code == 404
        assert response.json()["code"] == "workspace_not_found"


async def test_active_membership_grants_access_to_that_workspace(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Acme")
    response = await api.client.get(f"/workspaces/{workspace}", headers=api.as_user("user_owner"))
    assert response.status_code == 200
    assert response.json() == {"id": str(workspace), "name": "Acme", "role": "owner"}


async def test_inactive_membership_immediately_blocks_access(api: Api) -> None:
    workspace = await api.create_workspace("user_owner", "Acme")
    headers = api.as_user("user_owner")
    for status, expected in [("suspended", 403), ("active", 200), ("removed", 403)]:
        await api.set_membership_status(workspace, "user_owner", status)
        response = await api.client.get(f"/workspaces/{workspace}", headers=headers)
        assert response.status_code == expected, status
        if expected == 403:
            assert response.json()["code"] == "membership_inactive"
    listing = await api.client.get("/workspaces", headers=headers)
    assert listing.json() == []


async def test_user_in_two_workspaces_accesses_each_only_while_active(api: Api) -> None:
    first = await api.create_workspace("user_multi", "First")
    second = await api.create_workspace("user_multi", "Second")
    headers = api.as_user("user_multi")
    listing = await api.client.get("/workspaces", headers=headers)
    assert [w["name"] for w in listing.json()] == ["First", "Second"]

    await api.set_membership_status(first, "user_multi", "suspended")
    assert (await api.client.get(f"/workspaces/{first}", headers=headers)).status_code == 403
    second_response = await api.client.get(f"/workspaces/{second}", headers=headers)
    assert second_response.json()["name"] == "Second"
    listing = await api.client.get("/workspaces", headers=headers)
    assert [w["name"] for w in listing.json()] == ["Second"]


async def test_changing_path_params_or_headers_cannot_reach_another_workspace(api: Api) -> None:
    mine = await api.create_workspace("user_a", "Mine")
    theirs = await api.create_workspace("user_b", "Theirs")
    headers = {**api.as_user("user_a"), "X-Tenant-Id": str(theirs), "X-Workspace-Id": str(theirs)}

    response = await api.client.get(f"/workspaces/{theirs}", headers=headers)
    assert response.status_code == 404
    response = await api.client.get(
        f"/workspaces/{mine}", headers=headers, params={"tenant_id": str(theirs)}
    )
    assert response.json()["name"] == "Mine"


# 8-9: workspace creation


async def test_workspace_creation_writes_workspace_user_and_owner_membership(api: Api) -> None:
    workspace = await api.create_workspace("user_founder", "Founder Co")
    assert count_rows("platform.tenant", "id = %s", (workspace,)) == 1
    assert count_rows("identity.user_account", "workos_user_id = 'user_founder'") == 1
    assert (
        count_rows(
            "identity.membership",
            "tenant_id = %s AND role = 'owner' AND status = 'active'",
            (workspace,),
        )
        == 1
    )


async def test_workspace_creation_is_atomic(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    # Make the final insert (membership) violate its CHECK constraint.
    monkeypatch.setattr(identity_models, "OWNER_ROLE", "superuser")
    with pytest.raises(IntegrityError):
        await create_workspace(
            api.app.state.session_factory, "user_atomic", "Broken", "key-atomic-1"
        )
    for table in (
        "platform.tenant",
        "identity.user_account",
        "identity.membership",
        "identity.workspace_creation_request",
    ):
        assert count_rows(table) == 0, table


async def test_workspace_creation_rejects_client_supplied_creator(api: Api) -> None:
    response = await api.client.post(
        "/workspaces",
        json={"name": "Spoof", "user_id": str(uuid.uuid4()), "workos_user_id": "user_victim"},
        headers={**api.as_user("user_real"), "Idempotency-Key": "spoof-attempt-1"},
    )
    assert response.status_code == 201
    assert count_rows("identity.user_account", "workos_user_id = 'user_victim'") == 0
    assert count_rows("identity.user_account", "workos_user_id = 'user_real'") == 1


async def test_retry_with_same_idempotency_key_returns_original_workspace(api: Api) -> None:
    headers = {**api.as_user("user_retry"), "Idempotency-Key": "retry-key-0001"}
    first = await api.client.post("/workspaces", json={"name": "Once"}, headers=headers)
    second = await api.client.post("/workspaces", json={"name": "Once"}, headers=headers)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json() == second.json()
    assert count_rows("platform.tenant") == 1


async def test_concurrent_creation_with_same_key_creates_exactly_one_workspace() -> None:
    async with make_api(db_pool_size=10, db_max_overflow=0) as api:
        headers = {**api.as_user("user_race"), "Idempotency-Key": "race-key-0001"}
        results: list[httpx.Response] = []

        async def submit() -> None:
            results.append(
                await api.client.post("/workspaces", json={"name": "Race"}, headers=headers)
            )

        async with anyio.create_task_group() as tg:
            for _ in range(8):
                tg.start_soon(submit)

        assert sorted(r.status_code for r in results) == [200] * 7 + [201]
        assert len({r.json()["id"] for r in results}) == 1
        assert count_rows("platform.tenant") == 1
        assert count_rows("identity.membership") == 1
        assert count_rows("identity.user_account") == 1
        assert count_rows("identity.workspace_creation_request") == 1


async def test_concurrent_first_requests_resolve_one_user() -> None:
    async with make_api(db_pool_size=10, db_max_overflow=0) as api:
        names = [f"Parallel {i}" for i in range(8)]

        async with anyio.create_task_group() as tg:
            for name in names:
                tg.start_soon(api.create_workspace, "user_parallel", name)

        assert count_rows("identity.user_account") == 1
        assert count_rows("platform.tenant") == 8
        assert count_rows("identity.membership", "role = 'owner' AND status = 'active'") == 8


# 10: tenant context from membership, no leaks


async def test_request_context_does_not_leak_through_pooled_connection() -> None:
    async with make_api(db_pool_size=1, db_max_overflow=0) as api:
        a_ws = await api.create_workspace("user_a", "A")
        b_ws = await api.create_workspace("user_b", "B")
        sequence = [
            ("user_a", a_ws, 200),
            ("user_b", a_ws, 404),
            ("user_b", b_ws, 200),
            ("user_a", b_ws, 404),
            ("user_a", a_ws, 200),
        ]
        for sub, workspace, expected in sequence:
            response = await api.client.get(f"/workspaces/{workspace}", headers=api.as_user(sub))
            assert response.status_code == expected, (sub, workspace)

        # The single pooled connection carries no tenant or principal afterwards.
        async with unit_of_work(api.app.state.session_factory, None) as session:
            settings = (
                await session.execute(
                    text(
                        "SELECT current_setting('app.tenant_id', true), "
                        "current_setting('app.principal', true), "
                        "(SELECT count(*) FROM platform.tenant), "
                        "(SELECT count(*) FROM identity.membership), "
                        "(SELECT count(*) FROM identity.user_account)"
                    )
                )
            ).one()
        assert tuple(settings) == ("", "", 0, 0, 0)


async def test_principal_sees_only_its_own_identity_rows(api: Api) -> None:
    await api.create_workspace("user_a", "A")
    await api.create_workspace("user_b", "B")
    async with unit_of_work(api.app.state.session_factory, None, "user_a") as session:
        row = (
            await session.execute(
                text(
                    "SELECT (SELECT count(*) FROM identity.user_account), "
                    "(SELECT count(*) FROM identity.membership), "
                    "(SELECT count(*) FROM platform.tenant), "
                    "(SELECT count(*) FROM identity.workspace_creation_request)"
                )
            )
        ).one()
    assert tuple(row) == (1, 1, 1, 1)


async def test_tenant_context_cannot_be_rebound_within_a_session(api: Api) -> None:
    first = await api.create_workspace("user_a", "A")
    async with unit_of_work(api.app.state.session_factory, first, "user_a") as session:
        await establish_tenant_context(session, first)  # same tenant: no-op
        with pytest.raises(RuntimeError):
            await establish_tenant_context(session, uuid.uuid4())
