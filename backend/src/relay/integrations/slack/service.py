"""Slack: post what people choose to share to a channel, through a Slack incoming webhook.

Relay only writes to Slack, and only when a person presses "Post to Slack": nothing is read
from Slack and nothing is posted automatically. The webhook URL grants posting to one
channel, so it is encrypted at rest, never returned by the API, and checked with a test
message before it is saved.
"""

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

import httpx
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select

from relay.audit import service as audit
from relay.config import Settings
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.slack.models import SlackConnection
from relay.intelligence import meetings
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.shared import secrets
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

WEBHOOK_PREFIX = "https://hooks.slack.com/services/"
TIMEOUT = httpx.Timeout(10.0)
KIND_ICON = {"decision": "✅", "action": "📌", "question": "❓", "risk": "⚠️"}


class SlackIn(StrictInput):
    webhook_url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
    channel: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class SlackStatus(BaseModel):
    connected: bool
    channel: str | None = None
    connected_at: datetime | None = None
    last_posted_at: datetime | None = None
    last_error: str | None = None
    can_manage: bool
    available: bool  # the server can encrypt secrets


class PostedView(BaseModel):
    channel: str
    posted_at: datetime


async def _connection(access: WorkspaceAccess) -> SlackConnection | None:
    return await access.session.scalar(
        select(SlackConnection).where(
            visible(access, Permission.WORKSPACE_READ, SlackConnection.tenant_id)
        )
    )


async def status(access: WorkspaceAccess, settings: Settings) -> SlackStatus:
    authorize(access, Permission.WORKSPACE_READ)
    c = await _connection(access)
    return SlackStatus(
        connected=c is not None,
        channel=c.channel if c else None,
        connected_at=c.connected_at if c else None,
        last_posted_at=c.last_posted_at if c else None,
        last_error=c.last_error if c else None,
        can_manage=role_allows(access.role, Permission.INTEGRATION_MANAGE),
        available=secrets.can_encrypt(settings),
    )


async def _post(url: str, payload: dict[str, Any]) -> str | None:
    """Post to the webhook; returns an error code, or None when Slack accepted it."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError:
        return "slack_unreachable"
    if response.status_code == 200:
        return None
    # Slack answers with a short reason, e.g. "invalid_token" or "channel_is_archived".
    return f"slack_{response.text.strip()[:40] or response.status_code}"


async def connect(access: WorkspaceAccess, data: SlackIn, settings: Settings) -> SlackStatus:
    authorize(access, Permission.INTEGRATION_MANAGE)
    if not secrets.can_encrypt(settings):
        raise ApiError(503, "secrets_unavailable", "This server can't store integration secrets.")
    if not data.webhook_url.startswith(WEBHOOK_PREFIX):
        raise ApiError(
            422, "invalid_webhook", f"Paste a Slack incoming-webhook URL ({WEBHOOK_PREFIX}…)."
        )
    channel = data.channel.lstrip("#")
    error = await _post(
        data.webhook_url,
        {"text": f"Relay is connected. Handover updates people share will appear in #{channel}."},
    )
    if error:
        raise ApiError(422, "slack_rejected", f"Slack didn't accept a test message ({error}).")
    c = await _connection(access)
    if c is None:
        c = SlackConnection(tenant_id=access.tenant_id, webhook_encrypted="", channel=channel)
        access.session.add(c)
    c.webhook_encrypted = secrets.encrypt(settings, data.webhook_url)
    c.channel = channel
    c.connected_by = access.user_id
    c.connected_at = datetime.now(UTC)
    c.last_error = None
    await access.session.flush()
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="integration.slack_connected",
        actor_user_id=access.user_id,
        target_type="slack_connection",
        target_id=c.id,
        details={},
    )
    return await status(access, settings)


async def disconnect(access: WorkspaceAccess) -> None:
    authorize(access, Permission.INTEGRATION_MANAGE)
    c = await _connection(access)
    if c is None:
        return
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="integration.slack_disconnected",
        actor_user_id=access.user_id,
        target_type="slack_connection",
        target_id=c.id,
        details={},
    )
    await access.session.delete(c)


def meeting_message(m: meetings.MeetingDetail, link: str) -> dict[str, Any]:
    """Slack Block Kit message: the meeting's items (not the transcript), with a link back."""
    shown = [i for i in m.items if i.status != "dismissed"]
    lines = []
    for item in shown[:25]:
        extra = ", ".join(
            x for x in (item.owner_name and f"owner {item.owner_name}", item.due_text) if x
        )
        mark = " _(accepted)_" if item.status == "accepted" else ""
        lines.append(f"{KIND_ICON[item.kind]} {item.text}{f' ({extra})' if extra else ''}{mark}")
    body = "\n".join(lines) or "No decisions, actions, questions or risks were found."
    title = f"{m.title} · {m.held_at:%d %b %Y}"
    return {
        "text": f"Meeting summary: {title}",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": title[:150]}},
            {"type": "section", "text": {"type": "mrkdwn", "text": body[:2900]}},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Shared from Relay. Every item cites the transcript line it "
                        f"came from: <{link}|open the meeting>.",
                    }
                ],
            },
        ],
    }


async def share_meeting(
    access: WorkspaceAccess, meeting_id: uuid.UUID, settings: Settings
) -> PostedView:
    authorize(access, Permission.KNOWLEDGE_WRITE)
    m = await meetings.get_meeting(access, meeting_id)
    c = await _connection(access)
    if c is None:
        raise ApiError(409, "slack_not_connected", "Connect Slack in Integrations first.")
    link = f"{settings.frontend_base_url}/w/{access.tenant_id}/meetings/{m.id}"
    error = await _post(secrets.decrypt(settings, c.webhook_encrypted), meeting_message(m, link))
    c.last_error = error
    if error:
        raise ApiError(502, "slack_rejected", f"Slack didn't accept the message ({error}).")
    c.last_posted_at = datetime.now(UTC)
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="integration.slack_posted",
        actor_user_id=access.user_id,
        target_type="meeting",
        target_id=m.id,
        details={"items": len(m.items)},
    )
    return PostedView(channel=c.channel, posted_at=c.last_posted_at)
