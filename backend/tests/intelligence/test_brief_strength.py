"""Evidence strength is computed from the evidence and coverage, not the model's confidence."""

import uuid
from datetime import UTC, datetime, timedelta

from relay.intelligence import service as svc
from relay.intelligence.capsules import CapsulePoint, CapsuleSection, CoverageItem, strength


def _ev(age_days: int, *, changed: bool = False) -> svc.EvidenceView:
    return svc.EvidenceView(
        id=uuid.uuid4(),
        ref="E1",
        source_system="github",
        source_type="pull_request",
        title="t",
        url=None,
        revision=None,
        source_ts=datetime.now(UTC) - timedelta(days=age_days),
        excerpt="x",
        audience="workspace",
        status="active",
        changed=changed,
    )


def _point(kind: str = "work", *, evidence: list[svc.EvidenceView] | None = None) -> CapsulePoint:
    return CapsulePoint(
        key=str(uuid.uuid4()),
        text="t",
        kind=kind,
        claim_type="direct_fact",
        confidence="high",
        evidence=evidence or [],
    )


def _cover(cited: int) -> CoverageItem:
    return CoverageItem(
        responsibility_id=uuid.uuid4(), name="r", criticality="high", statements=1, cited=cited
    )


def test_fresh_cited_full_coverage_is_strong() -> None:
    s = strength(
        [CapsuleSection(heading="h", points=[_point(evidence=[_ev(10)])] * 3)], [_cover(1)]
    )
    assert s.level == "strong"
    assert (s.cited, s.fresh, s.covered, s.scope) == (3, 3, 1, 1)


def test_stale_or_conflicting_evidence_is_only_partial() -> None:
    stale = CapsuleSection(heading="h", points=[_point(evidence=[_ev(400)])] * 3)
    assert strength([stale], [_cover(1)]).level == "partial"
    conflict = CapsuleSection(
        heading="h", points=[_point(evidence=[_ev(1)]), _point("conflict", evidence=[_ev(1)])]
    )
    assert strength([conflict], [_cover(1)]).level == "partial"


def test_uncited_or_uncovered_is_weak() -> None:
    assert strength([], []).level == "weak"
    uncited = CapsuleSection(heading="h", points=[_point(), _point(), _point(evidence=[_ev(1)])])
    assert strength([uncited], [_cover(1)]).level == "weak"
    cited = CapsuleSection(heading="h", points=[_point(evidence=[_ev(1)])])
    assert strength([cited], [_cover(1), _cover(0), _cover(0)]).level == "weak"
