"""Assets: the repositories, services, vendors and processes responsibilities steward.

Assets carry no ownership. "Who looks after the payments API?" is answered through the
responsibilities linked to it, so ownership history, risks and cases stay in one place.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from relay.catalog import service as catalog
from relay.catalog.knowledge import readable
from relay.catalog.models import (
    Asset,
    AssetLink,
    KnowledgeItem,
    OwnershipAssignment,
    Responsibility,
    ResponsibilityAsset,
    ResponsibilityDependency,
)
from relay.continuity.models import CaseTask, ContinuityCase
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible
from relay.shared import pagination
from relay.shared.api_types import LongText, Name, StrictInput, blank_to_none
from relay.shared.errors import ApiError

AssetType = Literal[
    "repository",
    "service",
    "project",
    "process",
    "vendor",
    "document_collection",
    "customer_account",
    "infrastructure",
    "other",
]
AssetStatus = Literal["active", "archived"]
Lifecycle = Literal["planned", "active", "deprecated", "retired"]
Criticality = Literal["critical", "high", "standard", "low"]
ExternalSource = Literal["github", "linear", "notion", "manual"]
Tag = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
# Typed metadata: the fields each asset type may carry (values are short strings).
METADATA_FIELDS: dict[str, tuple[str, ...]] = {
    "repository": ("default_branch", "language", "deploy_target"),
    "service": ("environment", "runbook_url", "on_call", "slo"),
    "project": ("phase", "target_date", "sponsor"),
    "process": ("frequency", "system_of_record"),
    "vendor": ("contract_renewal", "account_manager", "support_contact", "spend_tier"),
    "document_collection": ("location",),
    "customer_account": ("tier", "renewal_date", "region", "account_owner"),
    "infrastructure": ("provider", "region", "environment", "cost_center"),
    "other": (),
}
MetaValue = Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)]
Relationship = Literal["stewards", "uses"]
Url = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000, pattern=r"^https?://\S+$")
]


class AssetIn(StrictInput):
    name: Name
    asset_type: AssetType
    description: LongText | None = None
    url: Url | None = None
    criticality: Criticality | None = None
    tags: Annotated[list[Tag], Field(max_length=20)] = []
    lifecycle: Lifecycle = "active"
    external_source: ExternalSource | None = None
    external_id: Annotated[str, StringConstraints(max_length=200)] | None = None
    metadata: dict[str, MetaValue] = {}


class AssetUpdate(StrictInput):
    name: Name | None = None
    asset_type: AssetType | None = None
    description: LongText | None = None
    url: Url | None = None
    status: AssetStatus | None = None
    criticality: Criticality | None = None
    tags: Annotated[list[Tag], Field(max_length=20)] | None = None
    lifecycle: Lifecycle | None = None
    external_source: ExternalSource | None = None
    external_id: Annotated[str, StringConstraints(max_length=200)] | None = None
    metadata: dict[str, MetaValue] | None = None
    source_state: Literal["available", "unavailable"] | None = None


class AssetTargetIn(StrictInput):
    knowledge_item_id: uuid.UUID | None = None
    case_id: uuid.UUID | None = None
    task_id: uuid.UUID | None = None


class AssetLinkIn(StrictInput):
    asset_id: uuid.UUID
    relationship: Relationship = "stewards"


class AssetSummary(BaseModel):
    id: uuid.UUID
    name: str
    asset_type: str
    description: str | None
    url: str | None
    status: str
    responsibility_count: int
    updated_at: datetime
    criticality: str | None = None
    tags: list[str] = []
    lifecycle: str = "active"
    external_source: str | None = None
    external_id: str | None = None
    source_state: str = "available"
    stewarded: bool = True


class AssetResponsibilityView(BaseModel):
    id: uuid.UUID
    name: str
    criticality: str
    relationship: str
    primary_owner: catalog.AssigneeView | None


class AssetLinkView(BaseModel):
    id: uuid.UUID
    kind: Literal["knowledge", "case", "task"]
    target_id: uuid.UUID
    case_id: uuid.UUID | None
    title: str
    status: str


class AssetDetail(AssetSummary):
    created_at: datetime
    responsibilities: list[AssetResponsibilityView]
    metadata: dict[str, str] = {}
    metadata_fields: list[str] = []
    links: list[AssetLinkView] = []
    # Responsibilities that depend on this asset (beyond stewarding it).
    dependents: list[AssetResponsibilityView] = []


def _pattern(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def _get(access: WorkspaceAccess, asset_id: uuid.UUID, *, lock: bool = False) -> Asset:
    stmt = select(Asset).where(
        Asset.id == asset_id, visible(access, Permission.RESPONSIBILITY_READ, Asset.tenant_id)
    )
    asset = await access.session.scalar(stmt.with_for_update() if lock else stmt)
    if asset is None:
        raise ApiError(404, "asset_not_found", "Asset not found.")
    return asset


async def _link_counts(
    access: WorkspaceAccess, ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, int]]:
    """Per asset: (linked active responsibilities, of which stewarding)."""
    rows = await access.session.execute(
        select(
            ResponsibilityAsset.asset_id,
            func.count(),
            func.count().filter(ResponsibilityAsset.relationship == "stewards"),
        )
        .join(Responsibility, Responsibility.id == ResponsibilityAsset.responsibility_id)
        .where(ResponsibilityAsset.asset_id.in_(ids), Responsibility.status == "active")
        .group_by(ResponsibilityAsset.asset_id)
    )
    return {key: (total, stewards) for key, total, stewards in rows}


def _clean_metadata(asset_type: str, metadata: dict[str, str]) -> dict[str, str]:
    allowed = METADATA_FIELDS.get(asset_type, ())
    unknown = set(metadata) - set(allowed)
    if unknown:
        raise ApiError(
            422,
            "unknown_metadata",
            f"{asset_type.replace('_', ' ').capitalize()} assets don't have: "
            + ", ".join(sorted(unknown)),
        )
    return {k: v for k, v in metadata.items() if v}


def _summary(a: Asset, counts: tuple[int, int]) -> AssetSummary:
    return AssetSummary(
        criticality=a.criticality,
        tags=a.tags,
        lifecycle=a.lifecycle,
        external_source=a.external_source,
        external_id=a.external_id,
        source_state=a.source_state,
        stewarded=counts[1] > 0,
        id=a.id,
        name=a.name,
        asset_type=a.asset_type,
        description=a.description,
        url=a.url,
        status=a.status,
        responsibility_count=counts[0],
        updated_at=a.updated_at,
    )


async def list_assets(
    access: WorkspaceAccess,
    *,
    q: str | None = None,
    asset_type: AssetType | None = None,
    status: AssetStatus | None = "active",
    tag: str | None = None,
    lifecycle: Lifecycle | None = None,
    criticality: Criticality | None = None,
    stewarded: bool | None = None,
    after: str | None = None,
    limit: int = pagination.MAX_PAGE,
) -> tuple[list[AssetSummary], str | None]:
    authorize(access, Permission.RESPONSIBILITY_READ)
    stmt = select(Asset).where(visible(access, Permission.RESPONSIBILITY_READ, Asset.tenant_id))
    keyset = pagination.after_key((Asset.name, Asset.id), after, (str, uuid.UUID))
    if keyset is not None:
        stmt = stmt.where(keyset)
    if status:
        stmt = stmt.where(Asset.status == status)
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
    if tag:
        stmt = stmt.where(Asset.tags.contains([tag]))
    if lifecycle:
        stmt = stmt.where(Asset.lifecycle == lifecycle)
    if criticality:
        stmt = stmt.where(Asset.criticality == criticality)
    if q:
        stmt = stmt.where(or_(Asset.name.ilike(_pattern(q)), Asset.description.ilike(_pattern(q))))
    assets, next_cursor = pagination.split(
        list(await access.session.scalars(stmt.order_by(Asset.name, Asset.id).limit(limit + 1))),
        limit,
        lambda a: (a.name, a.id),
    )
    counts = await _link_counts(access, [a.id for a in assets])
    summaries = [_summary(a, counts.get(a.id, (0, 0))) for a in assets]
    if stewarded is not None:
        summaries = [a for a in summaries if a.stewarded == stewarded]
    return summaries, next_cursor


async def get_asset(access: WorkspaceAccess, asset_id: uuid.UUID) -> AssetDetail:
    authorize(access, Permission.RESPONSIBILITY_READ)
    await access.session.flush()
    asset = await _get(access, asset_id)
    await access.session.refresh(asset)
    rows = (
        await access.session.execute(
            select(Responsibility, ResponsibilityAsset.relationship)
            .join(ResponsibilityAsset, ResponsibilityAsset.responsibility_id == Responsibility.id)
            .where(
                ResponsibilityAsset.asset_id == asset_id,
                visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
                Responsibility.status == "active",
            )
            .order_by(Responsibility.name)
        )
    ).all()
    primaries = list(
        await access.session.scalars(
            select(OwnershipAssignment).where(
                OwnershipAssignment.responsibility_id.in_([r.id for r, _ in rows]),
                OwnershipAssignment.role == "primary",
                catalog.active_at(catalog.utcnow()),
            )
        )
    )
    assignees = await catalog.assignee_views(access.session, primaries)
    primary_of = {a.responsibility_id: assignees[a.person_id or a.team_id] for a in primaries}  # type: ignore[index]
    stewards = sum(1 for _, rel in rows if rel == "stewards")
    return AssetDetail(
        **_summary(asset, (len(rows), stewards)).model_dump(),
        metadata=asset.meta,
        metadata_fields=list(METADATA_FIELDS.get(asset.asset_type, ())),
        links=await _links(access, asset_id),
        dependents=await _dependents(access, asset_id, primary_of),
        created_at=asset.created_at,
        responsibilities=[
            AssetResponsibilityView(
                id=r.id,
                name=r.name,
                criticality=r.criticality,
                relationship=relationship,
                primary_owner=primary_of.get(r.id),
            )
            for r, relationship in rows
        ],
    )


async def create_asset(access: WorkspaceAccess, data: AssetIn) -> AssetDetail:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    asset = Asset(
        id=uuid.uuid7(),
        tenant_id=access.tenant_id,
        name=data.name,
        asset_type=data.asset_type,
        description=blank_to_none(data.description),
        url=blank_to_none(data.url),
        criticality=data.criticality,
        tags=sorted(set(data.tags)),
        lifecycle=data.lifecycle,
        external_source=data.external_source,
        external_id=blank_to_none(data.external_id),
        meta=_clean_metadata(data.asset_type, data.metadata),
        created_by=access.user_id,
    )
    access.session.add(asset)
    await access.session.flush()
    catalog.record_audit(access, "asset.created", "asset", asset.id, asset_type=data.asset_type)
    return await get_asset(access, asset.id)


async def update_asset(
    access: WorkspaceAccess, asset_id: uuid.UUID, data: AssetUpdate
) -> AssetDetail:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    asset = await _get(access, asset_id, lock=True)
    changes = data.model_dump(exclude_unset=True)
    if "metadata" in changes or "asset_type" in changes:
        asset.meta = _clean_metadata(
            changes.get("asset_type") or asset.asset_type, changes.pop("metadata", asset.meta) or {}
        )
    if "tags" in changes:
        changes["tags"] = sorted(set(changes["tags"] or []))
    for field, value in changes.items():
        setattr(
            asset,
            field,
            blank_to_none(value) if field in ("description", "url", "external_id") else value,
        )
    asset.updated_at = func.now()
    action = {"archived": "asset.archived", "active": "asset.restored"}.get(
        changes.get("status", ""), "asset.updated"
    )
    catalog.record_audit(access, action, "asset", asset.id, fields=",".join(sorted(changes)))
    return await get_asset(access, asset_id)


async def link_asset(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, data: AssetLinkIn
) -> None:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await catalog.require_active_responsibility(access, responsibility_id)
    asset = await _get(access, data.asset_id)
    if asset.status != "active":
        raise ApiError(422, "asset_archived", "Archived assets cannot be linked.")
    created = await access.session.scalar(
        insert(ResponsibilityAsset)
        .values(
            tenant_id=access.tenant_id,
            responsibility_id=responsibility_id,
            asset_id=data.asset_id,
            relationship=data.relationship,
            created_by=access.user_id,
        )
        .on_conflict_do_nothing()
        .returning(ResponsibilityAsset.id)
    )
    if created is None:
        raise ApiError(409, "asset_already_linked", "That asset is already linked.")
    catalog.record_audit(
        access,
        "responsibility.asset_linked",
        "responsibility",
        responsibility_id,
        asset_id=str(data.asset_id),
        relationship=data.relationship,
    )


async def unlink_asset(
    access: WorkspaceAccess, responsibility_id: uuid.UUID, asset_id: uuid.UUID
) -> None:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    await catalog.require_active_responsibility(access, responsibility_id)
    removed = await access.session.scalar(
        delete(ResponsibilityAsset)
        .where(
            ResponsibilityAsset.responsibility_id == responsibility_id,
            ResponsibilityAsset.asset_id == asset_id,
        )
        .returning(ResponsibilityAsset.id)
    )
    if removed is None:
        raise ApiError(404, "asset_not_linked", "That asset is not linked.")
    catalog.record_audit(
        access,
        "responsibility.asset_unlinked",
        "responsibility",
        responsibility_id,
        asset_id=str(asset_id),
    )


async def _links(access: WorkspaceAccess, asset_id: uuid.UUID) -> list[AssetLinkView]:
    rows = list(
        await access.session.scalars(
            select(AssetLink).where(AssetLink.asset_id == asset_id).order_by(AssetLink.created_at)
        )
    )
    links: list[AssetLinkView] = []
    knowledge = {
        k.id: k
        for k in await access.session.scalars(
            select(KnowledgeItem).where(
                KnowledgeItem.id.in_([r.knowledge_item_id for r in rows if r.knowledge_item_id]),
                readable(access),
            )
        )
    }
    cases = {
        c.id: c
        for c in await access.session.scalars(
            select(ContinuityCase).where(
                ContinuityCase.id.in_([r.case_id for r in rows if r.case_id]),
                visible(access, Permission.CASE_READ, ContinuityCase.tenant_id),
            )
        )
    }
    tasks = {
        t.id: t
        for t in await access.session.scalars(
            select(CaseTask).where(
                CaseTask.id.in_([r.task_id for r in rows if r.task_id]),
                visible(access, Permission.CASE_READ, CaseTask.tenant_id),
            )
        )
    }
    for r in rows:
        # Targets the viewer can't read are left out entirely.
        if r.knowledge_item_id and (k := knowledge.get(r.knowledge_item_id)):
            links.append(
                AssetLinkView(
                    id=r.id,
                    kind="knowledge",
                    target_id=k.id,
                    case_id=None,
                    title=k.title,
                    status=k.status,
                )
            )
        elif r.case_id and (c := cases.get(r.case_id)):
            links.append(
                AssetLinkView(
                    id=r.id,
                    kind="case",
                    target_id=c.id,
                    case_id=c.id,
                    title=c.title,
                    status=c.status,
                )
            )
        elif r.task_id and (t := tasks.get(r.task_id)):
            links.append(
                AssetLinkView(
                    id=r.id,
                    kind="task",
                    target_id=t.id,
                    case_id=t.case_id,
                    title=t.title,
                    status=t.status,
                )
            )
    return links


async def _dependents(
    access: WorkspaceAccess,
    asset_id: uuid.UUID,
    primary_of: dict[uuid.UUID, catalog.AssigneeView],
) -> list[AssetResponsibilityView]:
    rows = await access.session.execute(
        select(Responsibility, ResponsibilityDependency.relationship)
        .join(
            ResponsibilityDependency,
            ResponsibilityDependency.responsibility_id == Responsibility.id,
        )
        .where(ResponsibilityDependency.depends_on_asset_id == asset_id)
        .order_by(Responsibility.name)
    )
    return [
        AssetResponsibilityView(
            id=r.id,
            name=r.name,
            criticality=r.criticality,
            relationship=rel,
            primary_owner=primary_of.get(r.id),
        )
        for r, rel in rows
    ]


async def link_target(
    access: WorkspaceAccess, asset_id: uuid.UUID, data: AssetTargetIn
) -> AssetDetail:
    """Link an asset to knowledge, a case or a task (one at a time)."""
    if sum(x is not None for x in (data.knowledge_item_id, data.case_id, data.task_id)) != 1:
        raise ApiError(422, "one_target", "Link one knowledge item, case or task.")
    # Linking to knowledge needs only write access to knowledge; cases/tasks need case.manage.
    if data.knowledge_item_id:
        authorize(access, Permission.KNOWLEDGE_WRITE)
        found = await access.session.scalar(
            select(KnowledgeItem.id).where(
                KnowledgeItem.id == data.knowledge_item_id, readable(access)
            )
        )
    elif data.case_id:
        authorize(access, Permission.CASE_MANAGE)
        found = await access.session.scalar(
            select(ContinuityCase.id).where(ContinuityCase.id == data.case_id)
        )
    else:
        authorize(access, Permission.CASE_MANAGE)
        found = await access.session.scalar(select(CaseTask.id).where(CaseTask.id == data.task_id))
    if found is None:
        raise ApiError(422, "target_not_found", "That item does not exist.")
    await _get(access, asset_id)
    exists = await access.session.scalar(
        select(AssetLink.id).where(
            AssetLink.asset_id == asset_id,
            AssetLink.knowledge_item_id.is_not_distinct_from(data.knowledge_item_id),
            AssetLink.case_id.is_not_distinct_from(data.case_id),
            AssetLink.task_id.is_not_distinct_from(data.task_id),
        )
    )
    if exists is None:
        access.session.add(
            AssetLink(
                tenant_id=access.tenant_id,
                asset_id=asset_id,
                knowledge_item_id=data.knowledge_item_id,
                case_id=data.case_id,
                task_id=data.task_id,
                created_by=access.user_id,
            )
        )
        catalog.record_audit(access, "asset.linked", "asset", asset_id)
        await access.session.flush()
    return await get_asset(access, asset_id)


async def unlink_target(
    access: WorkspaceAccess, asset_id: uuid.UUID, link_id: uuid.UUID
) -> AssetDetail:
    authorize(access, Permission.CASE_MANAGE)
    await _get(access, asset_id)
    removed = await access.session.scalar(
        delete(AssetLink)
        .where(AssetLink.id == link_id, AssetLink.asset_id == asset_id)
        .returning(AssetLink.id)
    )
    if removed is None:
        raise ApiError(404, "link_not_found", "Link not found.")
    catalog.record_audit(access, "asset.unlinked", "asset", asset_id)
    return await get_asset(access, asset_id)
