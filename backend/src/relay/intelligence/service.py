"""Reading AI output, reviewing proposals, and AI administration.

Evidence is re-checked whenever it is shown: a source that was withdrawn, archived or
lost since the run makes the evidence `withdrawn` (claims that relied only on it become
unsupported), and knowledge that became managers-only is treated as such (D2). Members
only ever see claims and proposals whose evidence is all workspace-visible.
"""

import uuid
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import Literal

import procrastinate
from pydantic import BaseModel
from sqlalchemy import func, select

from relay.audit import service as audit
from relay.catalog import knowledge as catalog_knowledge
from relay.catalog.models import KnowledgeItem
from relay.config import Settings
from relay.continuity import collaboration
from relay.continuity import service as continuity
from relay.continuity.models import CaseScopeItem
from relay.identity.workspace_access import WorkspaceAccess
from relay.integrations.github.models import GitHubRepository
from relay.integrations.linear.models import LinearIssue
from relay.integrations.notion.models import NotionPage
from relay.intelligence import runs
from relay.intelligence.models import (
    AgentRun,
    AgentRunEvent,
    AiCapabilitySetting,
    AiSettings,
    Claim,
    ClaimEvidence,
    Evidence,
    Proposal,
)
from relay.intelligence.registry import CAPABILITIES, capability
from relay.policy.permissions import Permission, authorize, role_allows
from relay.shared.api_types import LongText, Name, StrictInput
from relay.shared.errors import ApiError

CASE_COMMENT_TYPES = ("case_finding", "exception", "coordination_message", "handover_content")


class EvidenceView(BaseModel):
    id: uuid.UUID
    ref: str
    source_system: str
    source_type: str
    title: str
    url: str | None
    revision: str | None
    source_ts: datetime | None
    excerpt: str
    audience: str
    status: str
    # The source has a newer revision than the one cited (Relay knowledge and Notion pages).
    changed: bool = False


class ClaimView(BaseModel):
    id: uuid.UUID
    capability: str
    kind: str
    claim_type: str
    text: str
    confidence: str
    audience: str
    review_status: str
    supported: bool
    timeline_at: datetime | None
    evidence: list[EvidenceView]


class RunView(BaseModel):
    id: uuid.UUID
    capability: str
    case_id: uuid.UUID | None
    state: str
    step: int
    steps: list[str]
    ai: str
    provider: str | None
    model: str | None
    key_index: int | None
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    duration_ms: int
    error_code: str | None
    partial_sources: list[str]
    created_at: datetime
    finished_at: datetime | None


class ProposalView(BaseModel):
    id: uuid.UUID
    capability: str
    type: str
    title: str
    detail: str
    confidence: str
    audience: str
    status: str
    reason: str | None
    result_ref: str | None
    reviewed_at: datetime | None
    created_at: datetime
    evidence: list[EvidenceView]


class AnalysisView(BaseModel):
    case_id: uuid.UUID
    ai_configured: bool
    run: RunView | None
    claims: list[ClaimView]
    proposals: list[ProposalView]
    hidden_restricted: bool
    can_run: bool
    can_review: bool


class ProposalEdit(StrictInput):
    title: Name | None = None
    detail: LongText | None = None


class ProposalReject(StrictInput):
    reason: LongText | None = None


class ClaimReview(StrictInput):
    review_status: Literal["accepted", "rejected", "unreviewed"]


def run_view(run: AgentRun) -> RunView:
    cp = run.checkpoint
    return RunView(
        id=run.id,
        capability=run.capability,
        case_id=run.case_id,
        state=run.state,
        step=run.step,
        steps=list(cp.get("steps", [])),
        ai=str(cp.get("ai", "on")),
        provider=run.provider,
        model=run.model,
        key_index=run.key_index,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cost_usd=run.cost_usd,
        duration_ms=run.duration_ms,
        error_code=run.error_code,
        partial_sources=list(cp.get("partial_sources", [])),
        created_at=run.created_at,
        finished_at=run.finished_at,
    )


def _manager(access: WorkspaceAccess) -> bool:
    return role_allows(access.role, Permission.RESPONSIBILITY_MANAGE)


