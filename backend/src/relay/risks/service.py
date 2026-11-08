"""Deterministic continuity risks computed from the live catalogue (no scores, no AI).

Rules (severity in brackets; each risk explains itself in plain language):
- no_primary_owner: no current primary [critical/high: high, standard: medium, low: low]
- no_backup: no current backup [critical: high, high: medium, otherwise low]
- insufficient_critical_coverage: critical, covered by fewer than 2 owners [high]
- inactive_owner: a current owner is an archived person/team [critical/high: high, else medium]
- single_person_dependency: one person solely owns >= 2 responsibilities
  [high if any is critical/high, else medium]

Risks are recomputed on every read. `risk_record` keeps their lifecycle:
- open: detected and nobody has decided anything yet;
- acknowledged: someone has seen it and owns fixing it (still counted as open work);
- accepted: deliberately tolerated until a date, with a reason; when the date passes it is
  open again;
- resolved: the condition no longer holds (recorded automatically, with the time). If it
  recurs it opens again as a fresh risk.
"""

import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from relay.audit import service as audit
from relay.catalog.models import OwnershipAssignment, OwnershipAssignmentChange, Responsibility
from relay.catalog.service import active_at, assignee_views
from relay.directory.models import Person, Team
from relay.identity.models import Membership
from relay.identity.workspace_access import WorkspaceAccess
from relay.policy.permissions import Permission, authorize, visible
from relay.risks.models import RiskRecord
from relay.shared.api_types import LongText, StrictInput
from relay.shared.errors import ApiError

Severity = Literal["high", "medium", "low"]
RiskStatus = Literal["open", "acknowledged", "accepted", "resolved"]
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
ACTIVE: tuple[RiskStatus, ...] = ("open", "acknowledged")


class RiskDecisionIn(StrictInput):
    key: str
    action: Literal["acknowledge", "accept", "reopen"]
    note: LongText | None = None
    accepted_until: AwareDatetime | None = None


class RiskSubjectView(BaseModel):
    id: uuid.UUID
    name: str
    criticality: str


class RiskView(BaseModel):
    key: str
    rule: str
    severity: Severity
    title: str
    explanation: str
    recommendation: str
    responsibility: RiskSubjectView | None = None
    person_id: uuid.UUID | None = None
    person_name: str | None = None
    related: list[RiskSubjectView] = []
    status: RiskStatus = "open"
    note: str | None = None
    accepted_until: datetime | None = None
    decided_by_name: str | None = None
    decided_at: datetime | None = None
    first_detected_at: datetime | None = None


class ResolvedRiskView(BaseModel):
    key: str
    rule: str
    severity: Severity
    title: str
    subject: str | None
    first_detected_at: datetime
    resolved_at: datetime


class RecentChangeView(BaseModel):
    changed_at: datetime
    change_type: str
    role: str
    assignee_name: str
    responsibility_id: uuid.UUID
    responsibility_name: str
    reason: str | None


class OverviewView(BaseModel):
    active_responsibilities: int
    without_primary_owner: int
    critical_without_backup: int
    open_risks: int
    acknowledged_risks: int
    accepted_risks: int
    risks_by_severity: dict[str, int]
    top_risks: list[RiskView]
    recent_changes: list[RecentChangeView]


