"""Responsibility knowledge: capture, review, freshness, search, and case handover.

Knowledge always belongs to a responsibility and keeps its author and source URL.
Freshness is derived from the last review: fresh within the workspace's review interval
(governance policy, default 90 days), stale after that, and a
responsibility with no active knowledge is "missing". Visibility "managers" limits an
item to people who manage responsibilities (owners/admins); everything else follows the
responsibility's normal read access. Search is PostgreSQL full-text search.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, StringConstraints
from sqlalchemy import ColumnElement, and_, case, func, select, true

from relay.catalog import service as catalog
from relay.catalog.models import (
    KnowledgeItem,
    KnowledgeVersion,
    OwnershipAssignment,
    Responsibility,
)
from relay.continuity.models import OPEN_STATUSES, CaseKnowledge, CaseScopeItem, ContinuityCase
from relay.governance import service as governance
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.notion.models import NotionPage
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.shared.api_types import LongText, Name, StrictInput
from relay.shared.errors import ApiError

Kind = Literal[
    "note",
    "link",
    "document",
    "procedure",
    "context",
    "adr",
    "faq",
    "postmortem",
    "escalation_contact",
    "onboarding_resource",
    "project_overview",
]
Visibility = Literal["workspace", "managers"]
Freshness = Literal["fresh", "stale"]
# Lifecycle shown to people: review_state is stored; the rest is derived.
State = Literal["draft", "verified", "disputed", "stale", "expired", "inaccessible", "archived"]
Body = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20000)]
Url = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000, pattern=r"^https?://\S+$")
]


class KnowledgeGovernance(StrictInput):
    """Fields shared by create and update: scope, validity and decision lineage."""

    steward_user_id: uuid.UUID | None = None
    valid_from: AwareDatetime | None = None
    valid_until: AwareDatetime | None = None
    applies_to: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = (
        None
    )
    decision_rationale: Body | None = None
    decision_approver: Name | None = None
    decided_at: AwareDatetime | None = None


class KnowledgeIn(KnowledgeGovernance):
    kind: Kind
    title: Name
    body: Body | None = None
    url: Url | None = None
    visibility: Visibility = "workspace"


class KnowledgeUpdate(KnowledgeGovernance):
    title: Name | None = None
    body: Body | None = None
    url: Url | None = None
    kind: Kind | None = None
    visibility: Visibility | None = None
    status: Literal["active", "archived"] | None = None
    superseded_by_id: uuid.UUID | None = None
    change_note: LongText | None = None


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
    state: State = "verified"
    review_state: str = "verified"
    version: int = 1
    steward_user_id: uuid.UUID | None = None
    steward_name: str | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    applies_to: str | None = None
    decision_rationale: str | None = None
    decision_approver: str | None = None
    decided_at: datetime | None = None
    superseded_by_id: uuid.UUID | None = None
    # A decision is current while it isn't superseded and hasn't expired.
    current: bool = True
    dispute_reason: str | None = None
    disputed_by_name: str | None = None
    disputed_at: datetime | None = None
    can_verify: bool = False


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


readable = _readable  # shared with global search: one visibility rule


async def _names(access: WorkspaceAccess) -> dict[uuid.UUID, str]:
    rows = await access.session.execute(
        select(Membership.user_id, Membership.display_name, Membership.email).where(
            visible(access, Permission.MEMBER_READ, Membership.tenant_id)
        )
    )
    return {user_id: name or email or "Member" for user_id, name, email in rows}


async def review_cutoff(access: WorkspaceAccess) -> datetime:
    policy = await governance.current(access.session)
    return _now() - timedelta(days=policy.knowledge_review_days)


def _freshness(item: KnowledgeItem, cutoff: datetime) -> Freshness:
    if item.origin != "person" and item.last_reviewed_at is None:
        return "stale"  # imported content is unreviewed until a person confirms it
    reviewed = item.last_reviewed_at or item.created_at
    return "fresh" if reviewed >= cutoff else "stale"


def state_of(item: KnowledgeItem, cutoff: datetime, *, inaccessible: bool = False) -> State:
    """Archived > inaccessible source > expired > disputed > draft > stale > verified."""
    if item.status == "archived":
        return "archived"
    if inaccessible:
        return "inaccessible"
    if item.valid_until is not None and item.valid_until <= _now():
        return "expired"
    if item.review_state in ("disputed", "draft"):
        return item.review_state  # type: ignore[return-value]
    return "stale" if _freshness(item, cutoff) == "stale" else "verified"


def can_verify(access: WorkspaceAccess, item: KnowledgeItem) -> bool:
    """The steward verifies; so can anyone with knowledge.verify (managers, stewards)."""
    return item.steward_user_id == access.user_id or role_allows(
        access.role, Permission.KNOWLEDGE_VERIFY
    )


def _view(
    access: WorkspaceAccess,
    item: KnowledgeItem,
    responsibility_name: str,
    names: dict[uuid.UUID, str],
    cutoff: datetime,
    inaccessible: bool = False,
) -> KnowledgeView:
    return KnowledgeView(
        state=state_of(item, cutoff, inaccessible=inaccessible),
        review_state=item.review_state,
        version=item.version,
        steward_user_id=item.steward_user_id,
        steward_name=names.get(item.steward_user_id) if item.steward_user_id else None,
        valid_from=item.valid_from,
        valid_until=item.valid_until,
        applies_to=item.applies_to,
        decision_rationale=item.decision_rationale,
        decision_approver=item.decision_approver,
        decided_at=item.decided_at,
        superseded_by_id=item.superseded_by_id,
        current=item.superseded_by_id is None
        and (item.valid_until is None or item.valid_until > _now()),
        dispute_reason=item.dispute_reason,
        disputed_by_name=names.get(item.disputed_by) if item.disputed_by else None,
        disputed_at=item.disputed_at,
        can_verify=can_verify(access, item),
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
        freshness=_freshness(item, cutoff),
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
    names, cutoff = await _names(access), await review_cutoff(access)
    # Imported pages whose source page was withdrawn can no longer be checked.
    withdrawn = set(
        await access.session.scalars(
            select(NotionPage.knowledge_item_id).where(
                NotionPage.knowledge_item_id.in_([i.id for i, _ in rows]),
                NotionPage.status != "active",
            )
        )
    )
    return [_view(access, item, name, names, cutoff, item.id in withdrawn) for item, name in rows]


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


def snapshot(access: WorkspaceAccess, item: KnowledgeItem, note: str | None) -> None:
    """Record the item's current content as an immutable version."""
    access.session.add(
        KnowledgeVersion(
            tenant_id=access.tenant_id,
            knowledge_item_id=item.id,
            version=item.version,
            kind=item.kind,
            title=item.title,
            body=item.body,
            url=item.url,
            change_note=note,
            changed_by=access.user_id,
        )
    )


