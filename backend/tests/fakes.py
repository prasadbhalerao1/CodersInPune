"""In-memory doubles for WorkOS and GitHub HTTP APIs (automated tests only).

They model the documented request/response shapes; real-account behaviour still needs
the manual checks listed in README. The GitHub app JWT is really verified here.
"""

import base64
import json
from dataclasses import dataclass, field
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

GITHUB_APP_ID = "123456"


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


@dataclass
class FakeExternal:
    workos_users: dict[str, dict[str, Any]] = field(default_factory=dict)
    sent_invitations: list[str] = field(default_factory=list)
    oauth_codes: dict[str, list[int]] = field(default_factory=dict)  # code -> installation ids
    revoked_installations: set[int] = field(default_factory=set)
    repos: list[FakeRepo] = field(default_factory=list)
    github_down: bool = False

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

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host, path, method = request.url.host, request.url.path, request.method
        if host == "api.workos.com":
            return self._workos(method, path, request)
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
                }
                for r in self.repos
            ]
            return httpx.Response(200, json={"total_count": len(repos), "repositories": repos})
        for repo in self.repos:
            prefix = f"/repos/{repo.full_name}"
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
                        {"login": login, "type": "User", "role_name": role}
                        for login, role in repo.collaborators
                    ],
                )
        return httpx.Response(404)