async def _detect(access: WorkspaceAccess) -> list[RiskView]:
    session = access.session
    now = datetime.now(UTC)
    responsibilities = list(
        await session.scalars(
            select(Responsibility).where(
                visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
                Responsibility.status == "active",
            )
        )
    )
    assignments = list(
        await session.scalars(
            select(OwnershipAssignment).where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignment.tenant_id),
                active_at(now),
            )
        )
    )
    people = {
        p.id: p
        for p in await session.scalars(
            select(Person).where(visible(access, Permission.DIRECTORY_READ, Person.tenant_id))
        )
    }
    teams = {
        t.id: t
        for t in await session.scalars(
            select(Team).where(visible(access, Permission.DIRECTORY_READ, Team.tenant_id))
        )
    }

    by_responsibility: dict[uuid.UUID, list[OwnershipAssignment]] = defaultdict(list)
    for a in assignments:
        by_responsibility[a.responsibility_id].append(a)

    risks: list[RiskView] = []
    sole_owner_of: dict[uuid.UUID, list[Responsibility]] = defaultdict(list)

    for r in responsibilities:
        subject = RiskSubjectView(id=r.id, name=r.name, criticality=r.criticality)
        mine = by_responsibility.get(r.id, [])
        roles = {a.role for a in mine}
        holders = {a.person_id or a.team_id for a in mine}

        if "primary" not in roles:
            risks.append(
                RiskView(
                    key=f"no_primary_owner:{r.id}",
                    rule="no_primary_owner",
                    severity="high"
                    if r.criticality in ("critical", "high")
                    else "medium"
                    if r.criticality == "standard"
                    else "low",
                    title="No primary owner",
                    explanation=f"Nobody is currently accountable for “{r.name}”.",
                    recommendation="Assign a primary owner.",
                    responsibility=subject,
                )
            )
        if "backup" not in roles:
            risks.append(
                RiskView(
                    key=f"no_backup:{r.id}",
                    rule="no_backup",
                    severity="high"
                    if r.criticality == "critical"
                    else "medium"
                    if r.criticality == "high"
                    else "low",
                    title="No backup",
                    explanation=f"If the current owner of “{r.name}” is unavailable, "
                    "nobody is designated to cover.",
                    recommendation="Assign a backup owner.",
                    responsibility=subject,
                )
            )
        if r.criticality == "critical" and len(holders) < 2 and "primary" in roles:
            risks.append(
                RiskView(
                    key=f"insufficient_critical_coverage:{r.id}",
                    rule="insufficient_critical_coverage",
                    severity="high",
                    title="Critical responsibility with a single owner",
                    explanation=f"“{r.name}” is critical but only one person or team covers it.",
                    recommendation="Add a backup or co-owner.",
                    responsibility=subject,
                )
            )
        for a in mine:
            holder = people.get(a.person_id) if a.person_id else teams.get(a.team_id)  # type: ignore[arg-type]
            if holder is not None and holder.status == "archived":
                name = holder.display_name if isinstance(holder, Person) else holder.name
                risks.append(
                    RiskView(
                        key=f"inactive_owner:{a.id}",
                        rule="inactive_owner",
                        severity="high" if r.criticality in ("critical", "high") else "medium",
                        title="Owner is archived",
                        explanation=f"{name} is archived but still holds the "
                        f"{a.role.replace('_', '-')} role on “{r.name}”.",
                        recommendation="End the assignment and assign an active owner.",
                        responsibility=subject,
                    )
                )
        if len(holders) == 1 and mine[0].person_id is not None:
            sole_owner_of[mine[0].person_id].append(r)

    for person_id, owned in sole_owner_of.items():
        if len(owned) < 2:
            continue
        person = people.get(person_id)
        name = person.display_name if person else "A person"
        risks.append(
            RiskView(
                key=f"single_person_dependency:{person_id}",
                rule="single_person_dependency",
                severity="high"
                if any(r.criticality in ("critical", "high") for r in owned)
                else "medium",
                title="Single-person dependency",
                explanation=f"{name} is the only owner of {len(owned)} responsibilities; "
                "their absence leaves all of them uncovered.",
                recommendation="Spread coverage by adding backups to these responsibilities.",
                person_id=person_id,
                person_name=name,
                related=[
                    RiskSubjectView(id=r.id, name=r.name, criticality=r.criticality) for r in owned
                ],
            )
        )

    risks.sort(key=lambda x: (_SEVERITY_ORDER[x.severity], x.title, x.key))
    return risks


def _subject(risk: RiskView) -> str | None:
    return risk.responsibility.name if risk.responsibility else risk.person_name


async def _member_names(access: WorkspaceAccess) -> dict[uuid.UUID, str]:
    rows = await access.session.execute(
        select(Membership.user_id, Membership.display_name, Membership.email).where(
            visible(access, Permission.MEMBER_READ, Membership.tenant_id)
        )
    )
    return {user_id: name or email or "Member" for user_id, name, email in rows}