async def current_evidence(
    access: WorkspaceAccess, rows: Iterable[Evidence]
) -> dict[uuid.UUID, EvidenceView]:
    """Evidence as it stands now: withdrawn sources and tightened visibility applied."""
    rows = list(rows)
    session = access.session
    by_type: dict[str, set[str]] = {}
    for e in rows:
        by_type.setdefault(e.source_type, set()).add(e.source_id)

    knowledge: dict[str, tuple[str, str]] = {}
    revisions: dict[tuple[str, str], str] = {}  # (source_type, source_id) -> current revision
    ids = [uuid.UUID(i) for i in by_type.get("knowledge", ())]
    if ids:
        for kid, status, vis, updated in await session.execute(
            select(
                KnowledgeItem.id,
                KnowledgeItem.status,
                KnowledgeItem.visibility,
                KnowledgeItem.updated_at,
            ).where(KnowledgeItem.id.in_(ids))
        ):
            knowledge[str(kid)] = (status, vis)
            revisions["knowledge", str(kid)] = updated.isoformat()
    notion: dict[str, tuple[str, str]] = {}
    if by_type.get("notion_page"):
        for nid, page_status, k_status, vis, revision in await session.execute(
            select(
                NotionPage.notion_id,
                NotionPage.status,
                KnowledgeItem.status,
                KnowledgeItem.visibility,
                NotionPage.revision,
            )
            .join(KnowledgeItem, KnowledgeItem.id == NotionPage.knowledge_item_id)
            .where(NotionPage.notion_id.in_(by_type["notion_page"]))
        ):
            ok = page_status == "active" and k_status == "active"
            notion[nid] = ("active" if ok else "withdrawn", vis)
            revisions["notion_page", nid] = revision
    repos = {
        name: accessible
        for name, accessible in await session.execute(
            select(GitHubRepository.full_name, GitHubRepository.accessible)
        )
    }
    linear_ids = by_type.get("issue", set())
    linear = (
        set(
            await session.scalars(
                select(LinearIssue.identifier).where(LinearIssue.identifier.in_(linear_ids))
            )
        )
        if linear_ids
        else set()
    )

    out: dict[uuid.UUID, EvidenceView] = {}
    for e in rows:
        status, audience = e.status, e.audience
        if e.source_type == "knowledge":
            k_status, vis = knowledge.get(e.source_id, ("withdrawn", "managers"))
            status = "active" if k_status == "active" else "withdrawn"
            audience = "managers" if vis == "managers" else audience
        elif e.source_type == "notion_page":
            status, vis = notion.get(e.source_id, ("withdrawn", "managers"))
            audience = "managers" if vis == "managers" else audience
        elif e.source_system == "github":
            if not repos.get(e.source_id.split("#")[0], False):
                status = "withdrawn"
        elif e.source_system == "linear" and e.source_id not in linear:
            status = "withdrawn"
        current = revisions.get((e.source_type, e.source_id))
        out[e.id] = EvidenceView(
            changed=status == "active" and current is not None and current != e.revision,
            id=e.id,
            ref=e.ref,
            source_system=e.source_system,
            source_type=e.source_type,
            title=e.title,
            url=e.url,
            revision=e.revision,
            source_ts=e.source_ts,
            excerpt=e.excerpt if status == "active" else "",
            audience=audience,
            status=status,
        )
    return out


def _allowed(access: WorkspaceAccess, audience: str, evidence: list[EvidenceView]) -> bool:
    if _manager(access):
        return True
    return audience == "workspace" and all(e.audience == "workspace" for e in evidence)


async def _evidence_rows(access: WorkspaceAccess, ids: Iterable[uuid.UUID]) -> list[Evidence]:
    ids = list(ids)
    if not ids:
        return []
    return list(await access.session.scalars(select(Evidence).where(Evidence.id.in_(ids))))


def _proposal_view(p: Proposal, evidence: dict[uuid.UUID, EvidenceView]) -> ProposalView:
    return ProposalView(
        id=p.id,
        capability=p.capability,
        type=p.type,
        title=p.title,
        detail=str(p.payload.get("detail", "")),
        confidence=p.confidence,
        audience=p.audience,
        status=p.status,
        reason=p.reason,
        result_ref=p.result_ref,
        reviewed_at=p.reviewed_at,
        created_at=p.created_at,
        evidence=[evidence[uuid.UUID(i)] for i in p.evidence_ids if uuid.UUID(i) in evidence],
    )


