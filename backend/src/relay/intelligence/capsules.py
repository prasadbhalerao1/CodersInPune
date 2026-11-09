"""Context capsules: a role-specific handover for one recipient, versioned and approved.

A version is built from the case's latest analysis (supported, not rejected claims) and
reviewed interview answers; with AI on, the Handover Generator adds a written draft as a
further version. Content is limited to what the *recipient* may see (D2): anything that
relies on managers-only evidence is left out for a member recipient and counted under
omissions. Every render re-checks evidence (withdrawn sources drop out) and applies the
editors' redactions for the viewer (D9). Editing makes a new version and needs approval
again; the recipient acknowledges the approved version.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any

import procrastinate
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from relay.audit import service as audit
from relay.config import Settings
from relay.continuity import service as continuity
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence import capabilities as caps
from relay.intelligence import runs
from relay.intelligence import service as svc
from relay.intelligence.evidence import Pool, build_pool
from relay.intelligence.models import (
    AgentRun,
    Capsule,
    CapsuleAck,
    CapsuleVersion,
    Claim,
    ClaimEvidence,
    Evidence,
    InterviewQuestion,
)
from relay.intelligence.validate import validate_claims
from relay.policy.permissions import Permission, authorize, role_allows
from relay.shared.api_types import StrictInput
from relay.shared.errors import ApiError

GENERATOR = "handover_generator"
SECTIONS = (
    ("own", "What you now own"),
    ("work", "Work in flight"),
    ("decision", "Decisions already made"),
    ("risk", "Risks and gaps"),
    ("question", "Open questions"),
    ("dependency", "Dependencies"),
    ("interview", "From the handover interview"),
    ("other", "Other findings"),
)
MANAGER_ROLES = ("owner", "admin")


def _section_of(kind: str, claim_type: str) -> str:
    if kind == "finding" and claim_type == "direct_fact":
        return "own"
    return {
        "work": "work",
        "decision": "decision",
        "missing": "risk",
        "conflict": "risk",
        "question": "question",
        "dependency": "dependency",
    }.get(kind, "risk" if claim_type == "rule" else "other")


class CapsulePoint(BaseModel):
    key: str
    text: str
    kind: str
    claim_type: str
    confidence: str
    redacted: bool = False
    evidence: list[svc.EvidenceView] = []


class CapsuleSection(BaseModel):
    heading: str
    points: list[CapsulePoint]


class CapsuleOmission(BaseModel):
    reason: str
    count: int


class CapsuleView(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    case_title: str
    recipient_user_id: uuid.UUID
    recipient_name: str
    status: str
    version: int
    source: str
    summary: str | None
    sections: list[CapsuleSection]
    omissions: list[CapsuleOmission]
    approved_by: str | None
    approved_at: datetime | None
    acknowledged_at: datetime | None
    created_at: datetime
    can_edit: bool
    can_approve: bool
    can_acknowledge: bool
    generating: bool


class CapsuleSummary(BaseModel):
    id: uuid.UUID
    recipient_user_id: uuid.UUID
    recipient_name: str
    status: str
    version: int
    updated_at: datetime


class CapsuleVersionView(BaseModel):
    version: int
    source: str
    created_by: str | None
    created_at: datetime
    approved_by: str | None
    approved_at: datetime | None
    acknowledged: bool


class CapsuleIn(StrictInput):
    recipient_user_id: uuid.UUID


class CapsuleEdit(StrictInput):
    redactions: list[Annotated[str, StringConstraints(max_length=80)]] | None = Field(
        default=None, max_length=500
    )
    summary: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None


async def _recipient_role(access: WorkspaceAccess, user_id: uuid.UUID) -> str:
    role = await access.session.scalar(
        select(Membership.role).where(
            Membership.user_id == user_id,
            Membership.tenant_id == access.tenant_id,
            Membership.status == "active",
        )
    )
    if role is None:
        raise ApiError(422, "recipient_not_member", "The recipient must be an active member.")
    return role


def _audience(role: str) -> str:
    return "managers" if role in MANAGER_ROLES else "workspace"


async def _latest_analysis(session: AsyncSession, case_id: uuid.UUID) -> AgentRun | None:
    return await session.scalar(
        select(AgentRun)
        .where(AgentRun.case_id == case_id, AgentRun.capability == runs.ANALYSIS)
        .order_by(AgentRun.created_at.desc())
        .limit(1)
    )


async def _rules_version(
    access: WorkspaceAccess, case_id: uuid.UUID, audience: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Sections from the latest analysis and reviewed interview answers."""
    session = access.session
    buckets: dict[str, list[dict[str, Any]]] = {key: [] for key, _ in SECTIONS}
    restricted = withdrawn = 0
    analysis = await _latest_analysis(session, case_id)
    if analysis is not None:
        claims = list(
            await session.scalars(
                select(Claim).where(Claim.run_id == analysis.id, Claim.review_status != "rejected")
            )
        )
        links: dict[uuid.UUID, list[Evidence]] = {}
        for claim_id, e in await session.execute(
            select(ClaimEvidence.claim_id, Evidence)
            .join(Evidence, Evidence.id == ClaimEvidence.evidence_id)
            .where(Evidence.run_id == analysis.id)
        ):
            links.setdefault(claim_id, []).append(e)
        current = await svc.current_evidence(access, (e for es in links.values() for e in es))
        for c in claims:
            ev = [current[e.id] for e in links.get(c.id, [])]
            if ev and not any(e.status == "active" for e in ev):
                withdrawn += 1
                continue
            if audience == "workspace" and (
                c.audience != "workspace" or any(e.audience != "workspace" for e in ev)
            ):
                restricted += 1
                continue
            buckets[_section_of(c.kind, c.claim_type)].append(
                {
                    "key": f"c:{c.id}",
                    "text": c.text,
                    "kind": c.kind,
                    "claim_type": c.claim_type,
                    "confidence": c.confidence,
                    "evidence_ids": [str(e.id) for e in ev],
                }
            )
    for q in await session.scalars(
        select(InterviewQuestion).where(
            InterviewQuestion.case_id == case_id,
            InterviewQuestion.status == "answered",
            InterviewQuestion.reviewed_at.is_not(None),
        )
    ):
        rows = await svc._evidence_rows(access, (uuid.UUID(e) for e in q.evidence_ids))
        if audience == "workspace" and any(e.audience != "workspace" for e in rows):
            restricted += 1
            continue
        buckets["interview"].append(
            {
                "key": f"q:{q.id}",
                "text": f"{q.question} — {q.answer}",
                "kind": "decision",
                "claim_type": "human_decision",
                "confidence": "high",
                "evidence_ids": q.evidence_ids,
            }
        )
    sections = [
        {"heading": heading, "points": buckets[key]} for key, heading in SECTIONS if buckets[key]
    ]
    omissions = []
    if restricted:
        omissions.append(
            {"reason": "Relies on evidence the recipient can't see", "count": restricted}
        )
    if withdrawn:
        omissions.append({"reason": "Source withdrawn since the analysis", "count": withdrawn})
    return sections, omissions