async def _reconcile(access: WorkspaceAccess, detected: list[RiskView]) -> None:
    """Bring `risk_record` in line with what is detected now and annotate each risk.

    Idempotent and safe under concurrent reads (insert-if-absent, then row locks; rows
    are only updated when something changed). Lifecycle changes the system makes
    (resolved, recurred, acceptance expired) are audited with a system actor.
    """
    session = access.session
    now = datetime.now(UTC)
    if detected:
        await session.execute(
            insert(RiskRecord)
            .values(
                [
                    {
                        "tenant_id": access.tenant_id,
                        "risk_key": r.key,
                        "rule": r.rule,
                        "severity": r.severity,
                        "title": r.title,
                        "subject": _subject(r),
                    }
                    for r in detected
                ]
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "risk_key"])
        )
    records = {
        r.risk_key: r
        for r in await session.scalars(
            select(RiskRecord)
            .where(visible(access, Permission.RESPONSIBILITY_READ, RiskRecord.tenant_id))
            .order_by(RiskRecord.id)
            .with_for_update()
        )
    }

    def system_event(record: RiskRecord, action: str) -> None:
        audit.record(
            session,
            tenant_id=access.tenant_id,
            action=action,
            actor_user_id=None,
            target_type="risk",
            target_id=record.id,
            details={"rule": record.rule},
        )

    for risk in detected:
        record = records[risk.key]
        labels = (risk.severity, risk.title, _subject(risk))
        if (record.severity, record.title, record.subject) != labels:
            record.severity, record.title, record.subject = labels
        if record.status == "resolved":
            record.status, record.resolved_at, record.first_detected_at = "open", None, now
            record.note = record.accepted_until = record.decided_at = None
            record.decided_by = None
            record.updated_at = now
            system_event(record, "risk.recurred")
        elif record.status == "accepted" and record.accepted_until and record.accepted_until <= now:
            record.status, record.updated_at = "open", now
            system_event(record, "risk.acceptance_expired")
    current = {r.key for r in detected}
    for key, record in records.items():
        if key not in current and record.status != "resolved":
            record.status, record.resolved_at, record.updated_at = "resolved", now, now
            system_event(record, "risk.resolved")

    names = await _member_names(access)
    for risk in detected:
        record = records[risk.key]
        risk.status = record.status  # type: ignore[assignment]
        risk.note = record.note
        risk.accepted_until = record.accepted_until
        risk.decided_by_name = names.get(record.decided_by) if record.decided_by else None
        risk.decided_at = record.decided_at
        risk.first_detected_at = record.first_detected_at


async def compute_risks(
    access: WorkspaceAccess, *, statuses: tuple[RiskStatus, ...] | None = ACTIVE
) -> list[RiskView]:
    """Detected risks with their lifecycle state; `statuses=None` returns every one."""
    authorize(access, Permission.RESPONSIBILITY_READ)
    detected = await _detect(access)
    await _reconcile(access, detected)
    return [r for r in detected if statuses is None or r.status in statuses]


async def resolved_risks(access: WorkspaceAccess) -> list[ResolvedRiskView]:
    await compute_risks(access)  # reconcile first so freshly fixed risks appear
    records = await access.session.scalars(
        select(RiskRecord)
        .where(
            visible(access, Permission.RESPONSIBILITY_READ, RiskRecord.tenant_id),
            RiskRecord.status == "resolved",
        )
        .order_by(RiskRecord.resolved_at.desc())
        .limit(100)
    )
    return [
        ResolvedRiskView(
            key=r.risk_key,
            rule=r.rule,
            severity=r.severity,
            title=r.title,
            subject=r.subject,
            first_detected_at=r.first_detected_at,
            resolved_at=r.resolved_at or r.updated_at,
        )
        for r in records
    ]


