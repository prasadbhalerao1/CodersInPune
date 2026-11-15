"""Rule-based analysis: works with no model configured, and is never replaced by AI.

Every claim here is a `direct_fact` (read straight from a record), a `rule` (Relay's
continuity rules applied to records) or a `human_decision` (an approval someone made),
and cites the records it came from.
"""

import re
from datetime import UTC, datetime

from relay.intelligence.evidence import Pool, PoolItem
from relay.intelligence.validate import ValidClaim, audience_of


def _claim(
    pool: Pool,
    kind: str,
    claim_type: str,
    text: str,
    items: list[PoolItem],
    timeline_at: datetime | None = None,
) -> ValidClaim:
    refs = [i.ref for i in items]
    return ValidClaim(
        kind=kind,
        claim_type=claim_type,
        text=text,
        confidence="high",
        audience=audience_of(pool, refs),
        refs=refs,
        timeline_at=timeline_at,
    )


def _words(title: str) -> frozenset[str]:
    return frozenset(w for w in re.findall(r"[a-z0-9]+", title.lower()) if len(w) > 3)


def analyse(pool: Pool) -> list[ValidClaim]:
    now = datetime.now(UTC)
    claims: list[ValidClaim] = []
    by_kind: dict[str, list[PoolItem]] = {}
    for item in pool.items:
        by_kind.setdefault(str(item.facts.get("kind")), []).append(item)
    knowledge = by_kind.get("knowledge", [])
    work = by_kind.get("work", [])

    for r in by_kind.get("responsibility", []):
        f = r.facts
        rid = f["responsibility_id"]
        claims.append(_claim(pool, "finding", "direct_fact", _ownership_fact(r), [r]))
        if not f["recipient"] and not f["exception"]:
            claims.append(
                _claim(pool, "missing", "rule", f"No one is planned to take over {r.title}.", [r])
            )
        roles = f["roles"]
        if "primary" not in roles:  # type: ignore[operator]
            claims.append(
                _claim(pool, "missing", "rule", f"{r.title} has no current primary owner.", [r])
            )
        if f["criticality"] in ("critical", "high") and "backup" not in roles:  # type: ignore[operator]
            claims.append(
                _claim(
                    pool,
                    "missing",
                    "rule",
                    f"{r.title} is {f['criticality']} but has no backup owner.",
                    [r],
                )
            )
        mine = [k for k in knowledge if k.facts["responsibility_id"] == rid]
        if not mine:
            claims.append(
                _claim(pool, "missing", "rule", f"Nothing is written down for {r.title}.", [r])
            )
        stale = [k for k in mine if k.facts["stale"]]
        if stale:
            claims.append(
                _claim(
                    pool,
                    "finding",
                    "rule",
                    f"{len(stale)} knowledge item(s) for {r.title} are overdue for review.",
                    [r, *stale[:5]],
                )
            )
        open_work = [w for w in work if w.facts["responsibility_id"] == rid and w.facts["open"]]
        if open_work:
            claims.append(
                _claim(
                    pool,
                    "work",
                    "direct_fact",
                    f"{len(open_work)} open pull request(s)/issue(s) are linked to {r.title}.",
                    open_work[:8],
                )
            )
        # Two knowledge items about the same thing that disagree need a person to check.
        for i, a in enumerate(mine):
            for b in mine[i + 1 :]:
                wa, wb = _words(a.title), _words(b.title)
                # Compare content, not revisions: Relay items written together share one.
                if wa and wb and len(wa & wb) / len(wa | wb) >= 0.6 and a.excerpt != b.excerpt:
                    claims.append(
                        _claim(
                            pool,
                            "conflict",
                            "rule",
                            f"'{a.title}' and '{b.title}' cover the same topic; check which "
                            "one is current.",
                            [a, b],
                        )
                    )

    for t in by_kind.get("task", []):
        due = t.facts.get("due_at")
        if t.facts["status"] == "open" and isinstance(due, datetime) and due < now:
            claims.append(_claim(pool, "finding", "rule", f"Task '{t.title}' is overdue.", [t]))
    for c in by_kind.get("criterion", []):
        if c.facts["mandatory"] and c.facts["status"] not in ("met", "waived"):
            claims.append(
                _claim(
                    pool,
                    "missing",
                    "rule",
                    f"Mandatory readiness criterion '{c.title}' is not met yet.",
                    [c],
                )
            )
    for a in by_kind.get("approval", []):
        claims.append(_claim(pool, "decision", "human_decision", a.excerpt[:400], [a], a.source_ts))
    return claims


def _ownership_fact(r: PoolItem) -> str:
    """One readable sentence from the responsibility's recorded facts."""
    f = r.facts
    held = f.get("owners") or "nobody"
    handover = (
        f"It goes to {f['recipient']} in this handover"
        if f.get("recipient")
        else "No recipient is chosen yet"
    )
    notes = f" Notes: {f['notes']}" if f.get("notes") else ""
    return (
        f"{r.title} ({f['criticality']} criticality) is held today by {held}. {handover}.{notes}"
    )[:600]