async def _load(access: WorkspaceAccess, capsule_id: uuid.UUID, *, lock: bool = False) -> Capsule:
    authorize(access, Permission.AI_READ)
    stmt = select(Capsule).where(Capsule.id == capsule_id, Capsule.tenant_id == access.tenant_id)
    capsule = await access.session.scalar(stmt.with_for_update() if lock else stmt)
    editor = role_allows(access.role, Permission.AI_REVIEW)
    if capsule is None or not (editor or capsule.recipient_user_id == access.user_id):
        raise ApiError(404, "capsule_not_found", "Handover capsule not found.")
    return capsule


async def _version(session: AsyncSession, capsule: Capsule, n: int | None = None) -> CapsuleVersion:
    version = await session.scalar(
        select(CapsuleVersion).where(
            CapsuleVersion.capsule_id == capsule.id,
            CapsuleVersion.version == (n or capsule.current_version),
        )
    )
    if version is None:
        raise ApiError(404, "version_not_found", "That version doesn't exist.")
    return version


def _new_version(
    session: AsyncSession,
    capsule: Capsule,
    *,
    source: str,
    sections: list[dict[str, Any]],
    omissions: list[dict[str, Any]],
    created_by: uuid.UUID | None,
    summary: str | None = None,
    redactions: list[str] | None = None,
    run_id: uuid.UUID | None = None,
) -> None:
    capsule.current_version += 1
    capsule.status, capsule.updated_at = "draft", func.now()
    session.add(
        CapsuleVersion(
            tenant_id=capsule.tenant_id,
            capsule_id=capsule.id,
            version=capsule.current_version,
            run_id=run_id,
            source=source,
            summary=summary,
            sections=sections,
            omissions=omissions,
            redactions=redactions or [],
            created_by=created_by,
        )
    )