async def decide_risk(access: WorkspaceAccess, data: RiskDecisionIn) -> RiskView:
    authorize(access, Permission.RESPONSIBILITY_MANAGE)
    detected = {r.key for r in await compute_risks(access, statuses=None)}
    record = await access.session.scalar(
        select(RiskRecord).where(
            RiskRecord.risk_key == data.key,
            visible(access, Permission.RESPONSIBILITY_READ, RiskRecord.tenant_id),
        )
    )
    if record is None or data.key not in detected:
        raise ApiError(404, "risk_not_found", "This risk is not currently detected.")
    now = datetime.now(UTC)
    if data.action == "accept":
        if not data.note:
            raise ApiError(422, "reason_required", "Accepting a risk needs a reason.")
        if data.accepted_until is None or data.accepted_until <= now:
            raise ApiError(422, "invalid_until", "Accept the risk until a future date.")
        if (data.accepted_until - now).days > 366:
            raise ApiError(422, "invalid_until", "Accept a risk for at most a year.")
        record.status, record.accepted_until = "accepted", data.accepted_until
    elif data.action == "acknowledge":
        if record.status == "acknowledged":
            raise ApiError(409, "already_acknowledged", "This risk is already acknowledged.")
        record.status, record.accepted_until = "acknowledged", None
    else:
        if record.status == "open":
            raise ApiError(409, "already_open", "This risk is already open.")
        record.status, record.accepted_until = "open", None
    record.note = data.note or None
    record.decided_by, record.decided_at, record.updated_at = access.user_id, now, now
    audit.record(
        access.session,
        tenant_id=access.tenant_id,
        action={"accept": "risk.accepted", "acknowledge": "risk.acknowledged"}.get(
            data.action, "risk.reopened"
        ),
        actor_user_id=access.user_id,
        target_type="risk",
        target_id=record.id,
        details={
            "rule": record.rule,
            "accepted_until": record.accepted_until.isoformat() if record.accepted_until else None,
        },
    )
    await access.session.flush()
    return next(r for r in await compute_risks(access, statuses=None) if r.key == data.key)


async def overview(access: WorkspaceAccess) -> OverviewView:
    every = await compute_risks(access, statuses=None)
    risks = [r for r in every if r.status in ACTIVE]
    session = access.session
    active = list(
        await session.scalars(
            select(Responsibility.id).where(
                visible(access, Permission.RESPONSIBILITY_READ, Responsibility.tenant_id),
                Responsibility.status == "active",
            )
        )
    )
    rows = (
        await session.execute(
            select(OwnershipAssignmentChange, OwnershipAssignment, Responsibility.name)
            .join(
                OwnershipAssignment,
                OwnershipAssignment.id == OwnershipAssignmentChange.assignment_id,
            )
            .join(Responsibility, Responsibility.id == OwnershipAssignmentChange.responsibility_id)
            .where(
                visible(access, Permission.RESPONSIBILITY_READ, OwnershipAssignmentChange.tenant_id)
            )
            .order_by(
                OwnershipAssignmentChange.changed_at.desc(), OwnershipAssignmentChange.id.desc()
            )
            .limit(8)
        )
    ).all()
    assignees = await assignee_views(session, [a for _, a, _ in rows])
    by_severity = {s: sum(1 for r in risks if r.severity == s) for s in ("high", "medium", "low")}
    return OverviewView(
        active_responsibilities=len(active),
        without_primary_owner=sum(1 for r in risks if r.rule == "no_primary_owner"),
        critical_without_backup=sum(
            1
            for r in risks
            if r.rule == "no_backup"
            and r.responsibility
            and r.responsibility.criticality == "critical"
        ),
        open_risks=len(risks),
        acknowledged_risks=sum(1 for r in risks if r.status == "acknowledged"),
        accepted_risks=sum(1 for r in every if r.status == "accepted"),
        risks_by_severity=by_severity,
        top_risks=risks[:5],
        recent_changes=[
            RecentChangeView(
                changed_at=c.changed_at,
                change_type=c.change_type,
                role=a.role,
                assignee_name=assignees[a.person_id or a.team_id].name,  # type: ignore[index]
                responsibility_id=c.responsibility_id,
                responsibility_name=name,
                reason=c.reason,
            )
            for c, a, name in rows
        ],
    )
