"""GitHub App client: least-privilege, no persisted tokens.

App permissions required (GitHub docs, checked 2026-11-08):
- Repository > Metadata: read   — list repositories, list collaborators
- Repository > Contents: read   — read CODEOWNERS and catalog-info.yaml only
"Request user authorization (OAuth) during installation" must be enabled so the install
redirect carries a `code`; it is exchanged once to verify the installation belongs to the
user (`GET /user/installations`), because `installation_id` on the redirect can be spoofed.
"""

import base64
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import jwt

from relay.config import Settings
from relay.integrations.github.parsing import MAX_FILE_BYTES

_API_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


class GitHubError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


class GitHubNotConfiguredError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Repository:
    github_id: int
    full_name: str
    html_url: str
    default_branch: str | None
    private: bool
    archived: bool


class GitHubClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._s = settings
        self._http = http

    @property
    def configured(self) -> bool:
        s = self._s
        return all(
            [
                s.github_app_id,
                s.github_app_slug,
                s.github_client_id,
                s.github_client_secret,
                s.github_private_key,
            ]
        )

    def install_url(self, state: str) -> str:
        if not self.configured:
            raise GitHubNotConfiguredError
        base = f"{self._s.github_web_base_url}/apps/{self._s.github_app_slug}"
        return f"{base}/installations/new?state={state}"

    def _app_jwt(self) -> str:
        if not self.configured or self._s.github_private_key is None:
            raise GitHubNotConfiguredError
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 540, "iss": self._s.github_app_id}
        return jwt.encode(payload, self._s.github_private_key.get_secret_value(), algorithm="RS256")

    async def _call(self, method: str, url: str, token: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._http.request(
                method, url, headers={**_API_HEADERS, "Authorization": f"Bearer {token}"}, **kwargs
            )
        except httpx.HTTPError as exc:
            raise GitHubError(0, f"GitHub unreachable: {type(exc).__name__}") from exc
        if response.status_code >= 400 and response.status_code != 404:
            raise GitHubError(response.status_code, f"GitHub returned {response.status_code}")
        return response

    async def _paginate(self, path: str, token: str, key: str | None = None) -> AsyncIterator[Any]:
        page = 1
        while True:
            response = await self._call(
                "GET",
                f"{self._s.github_api_base_url}{path}",
                token,
                params={"per_page": 100, "page": page},
            )
            if response.status_code == 404:
                raise GitHubError(404, "not found")
            data = response.json()
            items = data[key] if key else data
            for item in items:
                yield item
            if len(items) < 100:
                return
            page += 1

    # ---- install verification (user OAuth token, used once and discarded)

    async def verify_user_installation(self, code: str, installation_id: int) -> dict[str, Any]:
        if not self.configured or self._s.github_client_secret is None:
            raise GitHubNotConfiguredError
        try:
            response = await self._http.post(
                f"{self._s.github_web_base_url}/login/oauth/access_token",
                data={
                    "client_id": self._s.github_client_id,
                    "client_secret": self._s.github_client_secret.get_secret_value(),
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            token = response.json().get("access_token")
        except (httpx.HTTPError, ValueError) as exc:
            raise GitHubError(0, "GitHub authorization failed") from exc
        if not isinstance(token, str):
            raise GitHubError(401, "GitHub authorization code was rejected")
        async for installation in self._paginate("/user/installations", token, key="installations"):
            if installation.get("id") == installation_id:
                return dict(installation)
        raise GitHubError(403, "That installation is not accessible to your GitHub account")

    # ---- installation access (minted per sync)

    async def installation_token(self, installation_id: int) -> str:
        response = await self._call(
            "POST",
            f"{self._s.github_api_base_url}/app/installations/{installation_id}/access_tokens",
            self._app_jwt(),
        )
        if response.status_code == 404:
            raise GitHubError(404, "installation not found (uninstalled or suspended)")
        return str(response.json()["token"])

    async def repositories(self, token: str) -> list[Repository]:
        return [
            Repository(
                github_id=int(r["id"]),
                full_name=str(r["full_name"]),
                html_url=str(r["html_url"]),
                default_branch=r.get("default_branch"),
                private=bool(r.get("private")),
                archived=bool(r.get("archived")),
            )
            async for r in self._paginate("/installation/repositories", token, key="repositories")
        ]

    async def file(self, token: str, full_name: str, path: str) -> str | None:
        response = await self._call(
            "GET", f"{self._s.github_api_base_url}/repos/{full_name}/contents/{path}", token
        )
        if response.status_code == 404:
            return None
        data = response.json()
        if (
            not isinstance(data, dict)
            or data.get("type") != "file"
            or int(data.get("size", 0)) > MAX_FILE_BYTES
        ):
            return None
        return base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")

    async def maintainers(self, token: str, full_name: str) -> list[tuple[str, str]]:
        """Direct collaborators with maintain/admin (role_name); requires Metadata: read."""
        found: list[tuple[str, str]] = []
        async for c in self._paginate(
            f"/repos/{full_name}/collaborators?affiliation=direct", token
        ):
            role = c.get("role_name")
            if role in ("maintain", "admin") and c.get("type") == "User":
                found.append((f"@{str(c['login']).lower()}", role))
        return found