async def generate(
    access: WorkspaceAccess,
    case_id: uuid.UUID,
    data: CapsuleIn,
    settings: Settings,
    jobs: procrastinate.App,
) -> CapsuleView:
    authorize(access, Permission.AI_RUN)
    session = access.session
    case = await continuity._load(access, case_id)
    audience = _audience(await _recipient_role(access, data.recipient_user_id))
    capsule = await session.scalar(
        select(Capsule)
        .where(Capsule.case_id == case_id, Capsule.recipient_user_id == data.recipient_user_id)
        .with_for_update()
    )
    if capsule is None:
        capsule = Capsule(
            id=uuid.uuid7(),
            tenant_id=access.tenant_id,
            case_id=case_id,
            recipient_user_id=data.recipient_user_id,
            created_by=access.user_id,
        )
        session.add(capsule)
        await session.flush()
    sections, omissions = await _rules_version(access, case_id, audience)
    _new_version(
        session,
        capsule,
        source="rules",
        sections=sections,
        omissions=omissions,
        created_by=access.user_id,
    )
    gateway = runs.gateway_for(settings)
    if gateway.configured and await runs.ai_enabled(session, GENERATOR):
        pool = await build_pool(access, case)
        run = AgentRun(
            id=uuid.uuid7(),
            tenant_id=access.tenant_id,
            capability=GENERATOR,
            capability_version=1,
            case_id=case_id,
            requested_by=access.user_id,
            state="running",
            input_hash=pool.input_hash(),
            checkpoint={
                "case_title": case.title,
                "partial_sources": pool.partial_sources,
                "steps": [GENERATOR],
                "ai": "on",
                "audience": audience,
                "capsule_id": str(capsule.id),
                "brief": f"Recipient audience: {audience}. Omitted for them: "
                + (", ".join(f"{o['count']} ({o['reason']})" for o in omissions) or "nothing"),
            },
            started_at=runs._now(),
        )
        session.add(run)
        await session.flush()
        await runs.persist_pool(session, run, pool)
        await runs._queue(session, jobs, run)
    audit.record(
        session,
        tenant_id=access.tenant_id,
        action="ai.capsule_generated",
        actor_user_id=access.user_id,
        target_type="continuity_case",
        target_id=case_id,
        details={"capsule_id": str(capsule.id), "version": capsule.current_version},
    )
    await session.flush()
    return await view(access, capsule.id)


async def _store(
    session: AsyncSession,
    run: AgentRun,
    name: str,
    output: caps.CapsuleOutput,
    pool: Pool,
    ids: dict[str, uuid.UUID],
) -> dict[str, int]:
    capsule = await session.get(Capsule, uuid.UUID(run.checkpoint["capsule_id"]))
    if capsule is None or capsule.status != "draft":
        return {"skipped": 1}  # approved meanwhile: never replace approved content silently
    sections, kept, rejected = [], 0, 0
    for s in output.sections:
        outcome = validate_claims(pool, s.points)
        rejected += sum(outcome.rejected.values())
        points = [
            {
                "key": f"a:{run.id}:{kept + i}",
                "text": c.text,
                "kind": c.kind,
                "claim_type": c.claim_type,
                "confidence": c.confidence,
                "evidence_ids": [str(ids[r]) for r in c.refs],
            }
            for i, c in enumerate(outcome.claims)
        ]
        kept += len(points)
        if points:
            sections.append({"heading": " ".join(s.heading.split())[:120], "points": points})
    previous = await _version(session, capsule)
    _new_version(
        session,
        capsule,
        source="ai",
        sections=sections,
        omissions=previous.omissions,
        created_by=None,
        summary=" ".join(output.summary.split())[:1200] or None,
        run_id=run.id,
    )
    return {"points": kept, "rejected": rejected}


