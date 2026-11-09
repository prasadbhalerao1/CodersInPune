"""Notion REST client (read content only).

Errors: 401 -> NotionError(401) (access revoked); 403/404 on an object -> NotionError(404)
(deleted or no longer shared); network errors, 429 and 5xx -> transient.
Page text is extracted from blocks as plain text with light Markdown markers; nested
blocks are read to MAX_DEPTH and at most MAX_BLOCKS per page, so a huge page can't stall
a sync. Comments, users and files are never requested.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from relay.config import Settings
from relay.shared.oauth import TokenGrant

NOTION_VERSION = "2022-06-28"
MAX_DEPTH = 2
MAX_BLOCKS = 1000
_PREFIX = {
    "heading_1": "# ",
    "heading_2": "## ",
    "heading_3": "### ",
    "bulleted_list_item": "- ",
    "numbered_list_item": "1. ",
    "quote": "> ",
    "callout": "> ",
    "toggle": "",
    "paragraph": "",
    "code": "",
}


class NotionError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status

    @property
    def transient(self) -> bool:
        return self.status == 0 or self.status == 429 or self.status >= 500


@dataclass(frozen=True, slots=True)
class Grant:
    token: TokenGrant
    workspace_id: str
    workspace_name: str


def parse_when(value: object) -> datetime | None:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None


def _plain(rich: list[dict[str, Any]] | None) -> str:
    return "".join(str(part.get("plain_text") or "") for part in rich or [])


def title_of(obj: dict[str, Any]) -> str:
    if obj.get("object") == "database":
        return _plain(obj.get("title")).strip() or "Untitled"
    for prop in (obj.get("properties") or {}).values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            return _plain(prop.get("title")).strip() or "Untitled"
    return "Untitled"


def is_gone(obj: dict[str, Any]) -> bool:
    return bool(obj.get("archived") or obj.get("in_trash"))


def is_database_row(obj: dict[str, Any]) -> bool:
    return (obj.get("parent") or {}).get("type") in ("database_id", "data_source_id")


def _block_line(block: dict[str, Any]) -> str | None:
    kind = str(block.get("type"))
    data = block.get(kind) or {}
    if kind == "to_do":
        return f"[{'x' if data.get('checked') else ' '}] {_plain(data.get('rich_text'))}"
    if kind == "child_page":
        return f"Subpage: {data.get('title') or 'Untitled'}"
    if kind == "divider":
        return "---"
    if kind in _PREFIX:
        return _PREFIX[kind] + _plain(data.get("rich_text"))
    return None  # images, files, embeds, synced blocks: not imported


class NotionClient:
    def __init__(self, settings: Settings, http: httpx.AsyncClient) -> None:
        self._s = settings
        self._http = http

    @property
    def settings(self) -> Settings:
        return self._s

    @property
    def configured(self) -> bool:
        s = self._s
        return bool(s.notion_client_id and s.notion_client_secret and s.integration_encryption_key)

    @property
    def redirect_uri(self) -> str:
        return f"{self._s.frontend_base_url.rstrip('/')}/integrations/notion/callback"

    def authorize_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self._s.notion_client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "owner": "user",
                "state": state,
            }
        )
        return f"{self._s.notion_api_url}/oauth/authorize?{query}"

    async def _token(self, payload: dict[str, str]) -> dict[str, object]:
        assert self._s.notion_client_id
        assert self._s.notion_client_secret
        try:
            response = await self._http.post(
                f"{self._s.notion_api_url}/oauth/token",
                json=payload,
                auth=(self._s.notion_client_id, self._s.notion_client_secret.get_secret_value()),
            )
        except httpx.HTTPError as exc:
            raise NotionError(0, "Notion unreachable") from exc
        if response.status_code >= 500 or response.status_code == 429:
            raise NotionError(response.status_code, "Notion token endpoint unavailable")
        body: dict[str, object] = response.json() if response.status_code == 200 else {}
        if TokenGrant.from_response(body) is None:
            raise NotionError(401, "Notion rejected the token request")
        return body

    async def exchange_code(self, code: str) -> Grant:
        body = await self._token(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": self.redirect_uri}
        )
        token = TokenGrant.from_response(body)
        assert token is not None
        return Grant(
            token=token,
            workspace_id=str(body.get("workspace_id") or body.get("bot_id")),
            workspace_name=str(body.get("workspace_name") or "Notion workspace"),
        )

    async def refresh(self, refresh_token: str) -> TokenGrant:
        body = await self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})
        token = TokenGrant.from_response(body)
        assert token is not None
        return token

    async def _call(
        self, token: str, method: str, path: str, json: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        try:
            response = await self._http.request(
                method,
                f"{self._s.notion_api_url}{path}",
                json=json,
                headers={"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION},
            )
        except httpx.HTTPError as exc:
            raise NotionError(0, f"Notion unreachable: {type(exc).__name__}") from exc
        if response.status_code == 401:
            raise NotionError(401, "Notion access was revoked")
        if response.status_code in (403, 404):
            raise NotionError(404, "Not found or no longer shared with Relay")
        if response.status_code >= 400:
            raise NotionError(response.status_code, f"Notion returned {response.status_code}")
        return dict(response.json())

    async def _pages(
        self, token: str, method: str, path: str, body: dict[str, Any] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        cursor: str | None = None
        while True:
            if method == "GET":
                query = {"page_size": 100, **({"start_cursor": cursor} if cursor else {})}
                data = await self._call(token, "GET", f"{path}?{urlencode(query)}")
            else:
                payload = {**(body or {}), "page_size": 100}
                if cursor:
                    payload["start_cursor"] = cursor
                data = await self._call(token, "POST", path, payload)
            for item in data.get("results") or []:
                yield item
            if not data.get("has_more"):
                return
            cursor = data.get("next_cursor")

    async def search(self, token: str, limit: int) -> list[dict[str, Any]]:
        """Everything shared with the integration (pages and databases)."""
        found: list[dict[str, Any]] = []
        async for obj in self._pages(token, "POST", "/search", {}):
            found.append(obj)
            if len(found) >= limit:
                break
        return found

    async def database_pages(
        self, token: str, database_id: str, limit: int
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        async for row in self._pages(token, "POST", f"/databases/{database_id}/query", {}):
            rows.append(row)
            if len(rows) >= limit:
                break
        return rows

    async def page_text(self, token: str, page_id: str) -> str:
        lines: list[str] = []

        async def walk(block_id: str, depth: int) -> None:
            async for block in self._pages(token, "GET", f"/blocks/{block_id}/children"):
                if len(lines) >= MAX_BLOCKS:
                    return
                line = _block_line(block)
                if line is not None:
                    lines.append("  " * depth + line)
                nested = block.get("type") not in ("child_page", "child_database")
                if block.get("has_children") and depth < MAX_DEPTH and nested:
                    await walk(str(block["id"]), depth + 1)

        await walk(page_id, 0)
        return "\n".join(lines).strip()
