"""Case consent and privacy review: which sources a case uses, what it will share and with
whom, and the outgoing owner's review of it.

- A manager chooses the connected sources (Relay's own records are always in scope) and
  confirms the data-use notice, then prepares the review: one item per responsibility
  handover, knowledge item and connected source.
- The outgoing owner (matched by email) or a manager confirms, corrects or disputes each
  item, with a reason. Nothing is deleted: a disputed knowledge item is narrowed to
  managers in this case's evidence (so AI outputs and capsules for members leave it out),
  and every decision is kept with who made it and when.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from relay.catalog.knowledge import readable
from relay.catalog.models import KnowledgeItem
from relay.continuity import service as cases
from relay.continuity.impact import source_status
from relay.continuity.models import OPEN_STATUSES, CaseReviewItem, ContinuityCase
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, role_allows, visible
from relay.shared.api_types import LongText, StrictInput
from relay.shared.errors import ApiError

Source = Literal["github", "linear", "notion"]
NOTICE = (
    "Relay uses what is recorded about the responsibilities in this case (ownership, tasks, "
    "notes and knowledge) and, for the sources you keep selected, linked GitHub pull "
    "requests and issues, Linear issues and Notion pages. It never reads private messages "
    "or personal files. AI suggestions only use evidence the case may share, and every "
    "suggestion cites its source. The person handing over can review, correct or dispute "
    "what will be shared before anyone else sees it."
)
AUDIENCE = {
    "case": "People in this case: the recipients, coordinator, accountable manager and approvers",
    "workspace": "Everyone in the workspace",
    "managers": "Workspace owners and admins only",
}


class PrivacyIn(StrictInput):
    excluded_sources: list[Source] = []
    acknowledge_notice: bool = False


class ReviewDecisionIn(StrictInput):
    decision: Literal["confirmed", "corrected", "disputed"]
    note: LongText | None = None


class ReviewItemView(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    case_title: str | None = None
    subject_type: str
    subject_id: str
    summary: str
    audience: str
    audience_label: str
    decision: str
    note: str | None
    decided_by_name: str | None
    decided_at: datetime | None
    can_decide: bool


class PrivacyView(BaseModel):
    notice: str
    notice_acknowledged_at: datetime | None
    excluded_sources: list[str]
    sources: list[dict[str, str]]
    reviewer_name: str | None
    items: list[ReviewItemView]
    pending: int
    can_manage: bool


async def _reviewer(access: WorkspaceAccess, case: ContinuityCase) -> uuid.UUID | None:
    """The person handing over: the affected person, except for onboarding (the joiner)."""
    return None if case.case_type == "onboarding" else case.affected_person_id


async def _views(
    access: WorkspaceAccess, rows: list[CaseReviewItem], titles: dict[uuid.UUID, str] | None = None
) -> list[ReviewItemView]:
    names = await cases._member_names(access)
    mine = await cases.my_person_ids(access)
    manager = role_allows(access.role, Permission.CASE_MANAGE)
    return [
        ReviewItemView(
            id=r.id,
            case_id=r.case_id,
            case_title=titles.get(r.case_id) if titles else None,
            subject_type=r.subject_type,
            subject_id=r.subject_id,
            summary=r.summary,
            audience=r.audience,
            audience_label=AUDIENCE[r.audience],
            decision=r.decision,
            note=r.note,
            decided_by_name=names.get(r.decided_by) if r.decided_by else None,
            decided_at=r.decided_at,
            can_decide=manager
            or (r.reviewer_person_id is not None and r.reviewer_person_id in mine),
        )
        for r in rows
    ]


async def privacy(access: WorkspaceAccess, case_id: uuid.UUID) -> PrivacyView:
    authorize(access, Permission.CASE_READ)
    case = await cases._load(access, case_id)
    rows = list(
        await access.session.scalars(
            select(CaseReviewItem)
            .where(CaseReviewItem.case_id == case_id)
            .order_by(CaseReviewItem.subject_type, CaseReviewItem.created_at)
        )
    )
    reviewer = await _reviewer(access, case)
    detail = await cases.get_case(access, case_id)
    return PrivacyView(
        notice=NOTICE,
        notice_acknowledged_at=case.privacy_notice_at,
        excluded_sources=case.excluded_sources,
        sources=[
            {"source": s.source, "state": s.state}
            for s in await source_status(access)
            if s.state != "not_connected"
        ],
        reviewer_name=detail.affected_person_name if reviewer else None,
        items=await _views(access, rows),
        pending=sum(1 for r in rows if r.decision == "pending"),
        can_manage=role_allows(access.role, Permission.CASE_MANAGE)
        and case.status in OPEN_STATUSES,
    )


async def configure(access: WorkspaceAccess, case_id: uuid.UUID, data: PrivacyIn) -> PrivacyView:
    case = await cases._for_change(access, case_id, cases.OPEN)
    case.excluded_sources = sorted(set(data.excluded_sources))
    if data.acknowledge_notice and case.privacy_notice_at is None:
        case.privacy_notice_at, case.privacy_notice_by = func.now(), access.user_id
    cases._record(access, case, "case.privacy_configured", excluded=",".join(case.excluded_sources))
    await access.session.flush()
    await prepare(access, case)
    return await privacy(access, case_id)


async def prepare(access: WorkspaceAccess, case: ContinuityCase) -> None:
    """Create review items for what the case will share (idempotent: existing decisions
    are kept; new scope or knowledge gets a new pending item)."""
    detail = await cases.get_case(access, case.id)
    reviewer = await _reviewer(access, case)
    rows: list[dict[str, object]] = []

    def add(subject_type: str, subject_id: str, summary: str, audience: str) -> None:
        rows.append(
            {
                "tenant_id": access.tenant_id,
                "case_id": case.id,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "summary": summary[:1000],
                "audience": audience,
                "reviewer_person_id": reviewer,
                "created_by": access.user_id,
            }
        )

    visible_ids = []
    for s in detail.scope:
        if s.hidden:
            continue
        visible_ids.append(s.responsibility_id)
        notes = f" Notes: {s.handover_notes}" if s.handover_notes else ""
        to = s.recipient.name if s.recipient else "a recipient not yet chosen"
        add(
            "responsibility",
            str(s.responsibility_id),
            f"“{s.responsibility_name}” ({s.role.replace('_', ' ')}) is handed to {to}.{notes}",
            "case",
        )
    for k in await access.session.scalars(
        select(KnowledgeItem).where(
            readable(access),
            KnowledgeItem.responsibility_id.in_(visible_ids),
            KnowledgeItem.status == "active",
        )
    ):
        add(
            "knowledge",
            str(k.id),
            f"Knowledge “{k.title}” ({k.kind.replace('_', ' ')}) is included in the handover.",
            "managers" if k.visibility == "managers" else "case",
        )
    for src in await source_status(access):
        if src.state == "not_connected" or src.source.lower() in case.excluded_sources:
            continue
        add(
            "source",
            src.source.lower(),
            f"{src.source} items linked to the responsibilities in scope are used as evidence.",
            "case",
        )
    if rows:
        await access.session.execute(
            insert(CaseReviewItem)
            .values(rows)
            .on_conflict_do_nothing(
                index_elements=["tenant_id", "case_id", "subject_type", "subject_id"]
            )
        )


async def decide(
    access: WorkspaceAccess, item_id: uuid.UUID, data: ReviewDecisionIn
) -> ReviewItemView:
    authorize(access, Permission.CASE_READ)
    item = await access.session.scalar(
        select(CaseReviewItem)
        .where(
            CaseReviewItem.id == item_id,
            visible(access, Permission.CASE_READ, CaseReviewItem.tenant_id),
        )
        .with_for_update()
    )
    if item is None:
        raise ApiError(404, "review_item_not_found", "Review item not found.")
    case = await cases._load(access, item.case_id, lock=True)
    if case.status not in OPEN_STATUSES:
        raise ApiError(409, "invalid_state", "The case is closed.")
    reviewer = item.reviewer_person_id is not None and item.reviewer_person_id in (
        await cases.my_person_ids(access)
    )
    if not reviewer:
        authorize(access, Permission.CASE_MANAGE)
    if data.decision != "confirmed" and not data.note:
        raise ApiError(422, "reason_required", "Say what should change or why you dispute it.")
    item.decision, item.note = data.decision, data.note or None
    item.decided_by, item.decided_at = access.user_id, func.now()
    cases._record(
        access, case, "case.review_decided", subject_type=item.subject_type, decision=data.decision
    )
    await access.session.flush()
    await access.session.refresh(item)
    return (await _views(access, [item]))[0]


async def inbox(access: WorkspaceAccess) -> list[ReviewItemView]:
    """Pending review items addressed to the signed-in member as the outgoing owner."""
    authorize(access, Permission.CASE_READ)
    mine = await cases.my_person_ids(access)
    if not mine:
        return []
    rows = (
        await access.session.execute(
            select(CaseReviewItem, ContinuityCase.title)
            .join(ContinuityCase, ContinuityCase.id == CaseReviewItem.case_id)
            .where(
                visible(access, Permission.CASE_READ, CaseReviewItem.tenant_id),
                CaseReviewItem.reviewer_person_id.in_(mine),
                CaseReviewItem.decision == "pending",
                ContinuityCase.status.in_(OPEN_STATUSES),
            )
            .order_by(CaseReviewItem.created_at)
        )
    ).all()
    return await _views(access, [r for r, _ in rows], {r.case_id: t for r, t in rows})


async def narrowed_knowledge(session: AsyncSession, case_id: uuid.UUID) -> set[str]:
    """Knowledge the outgoing owner disputed for this case: shared with managers only."""
    return set(
        await session.scalars(
            select(CaseReviewItem.subject_id).where(
                CaseReviewItem.case_id == case_id,
                CaseReviewItem.subject_type == "knowledge",
                CaseReviewItem.decision == "disputed",
            )
        )
    )
