"""Case comments, @mentions and the activity feed.

Comments are human notes (append-only). The activity feed interleaves them with the
case's audit events, labelled by kind, so a reader can always tell a person's words from
a recorded system fact. Mentions notify the mentioned members asynchronously.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

import procrastinate
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select

from relay.audit import service as audit
from relay.audit.models import AuditEvent
from relay.continuity.models import CaseComment, CaseMention, ContinuityCase
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.notifications import service as notifications
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

CommentBody = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
]


class CommentIn(StrictInput):
    body: CommentBody
    mention_user_ids: Annotated[list[uuid.UUID], Field(max_length=20)] = []


class MentionView(BaseModel):
    user_id: uuid.UUID
    name: str


class ActivityView(BaseModel):
    kind: Literal["comment", "event"]
    id: uuid.UUID
    occurred_at: datetime
    actor_name: str | None
    # comment
    body: str | None = None
    mentions: list[MentionView] = []
    # event
    action: str | None = None
    details: dict[str, Any] = {}


async def _case(access: WorkspaceAccess, case_id: uuid.UUID) -> ContinuityCase:
    case = await access.session.scalar(
        select(ContinuityCase).where(
            ContinuityCase.id == case_id,
            visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
        )
    )
    if case is None:
        raise ApiError(404, "case_not_found", "Case not found.")
    return case


async def _names(access: WorkspaceAccess) -> dict[uuid.UUID, str]:
    rows = await access.session.execute(
        select(Membership.user_id, Membership.display_name, Membership.email).where(
            visible(access, Permission.MEMBER_READ, Membership.tenant_id)
        )
    )
    return {user_id: name or email or "Member" for user_id, name, email in rows}


async def add_comment(
    access: WorkspaceAccess, case_id: uuid.UUID, data: CommentIn, jobs: procrastinate.App
) -> ActivityView:
    authorize(access, Permission.CASE_COMMENT)
    case = await _case(access, case_id)
    mentioned = sorted(set(data.mention_user_ids))
    if mentioned:
        active = set(
            await access.session.scalars(
                select(Membership.user_id).where(
                    Membership.user_id.in_(mentioned),
                    Membership.status == "active",
                    visible(access, Permission.MEMBER_READ, Membership.tenant_id),
                )
            )
        )
        if active != set(mentioned):
            raise ApiError(422, "mention_not_member", "Only active members can be mentioned.")
    comment = CaseComment(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        case_id=case.id,
        author_user_id=access.user_id,
        body=data.body,
    )
    access.session.add(comment)
    await access.session.flush()
    access.session.add_all(
        CaseMention(tenant_id=access.tenant_id, comment_id=comment.id, user_id=user_id)
        for user_id in mentioned
    )
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="case.comment_added",
        actor_user_id=access.user_id,
        target_type="continuity_case",
        target_id=case.id,
        details={"comment_id": str(comment.id), "mentions": len(mentioned)},
    )
    if mentioned:
        await notifications.request(
            access.session,
            jobs,
            tenant_id=access.tenant_id,
            kind="mentioned",
            case_id=case.id,
            recipients=mentioned,
            actor_user_id=access.user_id,
            dedupe=f"mentioned:{comment.id}",
        )
    await access.session.flush()
    await access.session.refresh(comment)
    names = await _names(access)
    return ActivityView(
        kind="comment",
        id=comment.id,
        occurred_at=comment.created_at,
        actor_name=names.get(access.user_id),
        body=comment.body,
        mentions=[MentionView(user_id=u, name=names.get(u, "Member")) for u in mentioned],
    )


async def case_activity(access: WorkspaceAccess, case_id: uuid.UUID) -> list[ActivityView]:
    authorize(access, Permission.CASE_READ)
    case = await _case(access, case_id)
    names = await _names(access)
    comments = list(
        await access.session.scalars(
            select(CaseComment)
            .where(
                CaseComment.case_id == case.id,
                visible(access, Permission.CASE_READ, CaseComment.tenant_id),
            )
            .order_by(CaseComment.created_at.desc())
            .limit(500)
        )
    )
    mentions: dict[uuid.UUID, list[MentionView]] = {}
    for m in await access.session.scalars(
        select(CaseMention).where(CaseMention.comment_id.in_([c.id for c in comments]))
    ):
        mentions.setdefault(m.comment_id, []).append(
            MentionView(user_id=m.user_id, name=names.get(m.user_id, "Member"))
        )
    events = await access.session.scalars(
        select(AuditEvent)
        .where(
            AuditEvent.target_type == "continuity_case",
            AuditEvent.target_id == case.id,
            AuditEvent.action != "case.comment_added",  # the comment itself is shown instead
            visible(access, Permission.CASE_READ, AuditEvent.tenant_id),
        )
        .order_by(AuditEvent.occurred_at.desc())
        .limit(500)
    )
    feed = [
        ActivityView(
            kind="comment",
            id=c.id,
            occurred_at=c.created_at,
            actor_name=names.get(c.author_user_id),
            body=c.body,
            mentions=mentions.get(c.id, []),
        )
        for c in comments
    ] + [
        ActivityView(
            kind="event",
            id=e.id,
            occurred_at=e.occurred_at,
            actor_name=names.get(e.actor_user_id) if e.actor_user_id else "Relay",
            action=e.action,
            details=e.details,
        )
        for e in events
    ]
    return sorted(feed, key=lambda a: (a.occurred_at, a.id), reverse=True)
