"""What a case touches, from what Relay actually knows: per responsibility in scope, the
assets it stewards, connected GitHub/Linear/Notion sources, open risks and knowledge.

Connector state is reported alongside so a missing source reads as "unavailable", never
as "nothing there". Nothing is inferred: this is a read of recorded data.
"""

import uuid
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select

from relay.catalog import context
from relay.catalog import knowledge as catalog_knowledge
from relay.catalog.models import Asset, ResponsibilityAsset
from relay.continuity import service as cases
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.github.models import GitHubInstallation
from relay.integrations.linear.models import LinearConnection
from relay.integrations.notion.models import NotionConnection
from relay.policy.permissions import Permission, authorize, visible


class SourceStatus(BaseModel):
    source: Literal["GitHub", "Linear", "Notion"]
    state: Literal["connected", "partial", "not_connected"]


class AssetRef(BaseModel):
    id: uuid.UUID
    name: str
    asset_type: str
    status: str


class KnowledgeCount(BaseModel):
    total: int
    stale: int


class ImpactItem(BaseModel):
    scope_item_id: uuid.UUID
    responsibility_id: uuid.UUID
    responsibility_name: str
    criticality: str
    role: str
    current_owner_name: str | None
    recipient_name: str | None
    state: str
    assets: list[AssetRef]
    evidence: list[context.Evidence]
    risks: list[context.RiskSignal]
    knowledge: KnowledgeCount


class ImpactView(BaseModel):
    items: list[ImpactItem]
    sources: list[SourceStatus]


async def source_status(access: WorkspaceAccess) -> list[SourceStatus]:
    """Per connector: not connected, connected, or partial (lost access or last sync failed)."""
    result = []
    for label, model in (
        ("GitHub", GitHubInstallation),
        ("Linear", LinearConnection),
        ("Notion", NotionConnection),
    ):
        rows = (await access.session.execute(select(model.status, model.last_sync_status))).all()
        state: Literal["connected", "partial", "not_connected"] = (
            "not_connected"
            if not rows
            else "partial"
            if any(status != "active" or sync in ("error", "partial") for status, sync in rows)
            else "connected"
        )
        result.append(SourceStatus(source=label, state=state))
    return result


async def case_impact(access: WorkspaceAccess, case_id: uuid.UUID) -> ImpactView:
    authorize(access, Permission.CASE_READ)
    detail = await cases.get_case(access, case_id)
    rids = [s.responsibility_id for s in detail.scope]
    assets: dict[uuid.UUID, list[AssetRef]] = {rid: [] for rid in rids}
    for rid, asset in await access.session.execute(
        select(ResponsibilityAsset.responsibility_id, Asset)
        .join(Asset, Asset.id == ResponsibilityAsset.asset_id)
        .where(
            ResponsibilityAsset.responsibility_id.in_(rids),
            visible(access, Permission.RESPONSIBILITY_READ, Asset.tenant_id),
        )
        .order_by(Asset.name)
    ):
        assets[rid].append(
            AssetRef(id=asset.id, name=asset.name, asset_type=asset.asset_type, status=asset.status)
        )
    items = []
    for s in detail.scope:
        ctx = await context.responsibility_context(access, s.responsibility_id)
        knowledge = await catalog_knowledge.responsibility_knowledge(access, s.responsibility_id)
        items.append(
            ImpactItem(
                scope_item_id=s.id,
                responsibility_id=s.responsibility_id,
                responsibility_name=s.responsibility_name,
                criticality=s.criticality,
                role=s.role,
                current_owner_name=s.current_owner_name,
                recipient_name=s.recipient.name if s.recipient else None,
                state=s.state,
                assets=assets[s.responsibility_id],
                evidence=ctx.evidence,
                risks=[r for r in ctx.risks if r.status != "resolved"],
                knowledge=KnowledgeCount(
                    total=len(knowledge), stale=sum(1 for k in knowledge if k.freshness == "stale")
                ),
            )
        )
    return ImpactView(items=items, sources=await source_status(access))