async def case_proposals(access: WorkspaceAccess, case_id: uuid.UUID) -> list[ProposalView]:
    session = access.session
    proposals = list(
        await session.scalars(
            select(Proposal)
            .where(Proposal.case_id == case_id, Proposal.tenant_id == access.tenant_id)
            .order_by(Proposal.status != "pending", Proposal.created_at.desc())
            .limit(100)
        )
    )
    rows = await _evidence_rows(access, (uuid.UUID(i) for p in proposals for i in p.evidence_ids))
    evidence = await current_evidence(access, rows)
    views = [_proposal_view(p, evidence) for p in proposals]
    return [v for v in views if _allowed(access, v.audience, v.evidence)]


async def get_analysis(
    access: WorkspaceAccess, case_id: uuid.UUID, settings: Settings
) -> AnalysisView:
    authorize(access, Permission.AI_READ)
    await continuity._load(access, case_id)
    session = access.session
    run = await session.scalar(
        select(AgentRun)
        .where(
            AgentRun.case_id == case_id,
            AgentRun.capability == runs.ANALYSIS,
            AgentRun.tenant_id == access.tenant_id,
        )
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )
    claims: list[ClaimView] = []
    hidden = False
    if run is not None:
        rows = list(await session.scalars(select(Claim).where(Claim.run_id == run.id)))
        links = list(
            await session.execute(
                select(ClaimEvidence.claim_id, Evidence)
                .join(Evidence, Evidence.id == ClaimEvidence.evidence_id)
                .where(Evidence.run_id == run.id)
            )
        )
        evidence = await current_evidence(access, (e for _, e in links))
        cited: dict[uuid.UUID, list[EvidenceView]] = {}
        for claim_id, e in links:
            cited.setdefault(claim_id, []).append(evidence[e.id])
        order = {"conflict": 0, "missing": 1, "decision": 2, "question": 3}
        for c in sorted(rows, key=lambda c: (order.get(c.kind, 9), c.created_at)):
            ev = sorted(cited.get(c.id, []), key=lambda e: int(e.ref[1:]))
            if not _allowed(access, c.audience, ev):
                hidden = True
                continue
            supported = not ev or any(e.status == "active" for e in ev)
            claims.append(
                ClaimView(
                    id=c.id,
                    capability=c.capability,
                    kind=c.kind,
                    claim_type=c.claim_type,
                    text=c.text,
                    confidence=c.confidence if supported else "insufficient",
                    audience=c.audience,
                    review_status=c.review_status,
                    supported=supported and c.supported,
                    timeline_at=c.timeline_at,
                    evidence=ev,
                )
            )
    return AnalysisView(
        case_id=case_id,
        ai_configured=runs.gateway_for(settings).configured,
        run=run_view(run) if run else None,
        claims=claims,
        proposals=await case_proposals(access, case_id),
        hidden_restricted=hidden,
        can_run=role_allows(access.role, Permission.AI_RUN),
        can_review=role_allows(access.role, Permission.AI_REVIEW),
    )


async def review_claim(access: WorkspaceAccess, claim_id: uuid.UUID, data: ClaimReview) -> None:
    authorize(access, Permission.AI_REVIEW)
    claim = await access.session.scalar(
        select(Claim).where(Claim.id == claim_id, Claim.tenant_id == access.tenant_id)
    )
    if claim is None:
        raise ApiError(404, "claim_not_found", "Finding not found.")
    claim.review_status = data.review_status


async def _pending(access: WorkspaceAccess, proposal_id: uuid.UUID) -> Proposal:
    proposal = await access.session.scalar(
        select(Proposal)
        .where(Proposal.id == proposal_id, Proposal.tenant_id == access.tenant_id)
        .with_for_update()
    )
    if proposal is None:
        raise ApiError(404, "proposal_not_found", "Proposal not found.")
    if proposal.status != "pending":
        raise ApiError(409, "proposal_already_reviewed", "This proposal was already reviewed.")
    return proposal


async def _target_responsibility(access: WorkspaceAccess, proposal: Proposal) -> uuid.UUID:
    for e in await _evidence_rows(access, (uuid.UUID(i) for i in proposal.evidence_ids)):
        if e.source_type == "responsibility":
            return uuid.UUID(e.source_id)
    first = await access.session.scalar(
        select(CaseScopeItem.responsibility_id)
        .where(CaseScopeItem.case_id == proposal.case_id)
        .order_by(CaseScopeItem.created_at)
        .limit(1)
    )
    if first is None:
        raise ApiError(
            409, "no_responsibility", "The case has no responsibility to attach this to."
        )
    return first


