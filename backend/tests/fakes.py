"""In-memory doubles for WorkOS and GitHub HTTP APIs (automated tests only).

They model the documented request/response shapes; real-account behaviour still needs
the manual checks listed in README. The GitHub app JWT is really verified here.
"""

import base64
import json
import zlib
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

GITHUB_APP_ID = "123456"


def user_id(login: str) -> int:
    """Stable fake GitHub user id for a login."""
    return zlib.crc32(login.lower().encode()) + 1000


def gh_user(login: str) -> dict[str, Any]:
    return {"id": user_id(login), "login": login, "type": "User"}


def _private_key_pem() -> tuple[str, Any]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return pem, key.public_key()


@dataclass
class FakeRepo:
    id: int
    full_name: str
    files: dict[str, str] = field(default_factory=dict)
    collaborators: list[tuple[str, str]] = field(default_factory=list)  # (login, role_name)
    archived: bool = False
    pulls: list[dict[str, Any]] = field(default_factory=list)  # REST pull objects
    issues: list[dict[str, Any]] = field(default_factory=list)  # REST issue objects
    pushed_at: str | None = None


@dataclass
class FakeExternal:
    workos_users: dict[str, dict[str, Any]] = field(default_factory=dict)
    sent_invitations: list[str] = field(default_factory=list)
    oauth_codes: dict[str, list[int]] = field(default_factory=dict)  # code -> installation ids
    revoked_installations: set[int] = field(default_factory=set)
    repos: list[FakeRepo] = field(default_factory=list)
    github_down: bool = False
    teams: dict[str, list[str]] = field(default_factory=dict)  # slug -> member logins
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)  # login -> name/email
    activity_forbidden: bool = False  # simulate missing Pull requests/Issues permission
    members_forbidden: bool = False  # simulate missing Organization > Members permission
    calls: list[str] = field(default_factory=list)
    # Resend: list of outcomes to return in order ("ok", "500", "422", "timeout"); then "ok".
    resend_script: list[str] = field(default_factory=list)
    emails: list[dict[str, Any]] = field(default_factory=list)  # accepted messages
    resend_keys: dict[str, str] = field(default_factory=dict)  # idempotency key -> id
    resend_requests: int = 0

    def __post_init__(self) -> None:
        self.private_key_pem, self._public_key = _private_key_pem()

    @property
    def github_settings(self) -> dict[str, Any]:
        return {
            "github_app_id": GITHUB_APP_ID,
            "github_app_slug": "relay-test",
            "github_client_id": "Iv1.test",
            "github_client_secret": "client-secret",
            "github_private_key": self.private_key_pem,
            "workos_api_key": "sk_test_fake",
        }

    email_settings: dict[str, Any] = field(
        default_factory=lambda: {
            "resend_api_key": "re_test_key",
            "email_from": "Relay <notifications@relay.test>",
            "frontend_base_url": "https://relay.test",
        }
    )

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host, path, method = request.url.host, request.url.path, request.method
        if host == "api.workos.com":
            return self._workos(method, path, request)
        if host == "api.resend.com":
            return self._resend(request)
        if self.github_down:
            return httpx.Response(502)
        if host == "github.com" and path == "/login/oauth/access_token":
            code = dict(httpx.QueryParams(request.content.decode())).get("code", "")
            if code in self.oauth_codes:
                return httpx.Response(
                    200, json={"access_token": f"ghu_{code}", "token_type": "bearer"}
                )
            return httpx.Response(200, json={"error": "bad_verification_code"})
        if host == "api.github.com":
            return self._github(method, path, request)
        return httpx.Response(404)

    def _resend(self, request: httpx.Request) -> httpx.Response:
        if request.headers.get("authorization") != "Bearer re_test_key":
            return httpx.Response(401, json={"name": "missing_api_key"})
        self.resend_requests += 1
        key = request.headers.get("idempotency-key", "")
        if key in self.resend_keys:  # Resend replays the original response for a key
            return httpx.Response(200, json={"id": self.resend_keys[key]})
        outcome = self.resend_script.pop(0) if self.resend_script else "ok"
        if outcome == "timeout":
            raise httpx.ReadTimeout("timed out", request=request)
        if outcome != "ok":
            return httpx.Response(int(outcome), json={"name": "validation_error"})
        message_id = f"email_{len(self.emails) + 1}"
        self.resend_keys[key] = message_id
        self.emails.append({**json.loads(request.content), "idempotency_key": key})
        return httpx.Response(200, json={"id": message_id})

    def _workos(self, method: str, path: str, request: httpx.Request) -> httpx.Response:
        if request.headers.get("authorization") != "Bearer sk_test_fake":
            return httpx.Response(401)
        if method == "GET" and path.startswith("/user_management/users/"):
            user = self.workos_users.get(path.rsplit("/", 1)[-1])
            return httpx.Response(200, json=user) if user else httpx.Response(404)
        if method == "POST" and path == "/user_management/invitations":
            email = json.loads(request.content)["email"]
            self.sent_invitations.append(email)
            return httpx.Response(
                201, json={"id": f"invitation_{len(self.sent_invitations)}", "email": email}
            )
        if method == "POST" and path.endswith("/revoke"):
            return httpx.Response(200, json={"id": path.split("/")[-2], "state": "revoked"})
        return httpx.Response(404)

    def _github(self, method: str, path: str, request: httpx.Request) -> httpx.Response:
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        self.calls.append(f"{method} {request.url.path}?{request.url.query.decode()}")
        if path == "/user/installations":
            code = token.removeprefix("ghu_")
            ids = self.oauth_codes.get(code, [])
            return httpx.Response(
                200,
                json={
                    "total_count": len(ids),
                    "installations": [
                        {"id": i, "account": {"login": "acme", "type": "Organization"}} for i in ids
                    ],
                },
            )
        if method == "POST" and path.startswith("/app/installations/"):
            claims = jwt.decode(token, self._public_key, algorithms=["RS256"])
            assert claims["iss"] == GITHUB_APP_ID
            installation = int(path.split("/")[3])
            if installation in self.revoked_installations:
                return httpx.Response(404)
            return httpx.Response(201, json={"token": f"ghs_{installation}"})
        if not token.startswith("ghs_"):
            return httpx.Response(401)
        if path == "/installation/repositories":
            repos = [
                {
                    "id": r.id,
                    "full_name": r.full_name,
                    "html_url": f"https://github.com/{r.full_name}",
                    "default_branch": "main",
                    "private": True,
                    "archived": r.archived,
                    "pushed_at": r.pushed_at,
                }
                for r in self.repos
            ]
            return httpx.Response(200, json={"total_count": len(repos), "repositories": repos})
        page = int(request.url.params.get("page", "1"))
        if path.startswith("/users/"):
            login = path.rsplit("/", 1)[-1]
            return httpx.Response(200, json={**gh_user(login), **self.profiles.get(login, {})})
        if path.startswith("/orgs/"):
            if self.members_forbidden:
                return httpx.Response(403)
            parts = path.split("/")
            if path.endswith("/teams"):
                body = [
                    {"id": zlib.crc32(slug.encode()), "slug": slug, "name": slug.title()}
                    for slug in self.teams
                ]
                return httpx.Response(200, json=body if page == 1 else [])
            if path.endswith("/members"):
                members = [gh_user(m) for m in self.teams.get(parts[4], [])]
                return httpx.Response(200, json=members if page == 1 else [])
        for repo in self.repos:
            prefix = f"/repos/{repo.full_name}"
            if path in (f"{prefix}/pulls", f"{prefix}/issues"):
                if self.activity_forbidden:
                    return httpx.Response(403)
                items = repo.pulls if path.endswith("/pulls") else repo.issues
                return httpx.Response(200, json=items if page == 1 else [])
            if path.startswith(f"{prefix}/contents/"):
                content = repo.files.get(path.removeprefix(f"{prefix}/contents/"))
                if content is None:
                    return httpx.Response(404)
                encoded = base64.b64encode(content.encode()).decode()
                return httpx.Response(
                    200, json={"type": "file", "size": len(content), "content": encoded}
                )
            if path == f"{prefix}/collaborators":
                return httpx.Response(
                    200,
                    json=[
                        {**gh_user(login), "role_name": role} for login, role in repo.collaborators
                    ],
                )
        return httpx.Response(404)


def pull(
    number: int,
    author: str,
    *,
    updated: str = "2026-11-01T10:00:00Z",
    state: str = "open",
    merged: str | None = None,
    reviewers: tuple[str, ...] = (),
    repo: str = "acme/payments",
) -> dict[str, Any]:
    """A REST pull request object (with a body, which Relay must never store)."""
    return {
        "id": 900_000 + number,
        "number": number,
        "title": f"Change {number}",
        "body": "SECRET BODY TEXT",
        "state": state,
        "user": gh_user(author),
        "assignees": [],
        "requested_reviewers": [gh_user(r) for r in reviewers],
        "labels": [{"name": "backend"}],
        "html_url": f"https://github.com/{repo}/pull/{number}",
        "created_at": "2026-10-01T10:00:00Z",
        "updated_at": updated,
        "closed_at": merged,
        "merged_at": merged,
    }
