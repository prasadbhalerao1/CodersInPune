"""Knowledge governance: disputes, feedback, version history and comparison, duplicate and
conflict detection, and a portable Markdown handover export.

Everything reads through `knowledge.readable` (and the responsibility row policy), so a
person never sees, compares or exports knowledge they couldn't open directly. The export
lists what it left out and why, plus a manifest of the exact source versions it used.
"""

import difflib
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select

from relay.catalog import knowledge
from relay.catalog import service as catalog
from relay.catalog.models import KnowledgeFeedback, KnowledgeItem, KnowledgeVersion, Responsibility
from relay.continuity import service as cases
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize
from relay.shared.api_types import LongText, StrictInput
from relay.shared.errors import ApiError


class DisputeIn(StrictInput):
    reason: LongText


class FeedbackIn(StrictInput):
    kind: Literal["stale", "authoritative"]
    note: LongText | None = None


class VersionView(BaseModel):
    version: int
    kind: str
    title: str
    body: str | None
    url: str | None
    change_note: str | None
    changed_by_name: str
    changed_at: datetime


class FeedbackView(BaseModel):
    kind: str
    note: str | None
    user_name: str
    created_at: datetime


class RelatedView(BaseModel):
    id: uuid.UUID
    title: str
    responsibility_name: str
    state: str
    updated_at: datetime
    last_reviewed_at: datetime | None


class GovernanceView(BaseModel):
    versions: list[VersionView]
    feedback: list[FeedbackView]
    # Same subject recorded twice (merge or archive one).
    duplicates: list[RelatedView]
    # Same responsibility and subject, different content: a person decides which holds.
    conflicts: list[RelatedView]
    superseded_by: RelatedView | None


class CompareView(BaseModel):
    from_version: int
    to_version: int
    title_changed: bool
    diff: list[str]


async def _item(
    access: WorkspaceAccess, item_id: uuid.UUID, *, lock: bool = False
) -> KnowledgeItem:
    stmt = select(KnowledgeItem).where(KnowledgeItem.id == item_id, knowledge.readable(access))
    item = await access.session.scalar(stmt.with_for_update() if lock else stmt)
    if item is None:
        raise ApiError(404, "knowledge_not_found", "Knowledge not found.")
    return item


async def dispute(
    access: WorkspaceAccess, item_id: uuid.UUID, data: DisputeIn
) -> knowledge.KnowledgeView:
    """Anyone who can read it may dispute it; the content and history stay untouched. The
    steward sees it in their My Work review queue."""
    authorize(access, Permission.KNOWLEDGE_WRITE)
    item = await _item(access, item_id, lock=True)
    if item.status != "active":
        raise ApiError(409, "invalid_state", "Archived knowledge can't be disputed.")
    item.review_state = "disputed"
    item.dispute_reason, item.disputed_by, item.disputed_at = (
        data.reason,
        access.user_id,
        func.now(),
    )
    catalog.record_audit(
        access,
        "knowledge.disputed",
        "responsibility",
        item.responsibility_id,
        knowledge_id=str(item.id),
    )
    await access.session.flush()
    return (await knowledge._items(access, KnowledgeItem.id == item.id))[0]


async def feedback(access: WorkspaceAccess, item_id: uuid.UUID, data: FeedbackIn) -> GovernanceView:
    authorize(access, Permission.KNOWLEDGE_WRITE)
    item = await _item(access, item_id)
    access.session.add(
        KnowledgeFeedback(
            tenant_id=access.tenant_id,
            knowledge_item_id=item.id,
            kind=data.kind,
            note=data.note or None,
            user_id=access.user_id,
        )
    )
    catalog.record_audit(
        access,
        f"knowledge.flagged_{data.kind}",
        "responsibility",
        item.responsibility_id,
        knowledge_id=str(item.id),
    )
    await access.session.flush()
    return await governance(access, item_id)