async def accept_proposal(
    access: WorkspaceAccess,
    proposal_id: uuid.UUID,
    edit: ProposalEdit | None,
    jobs: procrastinate.App,
) -> ProposalView:
    """Apply through the normal services, as the reviewer: same checks as doing it by hand."""
    authorize(access, Permission.AI_REVIEW)
    proposal = await _pending(access, proposal_id)
    title = (edit.title if edit and edit.title else proposal.title)[:200]
    detail = (
        edit.detail if edit and edit.detail is not None else str(proposal.payload.get("detail", ""))
    )
    restricted = proposal.audience == "managers"
    if restricted and proposal.type != "knowledge_draft":
        raise ApiError(
            409,
            "restricted_evidence",
            "This proposal relies on managers-only evidence, so it can't be posted where the "
            "whole workspace would see it.",
        )
    case_id = proposal.case_id
    if proposal.type == "task":
        await continuity.add_task(
            access, case_id, continuity.TaskIn(title=title, description=detail[:4000] or None), jobs
        )
        result = "task"
    elif proposal.type == "readiness_criterion":
        await continuity.add_criterion(
            access, case_id, continuity.CriterionIn(criterion_type="attestation", title=title)
        )
        result = "readiness_criterion"
    elif proposal.type == "knowledge_draft":
        rid = await _target_responsibility(access, proposal)
        view = await catalog_knowledge.add_knowledge(
            access,
            rid,
            catalog_knowledge.KnowledgeIn(
                kind="procedure",
                title=title,
                body=detail or None,
                visibility="managers" if restricted else "workspace",
            ),
        )
        item = await access.session.get(KnowledgeItem, view.id)
        assert item is not None
        item.origin = "ai"  # drafted by AI: stays unreviewed until a person reviews it
        result = f"knowledge:{view.id}"
    else:
        label = {
            "case_finding": "Finding",
            "exception": "Proposed exception",
            "coordination_message": "Message",
            "handover_content": "Handover note",
        }[proposal.type]
        body = f"{label}: {title}\n\n{detail}".strip()[:5000]
        await collaboration.add_comment(access, case_id, collaboration.CommentIn(body=body), jobs)
        result = "comment"
    proposal.status = "edited" if edit and (edit.title or edit.detail is not None) else "accepted"
    proposal.reviewed_by, proposal.reviewed_at = access.user_id, func.now()
    proposal.result_ref = result
    if edit:
        proposal.payload = {**proposal.payload, "detail": detail, "edited_title": title}
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="ai.proposal_accepted",
        actor_user_id=access.user_id,
        target_type="continuity_case",
        target_id=case_id,
        details={"proposal_id": str(proposal.id), "type": proposal.type, "status": proposal.status},
    )
    await access.session.flush()
    await access.session.refresh(proposal)
    return _proposal_view(proposal, {})


async def reject_proposal(
    access: WorkspaceAccess, proposal_id: uuid.UUID, data: ProposalReject
) -> None:
    authorize(access, Permission.AI_REVIEW)
    proposal = await _pending(access, proposal_id)
    proposal.status, proposal.reason = "rejected", data.reason
    proposal.reviewed_by, proposal.reviewed_at = access.user_id, func.now()
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="ai.proposal_rejected",
        actor_user_id=access.user_id,
        target_type="continuity_case",
        target_id=proposal.case_id,
        details={"proposal_id": str(proposal.id), "type": proposal.type},
    )


# --- administration -----------------------------------------------------------------


class CapabilityView(BaseModel):
    name: str
    version: int
    title: str
    description: str
    produces: list[str]
    tools: list[str]
    token_budget: int
    timeout_seconds: float
    enabled: bool
    accepted: int
    rejected: int
    pending: int


class AiAdminView(BaseModel):
    configured: bool
    providers: list[str]
    gemini_keys: int
    enabled: bool
    monthly_token_budget: int
    tokens_this_month: int
    capabilities: list[CapabilityView]


class AiSettingsUpdate(StrictInput):
    enabled: bool | None = None
    monthly_token_budget: int | None = None


class CapabilityUpdate(StrictInput):
    enabled: bool


