# Requirement gaps and contradictions

Source of truth: SRS v1.0 (`docs/round1/relay_srs_prd.md`, 8 Nov 2026) for requirements;
Decision Register v0.1 and ADRs for technical constraints. Full evidence per requirement:
[REQUIREMENT_TRACEABILITY.csv](REQUIREMENT_TRACEABILITY.csv) (207 rows: 137 FR, 13 NFR,
10 AC, 47 audit IDs for the unnumbered NFR bullets in SRS §15.3–15.8).

## Document precedence used

1. Problem statement → 2. SRS v1.0 (combined PRD + SRS; no separate PRD exists) →
3. Decision Register + ADRs → 4. Implementation Plan → 5. Competitive study (ideas only) →
6. Earlier reports in this repo (treated as claims, re-verified).

The Decision Register is marked "v0.1 — for founder review", yet `CLAUDE.md` treats it as
binding. In practice the founder has built against it for all milestones, so it is treated
as approved except where a decision is explicitly "Founder approval" pending (C-06).

## Status summary

| Status | Count |
|---|---|
| Implemented and verified | 173 |
| Partially implemented | 14 |
| Implemented but insufficiently verified | 8 |
| Blocked by external dependency | 7 |
| Proposed deferment | 4 |
| Contradictory / needs decision | 1 |

Of 108 P0 functional requirements, 104 are implemented and verified, 3 are partial
(FR-IAM-005, FR-ASSET-004, FR-INT-010) and 1 awaits real-account verification (FR-INT-002).
All 10 acceptance criteria (AC-01–AC-10) pass at integration level; AC-01 and AC-08 also
pass in the browser on a production build, and AC-02/AC-07 against the live Gemini API.

## Partially implemented

| ID | Pri | Gap | Disposition |
|---|---|---|---|
| FR-IAM-005 | P0 | One role per membership; scoping only via `team_manager` | Accept for pilot; per-resource grants if a customer needs them |
| FR-INT-010 | P0 | Source ACLs not mirrored per user; visibility is workspace/managers | Accept for internal pilot with org-shared sources; fix before customers with sensitive repos |
| FR-ORG-004 | P1 | Membership history only in the audit log | Accept |
| FR-ASSET-004 | P0 | No direct asset↔task link | Accept (reach via case scope) |
| FR-ASSET-005 | P1 | Free key/value metadata, no typed schemas | Defer |
| FR-CI-009 | P1 | Rule severities fixed in code | Accept |
| FR-AGENT-012 | P1 | Scripted regression tests, no labelled quality dataset | **Build before customer pilot** |
| FR-ADMIN-007 | P1 | Audit retention not configurable | Decision C-02 |
| NFR-SCAL-A03/A06 | — | Concurrency serialised, not configurable/fair-share | Accept |
| NFR-PRIV-A02/A06/A07 | — | ACL mirroring; legal hold; per-class retention | See FR-INT-010, C-02 |
| NFR-OBS-A01 | — | No metrics/alerting endpoint | Platform log alerts for pilot; add later |

## Implemented but insufficiently verified

FR-NOTIF-002 (no real email sent), NFR-REL-002 (drill run locally, not on a production
host), NFR-SCAL-A01/A07, NFR-SEC-A08 (CI not run), NFR-UX-A03/A04/A07 (no user or
assistive-technology testing).

## Blocked by external dependency

FR-IAM-008 (SSO needs a WorkOS org + IdP), FR-INT-002 (real-account sync per provider not
re-run in this audit), NFR-REL-001 (needs a hosted deployment), NFR-SEC-A01/A02 (hosting),
NFR-PRIV-A09 (AI provider data terms), NFR-PRIV-A10 (legal review).

## Proposed deferments

| ID | Reason it does not undermine the product promise |
|---|---|
| FR-ASSET-007 | MAY requirement; workflows complete without a graph |
| FR-INT-013 | P2 later-phase connectors |
| FR-NOTIF-006 | P2 digests |
| NFR-SCAL-A05 | Vector search not adopted (D10) |

## Contradiction register

| ID | Conflict | Sources | Consequence | Recommendation |
|---|---|---|---|---|
| C-01 | Default LLM provider and its data terms | DR D10 (Anthropic, terms verified) vs ADR 0001 (Gemini first) | "Not used for training" is only verified for Anthropic | Keep ADR 0001 for development; **verify Gemini paid-tier terms or switch to a provider with verified terms before real data** |
| C-02 | Audit and closed-case retention | DR D13 (audit 2 y, configurable 1–7; closed cases 2 y) vs code (kept until workspace deletion) and SRS FR-ADMIN-007 | Longer retention than the approved default | Founder + legal decision; implementing deletion of audit records is irreversible, so it was not done unilaterally |
| C-03 | Semantic retrieval | SRS FR-SEARCH-005 (SHOULD hybrid) vs DR D10 (FTS only until post-pilot) | No semantic search | DR governs (later, more specific decision); revisit with evals |
| C-04 | Reconciliation interval | Round 1 plan §9.3 (15 min) vs ADR 0002 (6 h) | Missed webhooks fixed within 6 h | ADR 0002 governs |
| C-05 | Cancelling a running case | Lifecycle forbids `executing → cancelled` but allows `blocked → cancelled` for a case blocked during execution | A partly executed handover can be cancelled with ownership already changed | Product decision: either require reopening via a "roll back" path or keep and show applied changes on cancel |
| C-06 | Decision approval state | DR header "v0.1 for founder review"; D10, D13, D19 "Founder approval" | Some built behaviour rests on unapproved decisions | Founder to mark approved/changed decisions |
| C-07 | Availability vs hosting | NFR-REL-001 (99.5%) vs deployment.md demo tier (Render free, spins down) | Free tier cannot meet the target | Production must use paid instances; free tier for demos only (stated in deployment.md) |
| C-08 | Multiple roles per user | SRS FR-IAM-005 / §5.2 vs single role per membership | Multi-hat users take the broader role | Accept for pilot; record as known limitation |

## Requirements without measurable acceptance criteria (proposed targets)

These are **proposals**, not existing requirements.

| Requirement | Proposed measurable target |
|---|---|
| FR-CI-009 explainable prioritisation | Every risk shows its rule, inputs and severity reason; 100% coverage checked by test |
| FR-AGENT-012 evaluation | ≥ 30 labelled cases; citation validity ≥ 95%; restricted leak = 0; conflict recall ≥ 90% |
| NFR-SCAL-A01 horizontal scaling | 2 API replicas behind a load balancer pass the e2e suite with shared rate limits |
| NFR-OBS-A01 | Alert within 5 min when `/health/ready` fails or 5xx rate > 2% over 5 min |
| NFR-UX-A02 case creation | A first-time manager creates a departure case in < 3 min unaided (moderated test, n ≥ 5) |
| NFR-REL-002 restore | Monthly drill restores within 30 min with matching row counts |