async def _check_governance(
    access: WorkspaceAccess, changes: dict[str, object], item: KnowledgeItem | None = None
) -> None:
    steward = changes.get("steward_user_id")
    if steward is not None:
        found = await access.session.scalar(
            select(Membership.id).where(
                Membership.user_id == steward, Membership.status == "active"
            )
        )
        if found is None:
            raise ApiError(422, "not_a_member", "The steward must be an active member.")
    successor = changes.get("superseded_by_id")
    if successor is not None:
        if item is not None and successor == item.id:
            raise ApiError(422, "not_self", "An item can't supersede itself.")
        found = await access.session.scalar(
            select(KnowledgeItem.id).where(KnowledgeItem.id == successor, _readable(access))
        )
        if found is None:
            raise ApiError(422, "knowledge_not_found", "The superseding item doesn't exist.")


async def add_knowledge(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, data: KnowledgeIn
) -> KnowledgeView:
    authorize(access, Permission.KNOWLEDGE_WRITE)
    if data.visibility == "managers":
        authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await catalog.require_active_responsibility(access, responsibility_id)
    if not data.body and not data.url:
        raise ApiError(422, "content_required", "Add a link or some content.")
    await _check_governance(access, data.model_dump(exclude_unset=True))
    verifier = role_allows(access.role, Permission.KNOWLEDGE_VERIFY)
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
        # Verifiers' own knowledge is verified; everyone else's waits for the steward.
        review_state="verified" if verifier else "draft",
        steward_user_id=data.steward_user_id,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        applies_to=data.applies_to or None,
        decision_rationale=data.decision_rationale or None,
        decision_approver=data.decision_approver or None,
        decided_at=data.decided_at,
    )
    access.session.add(item)
    await access.session.flush()
    snapshot(access, item, None)
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
    if item.origin != "person" and {"title", "body", "url", "kind"} & changes.keys():
        raise ApiError(409, "edit_in_source", "This page is synced from Notion; edit it there.")
    if changes.get("visibility") == "managers":
        authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await _check_governance(access, changes, item)
    change_note = changes.pop("change_note", None)
    for field, value in changes.items():
        setattr(
            item,
            field,
            (value or None)
            if field in ("body", "url", "applies_to", "decision_rationale")
            else value,
        )
    if not item.body and not item.url:
        raise ApiError(422, "content_required", "Keep a link or some content.")
    if (
        item.valid_until is not None
        and item.valid_from is not None
        and item.valid_until <= item.valid_from
    ):
        raise ApiError(422, "invalid_validity", "Valid until must be after valid from.")
    item.updated_at = func.now()
    if {"title", "body", "url", "kind"} & changes.keys():
        # A new immutable version; content changes need the steward's verification again.
        item.version += 1
        item.last_reviewed_by, item.last_reviewed_at = access.user_id, _now()
        if not can_verify(access, item):
            item.review_state = "draft"
        snapshot(access, item, change_note)
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
    if item.review_state != "verified" and not can_verify(access, item):
        raise ApiError(
            403, "steward_required", "Only the steward or a manager can verify this knowledge."
        )
    item.last_reviewed_by, item.last_reviewed_at = access.user_id, _now()
    item.review_state = "verified"
    item.dispute_reason = item.disputed_by = item.disputed_at = None
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