async def admin_overview(access: WorkspaceAccess, settings: Settings) -> AiAdminView:
    authorize(access, Permission.AI_READ)
    session = access.session
    row = await session.scalar(select(AiSettings))
    toggles = dict(
        (
            await session.execute(
                select(AiCapabilitySetting.capability, AiCapabilitySetting.enabled)
            )
        ).all()
    )
    stats: dict[tuple[str, str], int] = {
        (cap, status): n
        for cap, status, n in await session.execute(
            select(Proposal.capability, Proposal.status, func.count()).group_by(
                Proposal.capability, Proposal.status
            )
        )
    }
    budget = (
        row.monthly_token_budget
        if row and row.monthly_token_budget is not None
        else settings.ai_monthly_token_budget
    )
    left = await runs.monthly_tokens_left(session, settings)
    return AiAdminView(
        configured=runs.gateway_for(settings).configured,
        providers=settings.llm_provider_list,
        gemini_keys=len(settings.gemini_keys),
        enabled=row.enabled if row else True,
        monthly_token_budget=budget,
        tokens_this_month=budget - left,
        capabilities=[
            CapabilityView(
                name=c.name,
                version=c.version,
                title=c.title,
                description=c.description,
                produces=list(c.produces),
                tools=list(c.tools),
                token_budget=c.token_budget,
                timeout_seconds=c.timeout_seconds,
                enabled=toggles.get(c.name, True),
                accepted=stats.get((c.name, "accepted"), 0) + stats.get((c.name, "edited"), 0),
                rejected=stats.get((c.name, "rejected"), 0),
                pending=stats.get((c.name, "pending"), 0),
            )
            for c in CAPABILITIES.values()
        ],
    )


async def update_settings(access: WorkspaceAccess, data: AiSettingsUpdate) -> None:
    authorize(access, Permission.AI_ADMIN)
    session = access.session
    row = await session.scalar(select(AiSettings).with_for_update())
    if row is None:
        row = AiSettings(tenant_id=access.tenant_id, updated_by=access.user_id)
        session.add(row)
    if data.enabled is not None:
        row.enabled = data.enabled
    if data.monthly_token_budget is not None:
        if not 0 <= data.monthly_token_budget <= 1_000_000_000:
            raise ApiError(422, "invalid_budget", "Budget must be between 0 and 1,000,000,000.")
        row.monthly_token_budget = data.monthly_token_budget
    row.updated_by, row.updated_at = access.user_id, func.now()
    audit.record(
        session,
        tenant_id=access.tenant_id,
        action="ai.settings_updated",
        actor_user_id=access.user_id,
        details={"enabled": data.enabled, "budget_changed": data.monthly_token_budget is not None},
    )


async def update_capability(access: WorkspaceAccess, name: str, data: CapabilityUpdate) -> None:
    authorize(access, Permission.AI_ADMIN)
    try:
        capability(name)
    except LookupError:
        raise ApiError(404, "capability_not_found", "Unknown capability.") from None
    session = access.session
    row = await session.scalar(
        select(AiCapabilitySetting).where(AiCapabilitySetting.capability == name).with_for_update()
    )
    if row is None:
        row = AiCapabilitySetting(
            tenant_id=access.tenant_id, capability=name, updated_by=access.user_id
        )
        session.add(row)
    row.enabled, row.updated_by, row.updated_at = data.enabled, access.user_id, func.now()
    audit.record(
        session,
        tenant_id=access.tenant_id,
        action="ai.capability_updated",
        actor_user_id=access.user_id,
        details={"capability": name, "enabled": data.enabled},
    )


class RunEventView(BaseModel):
    step: str
    level: str
    code: str
    detail: dict[str, object]
    created_at: datetime


class RunDetail(RunView):
    events: list[RunEventView]


async def list_runs(access: WorkspaceAccess) -> list[RunView]:
    authorize(access, Permission.AI_READ)  # runs hold identifiers and metrics only
    rows = await access.session.scalars(
        select(AgentRun)
        .where(AgentRun.tenant_id == access.tenant_id)
        .order_by(AgentRun.created_at.desc())
        .limit(100)
    )
    return [run_view(r) for r in rows]


async def get_run(access: WorkspaceAccess, run_id: uuid.UUID) -> RunDetail:
    authorize(access, Permission.AI_READ)  # runs hold identifiers and metrics only
    run = await access.session.scalar(
        select(AgentRun).where(AgentRun.id == run_id, AgentRun.tenant_id == access.tenant_id)
    )
    if run is None:
        raise ApiError(404, "run_not_found", "Run not found.")
    events = await access.session.scalars(
        select(AgentRunEvent)
        .where(AgentRunEvent.run_id == run_id)
        .order_by(AgentRunEvent.created_at)
    )
    return RunDetail(
        **run_view(run).model_dump(),
        events=[
            RunEventView(
                step=e.step, level=e.level, code=e.code, detail=e.detail, created_at=e.created_at
            )
            for e in events
        ],
    )