runs.STEP_KINDS[GENERATOR] = runs.StepKind(caps.CapsuleOutput, _store)


async def view(
    access: WorkspaceAccess, capsule_id: uuid.UUID, version: int | None = None
) -> CapsuleView:
    """The capsule as this viewer may see it now."""
    capsule = await _load(access, capsule_id)
    session = access.session
    v = await _version(session, capsule, version)
    editor = role_allows(access.role, Permission.AI_REVIEW)
    ids = {uuid.UUID(e) for s in v.sections for p in s["points"] for e in p["evidence_ids"]}
    evidence = await svc.current_evidence(access, await svc._evidence_rows(access, ids))
    redacted, hidden, withdrawn = set(v.redactions), 0, 0
    sections: list[CapsuleSection] = []
    for s in v.sections:
        points = []
        for p in s["points"]:
            ev = [evidence[uuid.UUID(e)] for e in p["evidence_ids"] if uuid.UUID(e) in evidence]
            if ev and not any(e.status == "active" for e in ev):
                withdrawn += 1
                continue
            if not svc._allowed(access, "workspace", ev):
                hidden += 1
                continue
            if p["key"] in redacted and not editor:
                hidden += 1
                continue
            points.append(
                CapsulePoint(
                    key=p["key"],
                    text=p["text"],
                    kind=p["kind"],
                    claim_type=p["claim_type"],
                    confidence=p["confidence"],
                    redacted=p["key"] in redacted,
                    evidence=ev,
                )
            )
        if points:
            sections.append(CapsuleSection(heading=s["heading"], points=points))
    omissions = [CapsuleOmission(**o) for o in v.omissions]
    if withdrawn:
        omissions.append(
            CapsuleOmission(reason="Source withdrawn since this version", count=withdrawn)
        )
    if hidden:
        omissions.append(
            CapsuleOmission(reason="Withheld from you by the editors or access", count=hidden)
        )
    names = await continuity._member_names(access)
    ack = await session.scalar(
        select(CapsuleAck.acknowledged_at).where(
            CapsuleAck.capsule_id == capsule.id,
            CapsuleAck.version == v.version,
            CapsuleAck.user_id == capsule.recipient_user_id,
        )
    )
    case = await continuity._load(access, capsule.case_id)
    generating = await session.scalar(
        select(func.count()).where(
            AgentRun.capability == GENERATOR,
            AgentRun.case_id == capsule.case_id,
            AgentRun.state.in_(runs.ACTIVE),
            AgentRun.checkpoint["capsule_id"].astext == str(capsule.id),
        )
    )
    recipient = capsule.recipient_user_id == access.user_id
    latest = v.version == capsule.current_version
    return CapsuleView(
        id=capsule.id,
        case_id=capsule.case_id,
        case_title=case.title,
        recipient_user_id=capsule.recipient_user_id,
        recipient_name=names.get(capsule.recipient_user_id, "Member"),
        status=capsule.status if latest else ("approved" if v.approved_at else "superseded"),
        version=v.version,
        source=v.source,
        summary=v.summary,
        sections=sections,
        omissions=omissions,
        approved_by=names.get(v.approved_by) if v.approved_by else None,
        approved_at=v.approved_at,
        acknowledged_at=ack,
        created_at=v.created_at,
        can_edit=editor and latest,
        can_approve=editor and latest and not recipient and v.approved_at is None,
        can_acknowledge=recipient and latest and capsule.status == "approved",
        generating=bool(generating),
    )


