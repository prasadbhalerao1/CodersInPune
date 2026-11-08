"""Assets: the repositories, services, vendors and processes responsibilities steward.

Assets carry no ownership. "Who looks after the payments API?" is answered through the
responsibilities linked to it, so ownership history, risks and cases stay in one place.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints
from sqlalchemy import delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from relay.catalog import service as catalog
from relay.catalog.models import Asset, OwnershipAssignment, Responsibility, ResponsibilityAsset
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.api_types import LongText, Name, StrictInput, blank_to_none
from relay.shared.errors import ApiError

AssetType = Literal[
    "repository", "service", "project", "process", "vendor", "document_collection", "other"
]
AssetStatus = Literal["active", "archived"]
Relationship = Literal["stewards", "uses"]
Url = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=2000, pattern=r"^https?://\S+$")
]


class AssetIn(StrictInput):
    name: Name
    asset_type: AssetType
    description: LongText | None = None
    url: Url | None = None


class AssetUpdate(StrictInput):
    name: Name | None = None
    asset_type: AssetType | None = None
    description: LongText | None = None
    url: Url | None = None
    status: AssetStatus | None = None


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


class AssetResponsibilityView(BaseModel):
    id: uuid.UUID
    name: str
    criticality: str
    relationship: str
    primary_owner: catalog.AssigneeView | None


class AssetDetail(AssetSummary):
    created_at: datetime
    responsibilities: list[AssetResponsibilityView]


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


async def _link_counts(access: WorkspaceAccess, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    rows = await access.session.execute(
        select(ResponsibilityAsset.asset_id, func.count())
        .join(Responsibility, Responsibility.id == ResponsibilityAsset.responsibility_id)
        .where(ResponsibilityAsset.asset_id.in_(ids), Responsibility.status == "active")
        .group_by(ResponsibilityAsset.asset_id)
    )
    return {key: value for key, value in rows}


def _summary(a: Asset, count: int) -> AssetSummary:
    return AssetSummary(
        id=a.id,
        name=a.name,
        asset_type=a.asset_type,
        description=a.description,
        url=a.url,
        status=a.status,
        responsibility_count=count,
        updated_at=a.updated_at,
    )


async def list_assets(
    access: WorkspaceAccess,
    *,
    q: str | None = None,
    asset_type: AssetType | None = None,
    status: AssetStatus | None = "active",
) -> list[AssetSummary]:
    authorize(access, Permission.RESPONSIBILITY_READ)
    stmt = select(Asset).where(visible(access, Permission.RESPONSIBILITY_READ, Asset.tenant_id))
    if status:
        stmt = stmt.where(Asset.status == status)
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
    if q:
        stmt = stmt.where(or_(Asset.name.ilike(_pattern(q)), Asset.description.ilike(_pattern(q))))
    assets = list(await access.session.scalars(stmt.order_by(Asset.name, Asset.id).limit(500)))
    counts = await _link_counts(access, [a.id for a in assets])
    return [_summary(a, counts.get(a.id, 0)) for a in assets]


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
    return AssetDetail(
        **_summary(asset, len(rows)).model_dump(),
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
    for field, value in changes.items():
        setattr(asset, field, blank_to_none(value) if field in ("description", "url") else value)
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
