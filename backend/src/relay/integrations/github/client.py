"""GitHub App client: least-privilege, no persisted tokens.

App permissions (all read-only; GitHub docs, checked 2026-11-08):
- Repository > Metadata: read      — repositories, collaborators
- Repository > Contents: read      — CODEOWNERS and catalog-info.yaml only
- Repository > Pull requests: read — PR metadata (no diffs, no bodies are stored)
- Repository > Issues: read        — issue metadata (no bodies are stored)
- Organization > Members: read     — teams and team membership
Missing optional permissions degrade gracefully (403 -> an actionable sync note).
"Request user authorization (OAuth) during installation" must be enabled so the install
redirect carries a `code`; it is exchanged once to verify the installation belongs to the
user (`GET /user/installations`), because `installation_id` on the redirect can be spoofed.
"""

import base64
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
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
    pushed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class User:
    github_id: int
    login: str


@dataclass(frozen=True, slots=True)
class Team:
    github_id: int
    slug: str
    name: str


@dataclass(frozen=True, slots=True)
class WorkItem:
    kind: str  # pull_request | issue
    number: int
    github_id: int
    title: str
    state: str  # open | closed | merged
    author: User | None
    assignees: tuple[User, ...]
    reviewers: tuple[User, ...]
    labels: tuple[str, ...]
    html_url: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    merged_at: datetime | None


def _when(value: object) -> datetime | None:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None


def _user(value: object) -> User | None:
    if not isinstance(value, dict) or value.get("type") not in ("User", None):
        return None
    return User(int(value["id"]), str(value["login"]).lower())


def _users(values: object) -> tuple[User, ...]:
    found = (_user(v) for v in values) if isinstance(values, list) else ()
    return tuple(u for u in found if u is not None)


def work_item(data: dict[str, Any], kind: str) -> WorkItem:
    """Normalise a REST or webhook PR/issue object to metadata (bodies are dropped)."""
    merged_at = _when(data.get("merged_at"))
    state = "merged" if merged_at else str(data.get("state", "open"))
    return WorkItem(
        kind=kind,
        number=int(data["number"]),
        github_id=int(data["id"]),
        title=str(data.get("title") or "")[:300],
        state=state if state in ("open", "closed", "merged") else "open",
        author=_user(data.get("user")),
        assignees=_users(data.get("assignees")),
        reviewers=_users(data.get("requested_reviewers")),
        labels=tuple(
            str(lb["name"])[:100] for lb in data.get("labels") or [] if isinstance(lb, dict)
        ),
        html_url=str(data["html_url"]),
        created_at=_when(data["created_at"]),  # type: ignore[arg-type]
        updated_at=_when(data["updated_at"]),  # type: ignore[arg-type]
        closed_at=_when(data.get("closed_at")),
        merged_at=merged_at,
    )


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
                pushed_at=_when(r.get("pushed_at")),
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

    async def maintainer_users(self, token: str, full_name: str) -> list[tuple[User, str]]:
        found: list[tuple[User, str]] = []
        async for c in self._paginate(
            f"/repos/{full_name}/collaborators?affiliation=direct", token
        ):
            if c.get("role_name") in ("maintain", "admin") and c.get("type") == "User":
                found.append((User(int(c["id"]), str(c["login"]).lower()), str(c["role_name"])))
        return found

    # ---- organisation directory (Organization > Members: read)

    async def teams(self, token: str, org: str) -> list[Team]:
        return [
            Team(int(t["id"]), str(t["slug"]).lower(), str(t["name"]))
            async for t in self._paginate(f"/orgs/{org}/teams", token)
        ]

    async def team_members(self, token: str, org: str, slug: str) -> list[User]:
        return [
            User(int(u["id"]), str(u["login"]).lower())
            async for u in self._paginate(f"/orgs/{org}/teams/{slug}/members", token)
            if u.get("type", "User") == "User"
        ]

    async def profile(self, token: str, login: str) -> tuple[str | None, str | None]:
        """Public display name and public email (what the user chose to publish)."""
        response = await self._call("GET", f"{self._s.github_api_base_url}/users/{login}", token)
        if response.status_code == 404:
            return None, None
        data = response.json()
        return (data.get("name") or None), (
            str(data["email"]).lower() if data.get("email") else None
        )

    # ---- activity metadata (Pull requests / Issues: read)

    async def work_items(
        self, token: str, full_name: str, since: datetime, limit: int = 200
    ) -> list[WorkItem]:
        """Recently updated PRs and issues, newest first; metadata only."""
        items: list[WorkItem] = []
        async for pr in self._paginate(
            f"/repos/{full_name}/pulls?state=all&sort=updated&direction=desc", token
        ):
            item = work_item(pr, "pull_request")
            if item.updated_at < since or len(items) >= limit:
                break
            items.append(item)
        issues = 0
        async for issue in self._paginate(
            f"/repos/{full_name}/issues?state=all&sort=updated&direction=desc"
            f"&since={since.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            token,
        ):
            if "pull_request" in issue:  # PRs are covered above, with review data
                continue
            if issues >= limit:
                break
            items.append(work_item(issue, "issue"))
            issues += 1
        return items
