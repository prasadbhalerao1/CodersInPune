# ruff: noqa: E501  (GraphQL query strings read best unwrapped)
"""Linear GraphQL client (read scope only).

Queries select metadata fields explicitly; issue descriptions and comments are never
requested. Errors: 401/403 or an authentication GraphQL error -> LinearError(401)
(access revoked); network errors, 429 and 5xx -> transient (status 0 or the HTTP status).
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from relay.config import Settings


class LinearError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status

    @property
    def transient(self) -> bool:
        return self.status == 0 or self.status == 429 or self.status >= 500


@dataclass(frozen=True, slots=True)
class Organization:
    id: str
    name: str
    url_key: str | None


def _when(value: object) -> datetime | None:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None


TEAMS = "query($after: String) { teams(first: 100, after: $after) { nodes { id key name } pageInfo { hasNextPage endCursor } } }"
PROJECTS = (
    "query($after: String) { projects(first: 100, after: $after) { nodes { id name state url "
    "lead { id } teams { nodes { id } } } pageInfo { hasNextPage endCursor } } }"
)
USERS = (
    "query($after: String) { users(first: 100, after: $after) { nodes { id name displayName email active } "
    "pageInfo { hasNextPage endCursor } } }"
)
ISSUES = (
    "query($after: String, $since: DateTimeOrDuration) { issues(first: 100, after: $after, "
    "filter: { updatedAt: { gt: $since } }) { nodes { id identifier title priority url createdAt updatedAt "
    "completedAt canceledAt state { type name } assignee { id } creator { id } team { id } project { id } "
    "parent { identifier } labels { nodes { name } } } pageInfo { hasNextPage endCursor } } }"
)


class LinearClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._s = settings
        self._http = http

    @property
    def settings(self) -> Settings:
        return self._s

    @property
    def configured(self) -> bool:
        s = self._s
        return bool(s.linear_client_id and s.linear_client_secret and s.integration_encryption_key)

    @property
    def redirect_uri(self) -> str:
        return f"{self._s.frontend_base_url.rstrip('/')}/integrations/linear/callback"

    def authorize_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self._s.linear_client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": "read",
                "state": state,
                "prompt": "consent",
            }
        )
        return f"{self._s.linear_oauth_url}?{query}"

    async def exchange_code(self, code: str) -> str:
        assert self._s.linear_client_secret is not None
        try:
            response = await self._http.post(
                self._s.linear_token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self._s.linear_client_id,
                    "client_secret": self._s.linear_client_secret.get_secret_value(),
                },
            )
        except httpx.HTTPError as exc:
            raise LinearError(0, "Linear unreachable") from exc
        token = response.json().get("access_token") if response.status_code == 200 else None
        if not isinstance(token, str):
            raise LinearError(401, "Linear rejected the authorization code")
        return token

    async def _query(self, token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        try:
            response = await self._http.post(
                self._s.linear_api_url,
                json={"query": query, "variables": variables},
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx.HTTPError as exc:
            raise LinearError(0, f"Linear unreachable: {type(exc).__name__}") from exc
        if response.status_code in (401, 403):
            raise LinearError(401, "Linear access was revoked")
        if response.status_code >= 400:
            raise LinearError(response.status_code, f"Linear returned {response.status_code}")
        body = response.json()
        errors = body.get("errors") or []
        if errors:
            code = str((errors[0].get("extensions") or {}).get("code", ""))
            if "AUTHENTICATION" in code.upper() or "FORBIDDEN" in code.upper():
                raise LinearError(401, "Linear access was revoked")
            raise LinearError(422, "Linear query failed")
        return dict(body["data"])

    async def _nodes(
        self, token: str, query: str, key: str, **variables: Any
    ) -> AsyncIterator[dict[str, Any]]:
        after: str | None = None
        while True:
            data = (await self._query(token, query, {**variables, "after": after}))[key]
            for node in data["nodes"]:
                yield node
            page = data["pageInfo"]
            if not page["hasNextPage"]:
                return
            after = page["endCursor"]

    async def organization(self, token: str) -> Organization:
        data = await self._query(token, "query { organization { id name urlKey } }", {})
        org = data["organization"]
        return Organization(str(org["id"]), str(org["name"]), org.get("urlKey"))

    async def teams(self, token: str) -> list[dict[str, Any]]:
        return [t async for t in self._nodes(token, TEAMS, "teams")]

    async def projects(self, token: str) -> list[dict[str, Any]]:
        return [p async for p in self._nodes(token, PROJECTS, "projects")]

    async def users(self, token: str) -> list[dict[str, Any]]:
        return [u async for u in self._nodes(token, USERS, "users")]

    async def issues(self, token: str, since: datetime, limit: int = 2000) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        async for issue in self._nodes(token, ISSUES, "issues", since=since.isoformat()):
            items.append(issue)
            if len(items) >= limit:
                break
        return items


parse_when = _when