async def responsibility_knowledge_by_author(
    access: WorkspaceAccess, user_id: uuid.UUID
) -> list[KnowledgeView]:
    """Active knowledge a member wrote (for their own review queue in My Work)."""
    authorize(access, Permission.RESPONSIBILITY_READ)
    return await _items(
        access, KnowledgeItem.author_user_id == user_id, KnowledgeItem.status == "active"
    )


async def knowledge_overview(
    access: WorkspaceAccess,
    *,
    q: str | None = None,
    freshness: Freshness | None = None,
    origin: Literal["person", "notion", "ai"] | None = None,
    steward_user_id: uuid.UUID | None = None,
    review_state: Literal["draft", "verified", "disputed"] | None = None,
    visibility: Visibility | None = None,
    team_id: uuid.UUID | None = None,
    kind: Kind | None = None,
) -> KnowledgeOverviewView:
    authorize(access, Permission.RESPONSIBILITY_READ)
    conditions: list[ColumnElement[bool]] = [KnowledgeItem.status == "active"]
    if origin:
        conditions.append(KnowledgeItem.origin == origin)
    if steward_user_id:
        conditions.append(KnowledgeItem.steward_user_id == steward_user_id)
    if review_state:
        conditions.append(KnowledgeItem.review_state == review_state)
    if visibility:
        conditions.append(KnowledgeItem.visibility == visibility)
    if kind:
        conditions.append(KnowledgeItem.kind == kind)
    if team_id:
        # Knowledge of responsibilities the team currently owns.
        conditions.append(
            KnowledgeItem.responsibility_id.in_(
                select(OwnershipAssignment.responsibility_id).where(
                    OwnershipAssignment.team_id == team_id,
                    catalog.active_at(_now()),
                )
            )
        )
    if q:
        conditions.append(KnowledgeItem.search.op("@@")(func.websearch_to_tsquery("english", q)))
    cutoff = await review_cutoff(access)
    reviewed = func.coalesce(
        KnowledgeItem.last_reviewed_at,
        case((KnowledgeItem.origin == "person", KnowledgeItem.created_at)),
        func.to_timestamp(0),
    )
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
    if case.status not in OPEN_STATUSES:
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


async def stewarded_for_review(access: WorkspaceAccess) -> list[KnowledgeView]:
    """Drafts and disputed items the signed-in member stewards."""
    return await _items(
        access,
        KnowledgeItem.steward_user_id == access.user_id,
        KnowledgeItem.status == "active",
        KnowledgeItem.review_state.in_(("draft", "disputed")),
    )


async def get_knowledge(access: WorkspaceAccess, item_id: uuid.UUID) -> KnowledgeView:
    authorize(access, Permission.RESPONSIBILITY_READ)
    found = await _items(access, KnowledgeItem.id == item_id, limit=1)
    if not found:
        raise ApiError(404, "knowledge_not_found", "Knowledge not found.")
    return found[0]
