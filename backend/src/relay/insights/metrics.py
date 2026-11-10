"""Reproducible trend metrics with their definitions.

Every metric says exactly what it counts: definition, period, numerator, denominator,
sample size, data coverage and limitations. Nothing is estimated or backfilled: a period
without data reports no value rather than zero. No metric ranks or scores individuals.

Snapshots store the metrics as computed at a moment (append-only), so a trend is a list
of snapshots, each computed the same way over its own period.
"""

import uuid
from datetime import UTC, datetime, timedelta
from statistics import median, quantiles

from pydantic import BaseModel
from sqlalchemy import select

from relay.catalog.models import KnowledgeItem
from relay.continuity.models import CaseKnowledge, CaseReadinessCriterion, ContinuityCase
from relay.governance.models import ConnectorRun, MetricSnapshot
from relay.identity.workspace_access import WorkspaceAccess
from relay.intelligence.models import Proposal
from relay.policy.permissions import Permission, authorize, visible
from relay.shared.errors import ApiError

DEFAULT_DAYS = 90


class MetricView(BaseModel):
    key: str
    name: str
    definition: str
    numerator: int
    denominator: int
    value: float | None  # numerator / denominator; None when there is no data
    unit: str
    sample_size: int
    coverage: str
    limitations: str
    distribution: dict[str, float] = {}


class MetricsView(BaseModel):
    period_start: datetime
    period_end: datetime
    metrics: list[MetricView]


class SnapshotView(BaseModel):
    id: uuid.UUID
    period_start: datetime
    period_end: datetime
    trigger: str
    taken_at: datetime
    metrics: list[MetricView]


