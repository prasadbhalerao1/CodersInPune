# ADR 0002 — GitHub reconciliation every 6 hours, not 15 minutes

- Status: accepted (2026-11-10)
- Relates to: Round 1 plan §9.3 improvement 1 ("15-minute reconciliation sweep")

## Context
The Round 1 plan promised a 15-minute sweep for missed webhook events. Webhooks now arrive
authenticated, deduplicated and order-safe through the web proxy, so the sweep is only a
safety net. A full reconciliation lists every repository and reads CODEOWNERS and catalog
files per installation; doing that every 15 minutes would spend most of a larger
installation's GitHub API rate limit on data that rarely changes.

## Decision
`relay.github_reconcile` runs at minute 17 every 6 hours (`jobs/app.py`). Structural
webhook events (installation, repositories, teams, membership, ownership-file pushes)
trigger an immediate re-sync of that installation, and "Sync now" is always available.

## Consequences
A missed PR or issue event is picked up within 6 hours instead of 15 minutes. Ownership
data is unaffected, because it never changes from events alone. The interval is one cron
expression if a deployment needs it tighter.
