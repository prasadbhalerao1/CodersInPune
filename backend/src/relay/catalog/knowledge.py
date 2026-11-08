"""Responsibility knowledge: capture, review, freshness, search, and case handover.

Knowledge always belongs to a responsibility and keeps its author and source URL.
Freshness is derived from the last review: fresh <= REVIEW_DAYS, stale after that, and a
responsibility with no active knowledge is "missing". Visibility "managers" limits an
item to people who manage responsibilities (owners/admins); everything else follows the
responsibility's normal read access. Search is PostgreSQL full-text search.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints
from sqlalchemy import ColumnElement, and_, func, select, true

from relay.catalog import service as catalog
from relay.catalog.models import KnowledgeItem, Responsibility
from relay.continuity.models import CaseKnowledge, CaseScopeItem, ContinuityCase
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.shared.api_types import LongText, Name, StrictInput
from relay.shared.errors import ApiError

REVIEW_DAYS = 90
Kind = Literal["note", "link", "document", "procedure", "context"]
Visibility = Literal["workspace", "managers"]
Freshness = Literal["fresh", "stale"]
Body = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20000)]
Url = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000, pattern=r"^https?://\S+$")
]


class KnowledgeIn(StrictInput):
    kind: Kind
    title: Name
    body: Body | None = None
    url: Url | None = None
    visibility: Visibility = "workspace"


class KnowledgeUpdate(StrictInput):
    title: Name | None = None
    body: Body | None = None
    url: Url | None = None
    kind: Kind | None = None
    visibility: Visibility | None = None
    status: Literal["active", "archived"] | None = None


class KnowledgeView(BaseModel):
    id: uuid.UUID
    responsibility_id: uuid.UUID
    responsibility_name: str
    kind: str
    title: str
    body: str | None
    url: str | None
    visibility: str
    origin: str
    status: str
    author_name: str
    created_at: datetime
    updated_at: datetime
    last_reviewed_at: datetime | None
    last_reviewed_by_name: str | None
    freshness: Freshness
    can_edit: bool


class KnowledgeCoverageView(BaseModel):
    responsibility_id: uuid.UUID
    responsibility_name: str
    criticality: str
    items: int
    stale: int


class KnowledgeOverviewView(BaseModel):
    results: list[KnowledgeView]
    missing: list[KnowledgeCoverageView]
    stale_items: int
    fresh_items: int


class HandoverIn(StrictInput):
    responsibility_id: uuid.UUID
    outcome: Literal["handed_over", "missing"]
    knowledge_item_id: uuid.UUID | None = None
    note: LongText | None = None


class HandoverRecordView(BaseModel):
    id: uuid.UUID
    knowledge_item_id: uuid.UUID | None
    outcome: str
    note: str | None
    recorded_by_name: str
    recorded_at: datetime


class CaseKnowledgeItemView(BaseModel):
    responsibility_id: uuid.UUID
    responsibility_name: str
    knowledge: list[KnowledgeView]
    records: list[HandoverRecordView]


def _now() -> datetime:
    return datetime.now(UTC)


def _readable(access: WorkspaceAccess) -> ColumnElement[bool]:
    """Row filter: workspace items for readers; 'managers' items only for managers."""
    managers = role_allows(access.role, Permission.RESPONSIBILITY_MANAGE)
    return and_(
        visible(access, Permission.RESPONSIBILITY_READ, KnowledgeItem.tenant_id),
        true() if managers else KnowledgeItem.visibility == "workspace",
    )


async def _names(access: WorkspaceAccess) -> dict[uuid.UUID, str]:
    rows = await access.session.execute(
        select(Membership.user_id, Membership.display_name, Membership.email).where(
            visible(access, Permission.MEMBER_READ, Membership.tenant_id)
        )
    )
    return {user_id: name or email or "Member" for user_id, name, email in rows}


def _freshness(item: KnowledgeItem, now: datetime) -> Freshness:
    reviewed = item.last_reviewed_at or item.created_at
    return "fresh" if reviewed >= now - timedelta(days=REVIEW_DAYS) else "stale"


def _view(
    access: WorkspaceAccess,
    item: KnowledgeItem,
    responsibility_name: str,
    names: dict[uuid.UUID, str],
    now: datetime,
) -> KnowledgeView:
    return KnowledgeView(
        id=item.id,
        responsibility_id=item.responsibility_id,
        responsibility_name=responsibility_name,
        kind=item.kind,
        title=item.title,
        body=item.body,
        url=item.url,
        visibility=item.visibility,
        origin=item.origin,
        status=item.status,
        author_name=names.get(item.author_user_id, "Former member"),
        created_at=item.created_at,
        updated_at=item.updated_at,
        last_reviewed_at=item.last_reviewed_at,
        last_reviewed_by_name=names.get(item.last_reviewed_by) if item.last_reviewed_by else None,
        freshness=_freshness(item, now),
        can_edit=item.author_user_id == access.user_id
        or role_allows(access.role, Permission.RESPONSIBILITY_MANAGE),
    )


async def _items(
    access: WorkspaceAccess, *conditions: ColumnElement[bool], limit: int = 200
) -> list[KnowledgeView]:
    rows = (
        await access.session.execute(
            select(KnowledgeItem, Responsibility.name)
            .join(Responsibility, Responsibility.id == KnowledgeItem.responsibility_id)
            .where(_readable(access), *conditions)
            .order_by(KnowledgeItem.updated_at.desc())
            .limit(limit)
        )
    ).all()
    names, now = await _names(access), _now()
    return [_view(access, item, name, names, now) for item, name in rows]


async def _editable(access: WorkspaceAccess, item_id: uuid.UUID) -> KnowledgeItem:
    item = await access.session.scalar(
        select(KnowledgeItem)
        .where(KnowledgeItem.id == item_id, _readable(access))
        .with_for_update()
    )
    if item is None:
        raise ApiError(404, "knowledge_not_found", "Knowledge not found.")
    if item.author_user_id != access.user_id:
        authorize(access, Permission.RESPONSIBILITY_MANAGE)
    return item


# ---------------------------------------------------------------- commands


async def add_knowledge(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, data: KnowledgeIn
) -> KnowledgeView:
    authorize(access, Permission.KNOWLEDGE_WRITE)
    if data.visibility == "managers":
        authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await catalog.require_active_responsibility(access, responsibility_id)
    if not data.body and not data.url:
        raise ApiError(422, "content_required", "Add a link or some content.")
    item = KnowledgeItem(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        responsibility_id=responsibility_id,
        kind=data.kind,
        title=data.title,
        body=data.body or None,
        url=data.url or None,
        visibility=data.visibility,
        author_user_id=access.user_id,
        last_reviewed_by=access.user_id,
        last_reviewed_at=_now(),
    )
    access.session.add(item)
    await access.session.flush()
    catalog.record_audit(
        access,
        "knowledge.created",
        "responsibility",
        responsibility_id,
        knowledge_id=str(item.id),
        kind=data.kind,
    )
    return (await _items(access, KnowledgeItem.id == item.id))[0]


async def update_knowledge(
    access: WorkspaceAccess, item_id: uuid.UUID, data: KnowledgeUpdate
) -> KnowledgeView:
    authorize(access, Permission.KNOWLEDGE_WRITE)
    item = await _editable(access, item_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("visibility") == "managers":
        authorize(access, Permission.RESPONSIBILITY_MANAGE)
    for field, value in changes.items():
        setattr(item, field, (value or None) if field in ("body", "url") else value)
    if not item.body and not item.url:
        raise ApiError(422, "content_required", "Keep a link or some content.")
    item.updated_at = func.now()
    # Editing the content is a review by the editor.
    if {"title", "body", "url"} & changes.keys():
        item.last_reviewed_by, item.last_reviewed_at = access.user_id, _now()
    await access.session.flush()
    catalog.record_audit(
        access,
        "knowledge.archived" if changes.get("status") == "archived" else "knowledge.updated",
        "responsibility",
        item.responsibility_id,
        knowledge_id=str(item.id),
        fields=",".join(sorted(changes)),
    )
    return (await _items(access, KnowledgeItem.id == item.id))[0]


async def review_knowledge(access: WorkspaceAccess, item_id: uuid.UUID) -> KnowledgeView:
    """Confirm an item is still accurate (resets its freshness)."""
    authorize(access, Permission.KNOWLEDGE_WRITE)
    item = await access.session.scalar(
        select(KnowledgeItem)
        .where(KnowledgeItem.id == item_id, _readable(access))
        .with_for_update()
    )
    if item is None or item.status != "active":
        raise ApiError(404, "knowledge_not_found", "Knowledge not found.")
    item.last_reviewed_by, item.last_reviewed_at = access.user_id, _now()
    await access.session.flush()
    catalog.record_audit(
        access,
        "knowledge.reviewed",
        "responsibility",
        item.responsibility_id,
        knowledge_id=str(item.id),
    )
    return (await _items(access, KnowledgeItem.id == item.id))[0]


# ---------------------------------------------------------------- reads


async def responsibility_knowledge(
    access: WorkspaceAccess, responsibility_id: uuid.UUID
) -> list[KnowledgeView]:
    authorize(access, Permission.RESPONSIBILITY_READ)
    await catalog.get_responsibility(access, responsibility_id)  # 404 if not visible
    return await _items(
        access,
        KnowledgeItem.responsibility_id == responsibility_id,
        KnowledgeItem.status == "active",
    )


async def knowledge_overview(
    access: WorkspaceAccess, *, q: str | None = None, freshness: Freshness | None = None
) -> KnowledgeOverviewView:
    authorize(access, Permission.RESPONSIBILITY_READ)
    now = _now()
    conditions: list[ColumnElement[bool]] = [KnowledgeItem.status == "active"]
    if q:
        conditions.append(KnowledgeItem.search.op("@@")(func.websearch_to_tsquery("english", q)))
    cutoff = now - timedelta(days=REVIEW_DAYS)
    reviewed = func.coalesce(KnowledgeItem.last_reviewed_at, KnowledgeItem.created_at)
    if freshness == "stale":
        conditions.append(reviewed < cutoff)
    elif freshness == "fresh":
        conditions.append(reviewed >= cutoff)
    results = await _items(access, *conditions)
    counts = (
        await access.session.execute(
            select(
                func.count().filter(reviewed < cutoff), func.count().filter(reviewed >= cutoff)
            ).where(_readable(access), KnowledgeItem.status == "active")
        )
    ).one()
    per_responsibility = dict(
        (
            await access.session.execute(
                select(KnowledgeItem.responsibility_id, func.count())
                .where(_readable(access), KnowledgeItem.status == "active")
                .group_by(KnowledgeItem.responsibility_id)
            )
        ).all()
    )
    missing = [
        KnowledgeCoverageView(
            responsibility_id=r.id,
            responsibility_name=r.name,
            criticality=r.criticality,
            items=0,
            stale=0,
        )
        for r in await access.session.scalars(
            select(Responsibility)
            .where(
                visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
                Responsibility.status == "active",
            )
            .order_by(Responsibility.name)
        )
        if r.id not in per_responsibility
    ]
    order = {"critical": 0, "high": 1, "standard": 2, "low": 3}
    return KnowledgeOverviewView(
        results=results,
        missing=sorted(missing, key=lambda m: (order[m.criticality], m.responsibility_name)),
        stale_items=counts[0],
        fresh_items=counts[1],
    )


# ---------------------------------------------------------------- case handover


async def case_knowledge(
    access: WorkspaceAccess, case_id: uuid.UUID
) -> list[CaseKnowledgeItemView]:
    authorize(access, Permission.CASE_READ)
    case = await access.session.scalar(
        select(ContinuityCase).where(
            ContinuityCase.id == case_id,
            visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
        )
    )
    if case is None:
        raise ApiError(404, "case_not_found", "Case not found.")
    scope = list(
        await access.session.execute(
            select(CaseScopeItem.responsibility_id, Responsibility.name)
            .join(Responsibility, Responsibility.id == CaseScopeItem.responsibility_id)
            .where(CaseScopeItem.case_id == case.id)
            .order_by(CaseScopeItem.created_at)
        )
    )
    ids = [rid for rid, _ in scope]
    knowledge = await _items(
        access,
        KnowledgeItem.responsibility_id.in_(ids),
        KnowledgeItem.status == "active",
        limit=500,
    )
    names = await _names(access)
    records = list(
        await access.session.scalars(
            select(CaseKnowledge)
            .where(CaseKnowledge.case_id == case.id)
            .order_by(CaseKnowledge.recorded_at)
        )
    )
    return [
        CaseKnowledgeItemView(
            responsibility_id=rid,
            responsibility_name=name,
            knowledge=[k for k in knowledge if k.responsibility_id == rid],
            records=[
                HandoverRecordView(
                    id=r.id,
                    knowledge_item_id=r.knowledge_item_id,
                    outcome=r.outcome,
                    note=r.note,
                    recorded_by_name=names.get(r.recorded_by, "Former member"),
                    recorded_at=r.recorded_at,
                )
                for r in records
                if r.responsibility_id == rid
            ],
        )
        for rid, name in scope
    ]


async def record_handover(
    access: WorkspaceAccess, case_id: uuid.UUID, data: HandoverIn
) -> list[CaseKnowledgeItemView]:
    authorize(access, Permission.CASE_MANAGE)
    case = await access.session.scalar(
        select(ContinuityCase)
        .where(
            ContinuityCase.id == case_id,
            visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
        )
        .with_for_update()
    )
    if case is None:
        raise ApiError(404, "case_not_found", "Case not found.")
    if case.status not in ("draft", "planning", "executing"):
        raise ApiError(409, "invalid_state", "The case is closed.")
    in_scope = await access.session.scalar(
        select(CaseScopeItem.id).where(
            CaseScopeItem.case_id == case_id,
            CaseScopeItem.responsibility_id == data.responsibility_id,
        )
    )
    if in_scope is None:
        raise ApiError(422, "not_in_scope", "That responsibility is not part of this case.")
    if data.outcome == "handed_over":
        if data.knowledge_item_id is None:
            raise ApiError(422, "knowledge_required", "Choose the knowledge that was handed over.")
        item = await access.session.scalar(
            select(KnowledgeItem.id).where(
                KnowledgeItem.id == data.knowledge_item_id,
                KnowledgeItem.responsibility_id == data.responsibility_id,
                _readable(access),
            )
        )
        if item is None:
            raise ApiError(
                422, "knowledge_not_found", "That knowledge is not on this responsibility."
            )
        duplicate = await access.session.scalar(
            select(CaseKnowledge.id).where(
                CaseKnowledge.case_id == case_id,
                CaseKnowledge.knowledge_item_id == data.knowledge_item_id,
            )
        )
        if duplicate is not None:
            raise ApiError(409, "already_recorded", "Already recorded as handed over.")
    elif not data.note:
        raise ApiError(422, "note_required", "Describe the knowledge that is missing.")
    record = CaseKnowledge(
        tenant_id=access.tenant_id,
        case_id=case_id,
        responsibility_id=data.responsibility_id,
        knowledge_item_id=data.knowledge_item_id if data.outcome == "handed_over" else None,
        outcome=data.outcome,
        note=data.note or None,
        recorded_by=access.user_id,
    )
    access.session.add(record)
    await access.session.flush()
    catalog.record_audit(
        access,
        f"case.knowledge_{data.outcome}",
        "continuity_case",
        case_id,
        responsibility_id=str(data.responsibility_id),
        knowledge_id=str(data.knowledge_item_id) if data.knowledge_item_id else None,
    )
    case.updated_at = func.now()
    return await case_knowledge(access, case_id)