def _ratio(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


async def compute(
    access: WorkspaceAccess, *, days: int = DEFAULT_DAYS, now: datetime | None = None
) -> MetricsView:
    authorize(access, Permission.INSIGHTS_READ)
    if not 7 <= days <= 365:
        raise ApiError(422, "invalid_period", "Choose a period of 7 to 365 days.")
    end = now or datetime.now(UTC)
    start = end - timedelta(days=days)
    session = access.session
    in_case = visible(access, Permission.CASE_READ, ContinuityCase.tenant_id)

    closed = list(
        await session.scalars(
            select(ContinuityCase).where(
                in_case,
                ContinuityCase.status == "completed",
                ContinuityCase.closed_at >= start,
                ContinuityCase.closed_at < end,
            )
        )
    )
    durations = [
        (c.closed_at - c.created_at).total_seconds() / 86400 for c in closed if c.closed_at
    ]
    buckets = {"under_7_days": 0.0, "7_to_14_days": 0.0, "14_to_30_days": 0.0, "over_30_days": 0.0}
    for d in durations:
        key = (
            "under_7_days"
            if d < 7
            else "7_to_14_days"
            if d < 14
            else "14_to_30_days"
            if d < 30
            else "over_30_days"
        )
        buckets[key] += 1
    distribution = dict(buckets)
    if durations:
        distribution["median_days"] = round(median(durations), 1)
        if len(durations) >= 2:
            distribution["p90_days"] = round(quantiles(durations, n=10)[-1], 1)

    criteria = list(
        await session.scalars(
            select(CaseReadinessCriterion).where(
                CaseReadinessCriterion.case_id.in_([c.id for c in closed]),
                CaseReadinessCriterion.mandatory.is_(True),
            )
        )
    )
    met = sum(1 for c in criteria if c.status == "met")

    missing = list(
        await session.scalars(
            select(CaseKnowledge).where(
                visible(access, Permission.CASE_READ, CaseKnowledge.tenant_id),
                CaseKnowledge.outcome == "missing",
                CaseKnowledge.recorded_at >= start,
                CaseKnowledge.recorded_at < end,
            )
        )
    )
    resolved = 0
    for gap in missing:
        written = await session.scalar(
            select(KnowledgeItem.id)
            .where(
                KnowledgeItem.responsibility_id == gap.responsibility_id,
                KnowledgeItem.created_at > gap.recorded_at,
                KnowledgeItem.status == "active",
            )
            .limit(1)
        )
        resolved += written is not None

    runs = list(
        await session.scalars(
            select(ConnectorRun).where(
                visible(access, Permission.INSIGHTS_READ, ConnectorRun.tenant_id),
                ConnectorRun.status != "skipped",
                ConnectorRun.finished_at >= start,
                ConnectorRun.finished_at < end,
            )
        )
    )
    failed = sum(1 for r in runs if r.status == "error")

    reviewed = list(
        await session.scalars(
            select(Proposal).where(
                visible(access, Permission.INSIGHTS_READ, Proposal.tenant_id),
                Proposal.status != "pending",
                Proposal.reviewed_at >= start,
                Proposal.reviewed_at < end,
            )
        )
    )
    accepted = sum(1 for p in reviewed if p.status in ("accepted", "edited"))
    edited = sum(1 for p in reviewed if p.status == "edited")

    return MetricsView(
        period_start=start,
        period_end=end,
        metrics=[
            MetricView(
                key="handover_cycle_time",
                name="Handover cycle time",
                definition="Days from a case being opened to being completed, for cases "
                "completed in the period.",
                numerator=len(durations),
                denominator=len(durations),
                value=distribution.get("median_days"),
                unit="median days",
                sample_size=len(durations),
                coverage="Completed cases only; cancelled cases are excluded.",
                limitations="Cases reopened after completion count from their first opening.",
                distribution=distribution,
            ),
            MetricView(
                key="readiness_completion",
                name="Readiness completion rate",
                definition="Mandatory readiness checks met (not waived) on cases completed in "
                "the period, out of all their mandatory checks.",
                numerator=met,
                denominator=len(criteria),
                value=_ratio(met, len(criteria)),
                unit="share",
                sample_size=len(closed),
                coverage="Cases completed in the period.",
                limitations="Waived checks count against the rate; that's deliberate.",
            ),
            MetricView(
                key="knowledge_gap_resolution",
                name="Knowledge gap resolution rate",
                definition="Knowledge recorded as missing during a handover in the period that "
                "was later written for the same responsibility.",
                numerator=resolved,
                denominator=len(missing),
                value=_ratio(resolved, len(missing)),
                unit="share",
                sample_size=len(missing),
                coverage="Gaps recorded through case handovers only.",
                limitations="Counts any later knowledge for the responsibility as a resolution, "
                "even if it covers a different topic.",
            ),
            MetricView(
                key="integration_failure_rate",
                name="Integration sync failure rate",
                definition="Sync runs that failed, out of all sync runs in the period "
                "(paused runs excluded).",
                numerator=failed,
                denominator=len(runs),
                value=_ratio(failed, len(runs)),
                unit="share",
                sample_size=len(runs),
                coverage="Runs recorded since sync history was introduced.",
                limitations="Retried transient failures that later succeeded are not counted "
                "as failures.",
            ),
            MetricView(
                key="agent_acceptance",
                name="AI proposal acceptance rate",
                definition="AI proposals accepted (as is or after an edit), out of all "
                "proposals reviewed in the period.",
                numerator=accepted,
                denominator=len(reviewed),
                value=_ratio(accepted, len(reviewed)),
                unit="share",
                sample_size=len(reviewed),
                coverage="Reviewed proposals; pending ones are excluded.",
                limitations=f"{edited} of the accepted proposals needed a correction before "
                "acceptance (the correction rate).",
                distribution={"corrected": float(edited)},
            ),
        ],
    )


async def take_snapshot(
    access: WorkspaceAccess, *, days: int = DEFAULT_DAYS, trigger: str = "manual"
) -> SnapshotView:
    authorize(access, Permission.POLICY_MANAGE)
    view = await compute(access, days=days)
    row = MetricSnapshot(
        tenant_id=access.tenant_id,
        period_start=view.period_start,
        period_end=view.period_end,
        metrics=[m.model_dump() for m in view.metrics],
        trigger=trigger,
        taken_by=access.user_id,
    )
    access.session.add(row)
    await access.session.flush()
    await access.session.refresh(row)
    return SnapshotView(
        id=row.id,
        period_start=row.period_start,
        period_end=row.period_end,
        trigger=row.trigger,
        taken_at=row.taken_at,
        metrics=view.metrics,
    )


async def snapshots(access: WorkspaceAccess) -> list[SnapshotView]:
    authorize(access, Permission.INSIGHTS_READ)
    rows = await access.session.scalars(
        select(MetricSnapshot)
        .where(visible(access, Permission.INSIGHTS_READ, MetricSnapshot.tenant_id))
        .order_by(MetricSnapshot.taken_at.desc())
        .limit(52)
    )
    return [
        SnapshotView(
            id=r.id,
            period_start=r.period_start,
            period_end=r.period_end,
            trigger=r.trigger,
            taken_at=r.taken_at,
            metrics=[MetricView.model_validate(m) for m in r.metrics],
        )
        for r in rows
    ]
