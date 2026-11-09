"""Citation rules every AI output passes before it is stored.

- A citation must point into the run's evidence pool; a claim citing anything else is
  rejected outright (it means the model invented a source).
- A claim without citations is dropped, except "missing" and "question" claims, which are
  kept with confidence `insufficient` (absence of evidence is the point).
- A conflict needs at least two distinct pieces of evidence.
- Model output is always an `ai_inference`; only deterministic rules state facts.
- The audience is the narrowest of the cited evidence (D2): one managers-only citation
  makes the whole claim managers-only.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from relay.intelligence.evidence import Pool

ClaimKind = Literal["finding", "decision", "question", "dependency", "conflict", "missing", "work"]
UNCITED_OK = ("missing", "question")


class ClaimDraft(BaseModel):
    """What a model may return for one claim."""

    kind: ClaimKind
    text: str = Field(description="One or two sentences, plain language.", max_length=1200)
    confidence: Literal["high", "medium", "low"] = "medium"
    evidence: list[str] = Field(
        default_factory=list, description="Evidence refs like E3 that support this claim."
    )
    when: datetime | None = Field(
        default=None, description="When a decision was made or a question arose, if known."
    )


@dataclass
class ValidClaim:
    kind: str
    claim_type: str
    text: str
    confidence: str
    audience: str
    refs: list[str]
    timeline_at: datetime | None = None


@dataclass
class Outcome:
    claims: list[ValidClaim] = field(default_factory=list)
    rejected: Counter[str] = field(default_factory=Counter)


def audience_of(pool: Pool, refs: list[str]) -> str:
    cited = [pool.get(r) for r in refs]
    return (
        "managers"
        if any(i is not None and i.audience == "managers" for i in cited)
        else "workspace"
    )


def validate_claims(pool: Pool, drafts: list[ClaimDraft]) -> Outcome:
    out = Outcome()
    seen: set[tuple[str, str]] = set()
    for d in drafts:
        text = " ".join(d.text.split())[:600]
        refs = list(dict.fromkeys(r.strip().upper() for r in d.evidence if r.strip()))
        if not text:
            out.rejected["empty"] += 1
            continue
        if any(pool.get(r) is None for r in refs):
            out.rejected["unknown_citation"] += 1
            continue
        if not refs and d.kind not in UNCITED_OK:
            out.rejected["uncited"] += 1
            continue
        if d.kind == "conflict" and len(refs) < 2:
            out.rejected["conflict_needs_two_sources"] += 1
            continue
        key = (d.kind, text.lower())
        if key in seen:
            out.rejected["duplicate"] += 1
            continue
        seen.add(key)
        sources = [pool.get(r) for r in refs]
        latest = max((s.source_ts for s in sources if s and s.source_ts), default=None)
        out.claims.append(
            ValidClaim(
                kind=d.kind,
                claim_type="ai_inference",
                text=text,
                confidence=d.confidence if refs else "insufficient",
                audience=audience_of(pool, refs),
                refs=refs,
                timeline_at=d.when or (latest if d.kind in ("decision", "question") else None),
            )
        )
    return out


def valid_refs(pool: Pool, refs: list[str]) -> list[str] | None:
    """Normalised refs, or None if any is outside the pool (proposals use the same rule)."""
    clean = list(dict.fromkeys(r.strip().upper() for r in refs if r.strip()))
    return None if any(pool.get(r) is None for r in clean) else clean
