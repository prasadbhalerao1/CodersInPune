"""Shared API test harness: real app, real PostgreSQL as relay_app, simulated JWKS only."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

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


OWNER = "user_owner"


async def add_member(api: Api, tenant: uuid.UUID, sub: str, role: str) -> None:
    """Simulates an admin adding a member (no member-management API yet)."""
    async with unit_of_work(api.app.state.session_factory, tenant, sub) as session:
        user_id = (
            await session.execute(
                insert(UserAccount)
                .values(workos_user_id=sub)
                .on_conflict_do_update(
                    index_elements=["workos_user_id"], set_={"workos_user_id": sub}
                )
                .returning(UserAccount.id)
            )
        ).scalar_one()
        session.add(Membership(tenant_id=tenant, user_id=user_id, role=role, status="active"))


class Ws:
    def __init__(self, api: Api, workspace: uuid.UUID, sub: str = OWNER) -> None:
        self.api, self.id, self.sub = api, workspace, sub

    async def call(self, method: str, path: str, expected: int = 200, **kwargs: Any) -> Any:
        response = await self.api.client.request(
            method, f"/workspaces/{self.id}{path}", headers=self.api.as_user(self.sub), **kwargs
        )
        assert response.status_code == expected, response.text
        return response.json() if response.content else None

    async def person(self, name: str) -> str:
        return str((await self.call("POST", "/people", 201, json={"display_name": name}))["id"])

    async def responsibility(self, name: str, criticality: str = "standard") -> str:
        body = {"name": name, "criticality": criticality}
        return str((await self.call("POST", "/responsibilities", 201, json=body))["id"])
