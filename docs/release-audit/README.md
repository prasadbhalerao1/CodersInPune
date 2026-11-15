# Relay release audit (2026-11-10)

An evidence-based review of whether Relay solves its problem, meets SRS v1.0, and is
ready for production, followed by fixes for the unambiguous blockers.

**Decision: ready for a controlled internal pilot with conditions; not yet ready for a
customer pilot or production.** See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md).

| Document | Contents |
|---|---|
| [PRODUCT_VIABILITY.md](PRODUCT_VIABILITY.md) | Problem, users, scenarios A–F, wedge, viability judgement |
| [REQUIREMENT_TRACEABILITY.csv](REQUIREMENT_TRACEABILITY.csv) | All 160 SRS IDs + 47 audit IDs, with status, code, tests, gaps, actions |
| [REQUIREMENT_GAPS.md](REQUIREMENT_GAPS.md) | Partial, unverified, blocked and deferred items; contradiction register |
| [ARCHITECTURE_AND_CODE_REVIEW.md](ARCHITECTURE_AND_CODE_REVIEW.md) | Architecture, data integrity, API, frontend, AI runtime, integrations, measured performance |
| [SECURITY_AND_PRIVACY_REVIEW.md](SECURITY_AND_PRIVACY_REVIEW.md) | Threat model, findings, external assessment needs |
| [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) | Verification results, release gates, decision |
| [REMEDIATION_BACKLOG.md](REMEDIATION_BACKLOG.md) | Fixes made in this audit; prioritised remaining work |

Verification levels used: integration (real PostgreSQL, restricted app role), property
(seeded random walks), browser (Playwright on a production build with a real WorkOS
account), live provider (Gemini API on synthetic data), simulated provider (fakes for
GitHub/Linear/Notion/email), and code review. Nothing here is a penetration test, a WCAG
audit or a compliance certification.