def _related(
    item: KnowledgeItem, name: str, cutoff: datetime, withdrawn: bool = False
) -> RelatedView:
    return RelatedView(
        id=item.id,
        title=item.title,
        responsibility_name=name,
        state=knowledge.state_of(item, cutoff, inaccessible=withdrawn),
        updated_at=item.updated_at,
        last_reviewed_at=item.last_reviewed_at,
    )


async def governance(access: WorkspaceAccess, item_id: uuid.UUID) -> GovernanceView:
    authorize(access, Permission.RESPONSIBILITY_READ)
    item = await _item(access, item_id)
    names = await knowledge._names(access)
    cutoff = await knowledge.review_cutoff(access)
    versions = await access.session.scalars(
        select(KnowledgeVersion)
        .where(KnowledgeVersion.knowledge_item_id == item_id)
        .order_by(KnowledgeVersion.version.desc())
    )
    notes = await access.session.scalars(
        select(KnowledgeFeedback)
        .where(KnowledgeFeedback.knowledge_item_id == item_id)
        .order_by(KnowledgeFeedback.created_at.desc())
        .limit(50)
    )
    # Similar subject: the other item's text matches this title (full-text), same workspace.
    query = func.plainto_tsquery("english", item.title)
    similar = (
        await access.session.execute(
            select(KnowledgeItem, Responsibility.name)
            .join(Responsibility, Responsibility.id == KnowledgeItem.responsibility_id)
            .where(
                knowledge.readable(access),
                KnowledgeItem.id != item.id,
                KnowledgeItem.status == "active",
                KnowledgeItem.search.op("@@")(query),
            )
            .order_by(func.ts_rank(KnowledgeItem.search, query).desc())
            .limit(10)
        )
    ).all()
    title = item.title.strip().lower()
    duplicates = [
        _related(other, name, cutoff)
        for other, name in similar
        if other.title.strip().lower() == title or (other.url and other.url == item.url)
    ]
    dup_ids = {d.id for d in duplicates}
    conflicts = [
        _related(other, name, cutoff)
        for other, name in similar
        if other.id not in dup_ids
        and other.responsibility_id == item.responsibility_id
        and other.kind == item.kind
        and (other.body or "") != (item.body or "")
        and other.superseded_by_id != item.id
        and item.superseded_by_id != other.id
    ]
    successor = None
    if item.superseded_by_id:
        row = (
            await access.session.execute(
                select(KnowledgeItem, Responsibility.name)
                .join(Responsibility, Responsibility.id == KnowledgeItem.responsibility_id)
                .where(KnowledgeItem.id == item.superseded_by_id, knowledge.readable(access))
            )
        ).first()
        successor = _related(row[0], row[1], cutoff) if row else None
    return GovernanceView(
        versions=[
            VersionView(
                version=v.version,
                kind=v.kind,
                title=v.title,
                body=v.body,
                url=v.url,
                change_note=v.change_note,
                changed_by_name=names.get(v.changed_by, "Former member"),
                changed_at=v.changed_at,
            )
            for v in versions
        ],
        feedback=[
            FeedbackView(
                kind=f.kind,
                note=f.note,
                user_name=names.get(f.user_id, "Former member"),
                created_at=f.created_at,
            )
            for f in notes
        ],
        duplicates=duplicates,
        conflicts=conflicts[:5],
        superseded_by=successor,
    )


async def compare(
    access: WorkspaceAccess, item_id: uuid.UUID, from_version: int, to_version: int
) -> CompareView:
    authorize(access, Permission.RESPONSIBILITY_READ)
    await _item(access, item_id)
    rows = {
        v.version: v
        for v in await access.session.scalars(
            select(KnowledgeVersion).where(
                KnowledgeVersion.knowledge_item_id == item_id,
                KnowledgeVersion.version.in_((from_version, to_version)),
            )
        )
    }
    if from_version not in rows or to_version not in rows:
        raise ApiError(404, "version_not_found", "That version doesn't exist.")
    a, b = rows[from_version], rows[to_version]

    def lines(v: KnowledgeVersion) -> list[str]:
        return [f"# {v.title}", *(v.body or "").splitlines(), *([v.url] if v.url else [])]

    return CompareView(
        from_version=from_version,
        to_version=to_version,
        title_changed=a.title != b.title,
        diff=list(
            difflib.unified_diff(
                lines(a), lines(b), f"v{from_version}", f"v{to_version}", lineterm="", n=2
            )
        ),
    )