async def list_for_case(access: WorkspaceAccess, case_id: uuid.UUID) -> list[CapsuleSummary]:
    authorize(access, Permission.AI_READ)
    await continuity._load(access, case_id)
    stmt = select(Capsule).where(Capsule.case_id == case_id).order_by(Capsule.created_at)
    if not role_allows(access.role, Permission.AI_REVIEW):
        stmt = stmt.where(Capsule.recipient_user_id == access.user_id)
    names = await continuity._member_names(access)
    return [
        CapsuleSummary(
            id=c.id,
            recipient_user_id=c.recipient_user_id,
            recipient_name=names.get(c.recipient_user_id, "Member"),
            status=c.status,
            version=c.current_version,
            updated_at=c.updated_at,
        )
        for c in await access.session.scalars(stmt)
    ]


async def edit(access: WorkspaceAccess, capsule_id: uuid.UUID, data: CapsuleEdit) -> CapsuleView:
    authorize(access, Permission.AI_REVIEW)
    capsule = await _load(access, capsule_id, lock=True)
    v = await _version(access.session, capsule)
    keys = {p["key"] for s in v.sections for p in s["points"]}
    redactions = v.redactions if data.redactions is None else sorted(set(data.redactions) & keys)
    _new_version(
        access.session,
        capsule,
        source="edit",
        sections=v.sections,
        omissions=v.omissions,
        created_by=access.user_id,
        summary=v.summary if data.summary is None else (data.summary or None),
        redactions=redactions,
    )
    await access.session.flush()
    return await view(access, capsule.id)


async def approve(access: WorkspaceAccess, capsule_id: uuid.UUID) -> CapsuleView:
    authorize(access, Permission.AI_REVIEW)
    capsule = await _load(access, capsule_id, lock=True)
    if capsule.recipient_user_id == access.user_id:
        raise ApiError(409, "self_approval", "The recipient can't approve their own handover.")
    v = await _version(access.session, capsule)
    if v.approved_at is not None:
        raise ApiError(409, "already_approved", "This version is already approved.")
    v.approved_by, v.approved_at = access.user_id, func.now()
    capsule.status, capsule.updated_at = "approved", func.now()
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="ai.capsule_approved",
        actor_user_id=access.user_id,
        target_type="continuity_case",
        target_id=capsule.case_id,
        details={"capsule_id": str(capsule.id), "version": v.version},
    )
    await access.session.flush()
    return await view(access, capsule.id)


async def acknowledge(access: WorkspaceAccess, capsule_id: uuid.UUID) -> CapsuleView:
    capsule = await _load(access, capsule_id, lock=True)
    if capsule.recipient_user_id != access.user_id:
        raise ApiError(403, "forbidden", "Only the recipient can acknowledge this handover.")
    if capsule.status != "approved":
        raise ApiError(409, "not_approved", "Only an approved handover can be acknowledged.")
    access.session.add(
        CapsuleAck(
            tenant_id=access.tenant_id,
            capsule_id=capsule.id,
            version=capsule.current_version,
            user_id=access.user_id,
        )
    )
    capsule.status, capsule.updated_at = "acknowledged", func.now()
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action="ai.capsule_acknowledged",
        actor_user_id=access.user_id,
        target_type="continuity_case",
        target_id=capsule.case_id,
        details={"capsule_id": str(capsule.id), "version": capsule.current_version},
    )
    await access.session.flush()
    return await view(access, capsule.id)


async def versions(access: WorkspaceAccess, capsule_id: uuid.UUID) -> list[CapsuleVersionView]:
    capsule = await _load(access, capsule_id)
    session = access.session
    names = await continuity._member_names(access)
    acked = set(
        await session.scalars(
            select(CapsuleAck.version).where(
                CapsuleAck.capsule_id == capsule.id,
                CapsuleAck.user_id == capsule.recipient_user_id,
            )
        )
    )
    return [
        CapsuleVersionView(
            version=v.version,
            source=v.source,
            created_by=names.get(v.created_by) if v.created_by else None,
            created_at=v.created_at,
            approved_by=names.get(v.approved_by) if v.approved_by else None,
            approved_at=v.approved_at,
            acknowledged=v.version in acked,
        )
        for v in await session.scalars(
            select(CapsuleVersion)
            .where(CapsuleVersion.capsule_id == capsule.id)
            .order_by(CapsuleVersion.version.desc())
        )
    ]
