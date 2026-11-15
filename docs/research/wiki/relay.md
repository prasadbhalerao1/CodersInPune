---
title: "Relay (as built)"
type: concept
language: en
created: 2026-11-12
modified: 2026-11-12
tags: [relay, product]
aliases: []
summary: "What Relay actually does today, verified from the repository and its tests."
confidence: high
---

# Relay (as built)

## Definition
Organisational continuity platform: one record of who is accountable for what, the evidence behind it, a deterministic forecast of absences, and audited handovers. The database is the source of truth; AI only proposes cited drafts and answers.

## Key Properties (verified in code and tests, 2026-11-12)
- Responsibilities with primary / co-owner / backup assignments for people or teams; ownership history; review cadence 7–730 days (`catalog/`).
- Dependencies between responsibilities and assets: depends_on, feeds, escalates_to, shares_access (`catalog/models.py`).
- Risk rules: no owner, no backup, single-person dependency, inactive owner, stale knowledge; Continuity Debt as a sum of explained components (`risks/`, `insights/`).
- Key-person exposure: people who are the only holder of work, ranked, linked to the simulator (`insights/service.py::_key_people`).
- GitHub ownership suggestions from CODEOWNERS, catalog-info.yaml, maintainers and activity; they change nothing until accepted (`integrations/github/`).
- Linear and Notion connectors: read-only, encrypted credentials, health and retry states.
- Memory Replay, What If? simulator, Handover Copilot with brief coverage, version comparison and cited Q&A.
- Cases: plan, approve, execute, verify with separation of duties; append-only audit; transactional outbox.
- Tenant isolation by forced PostgreSQL row-level security and a restricted application role.

## Known gaps (verified)
- No Slack or Teams surface; no HRIS trigger; no calendar or leave feed.
- Ownership drift between Relay and source systems surfaces only as per-repository suggestions, not as a named conflict view.
- ~~No post-transfer follow-up~~ Built 2026-11-12: follow-through per transferred responsibility (`continuity/follow_through.py`).

## Related Concepts
- [[service-catalogues]] · [[knowledge-management]] · [[offboarding-knowledge-transfer]] · [[ai-knowledge-systems]] · [[incident-and-oncall]] · [[synth-2026-11-12-relay-competitive-position]]

## References
- Repository: `backend/src/relay`, `docs/JUDGE_GUIDE.md`
