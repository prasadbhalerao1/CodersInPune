"""Shared API test harness: real app, real PostgreSQL as relay_app, simulated JWKS only."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI
from sqlalchemy import select, update

from relay.app import create_app
from relay.identity.models import Membership, UserAccount
from relay.shared.db import unit_of_work
from tests.conftest import make_settings
from tests.tokens import JwksServer, SigningKey, bearer, make_token


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