# ---------------------------------------------------------------- Markdown export


async def export_case_markdown(access: WorkspaceAccess, case_id: uuid.UUID) -> str:
    """A portable handover pack for the viewer: what they may see, what was left out and
    why, and the exact source versions used. Never wider than the viewer's own access."""
    detail = await cases.get_case(access, case_id)
    cutoff = await knowledge.review_cutoff(access)
    visible_ids = [s.responsibility_id for s in detail.scope if not s.hidden]
    readable = (
        await access.session.execute(
            select(KnowledgeItem)
            .where(
                knowledge.readable(access),
                KnowledgeItem.responsibility_id.in_(visible_ids),
                KnowledgeItem.status == "active",
            )
            .order_by(KnowledgeItem.title)
        )
    ).scalars()
    by_responsibility: dict[uuid.UUID, list[KnowledgeItem]] = {}
    for item in readable:
        by_responsibility.setdefault(item.responsibility_id, []).append(item)
    # Items in scope the viewer can't read are counted, never named.
    total = await access.session.scalar(
        select(func.count()).where(
            KnowledgeItem.responsibility_id.in_(visible_ids), KnowledgeItem.status == "active"
        )
    )
    readable_count = sum(len(v) for v in by_responsibility.values())
    omissions: list[str] = []
    hidden_scope = sum(1 for s in detail.scope if s.hidden)
    if hidden_scope:
        omissions.append(f"{hidden_scope} restricted responsibility(ies) you can't see.")
    if (total or 0) > readable_count:
        omissions.append(
            f"{(total or 0) - readable_count} managers-only knowledge item(s) you can't see."
        )

    out = [
        f"# Handover: {detail.title}",
        "",
        f"- Case type: {detail.case_type.replace('_', ' ')} · status: {detail.status}",
        f"- Person: {detail.affected_person_name or '—'} · priority: {detail.priority}",
        f"- Ownership changes: {detail.starts_at.isoformat()}",
        "",
    ]
    manifest = []
    for scope in detail.scope:
        if scope.hidden:
            continue
        recipient = scope.recipient.name if scope.recipient else "not chosen"
        out += [
            f"## {scope.responsibility_name}",
            "",
            f"{scope.criticality} · {scope.role.replace('_', ' ')} · "
            f"{scope.current_owner_name or 'no current holder'} → {recipient}",
            "",
        ]
        if scope.handover_notes:
            out += ["**Handover notes**", "", scope.handover_notes, ""]
        items = by_responsibility.get(scope.responsibility_id, [])
        if not items:
            out += ["_Nothing written down for this responsibility._", ""]
        for item in items:
            state = knowledge.state_of(item, cutoff)
            if state in ("disputed", "expired"):
                omissions.append(f"“{item.title}” ({state}): left out until it is resolved.")
                continue
            out += [f"### {item.title}", "", f"_{item.kind.replace('_', ' ')} · {state}_", ""]
            if item.body:
                out += [item.body, ""]
            if item.url:
                out += [f"Source: {item.url}", ""]
            manifest.append(
                f"| {item.title} | v{item.version} | {item.origin} | "
                f"{item.updated_at.date().isoformat()} | {state} |"
            )
    out += ["## Omissions", ""]
    out += [f"- {o}" for o in omissions] or ["- None."]
    out += [
        "",
        "## Source versions",
        "",
        "| Item | Version | Source | Updated | State |",
        "| --- | --- | --- | --- | --- |",
        *manifest,
        "",
    ]
    catalog.record_audit(access, "case.exported", "continuity_case", case_id)
    return "\n".join(out)
