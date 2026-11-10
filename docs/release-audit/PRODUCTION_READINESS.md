# Production readiness

Final verification run, 2026-11-10, on `main` after all audit fixes (Windows 11, Docker
Desktop, PostgreSQL 18 container, Node 22, Python 3.14):

| Check | Result |
|---|---|
| Backend `ruff format --check`, `ruff check`, `mypy` (189 files) | Clean |
| Backend tests, real PostgreSQL as `relay_app`, migrations rebuilt base→head | **249 passed**, 1 skipped (opt-in perf) |
| Perf (`RELAY_PERF=1`, 250 people / 1,000 responsibilities / 60 cases) | All reads p95 ≤ 383 ms, writes ≤ 36 ms, search 71 ms |
| Frontend `format:check`, `lint`, `typecheck`, `build` | Clean; 60 routes built |
| Playwright on the production build (`next start`), real WorkOS account | **18 passed** (6 public, 12 signed-in) |
| Live AI (Gemini `gemini-3.5-flash-lite`, synthetic demo data) | 4 analysis runs (partial: GitHub source failing by design); citations valid; conflict flagged and planner proposals produced after fixes; key rotation observed |
| Docker images (backend, web) | Built; production-mode smoke: health 200, docs hidden, anonymous 401, JSON logs; worker starts; web serves with security headers |
| Backup/restore drill (local) | Restored counts identical; schema 0036; RLS forced on 87 tables |

## Release gates

Legend: ✅ Ready · 🟡 Ready with conditions · ❌ Not ready · 🔵 Requires external verification

### Product

| Gate | Status | Note |
|---|---|---|
| Core problem defined | ✅ | PRODUCT_VIABILITY.md |
| Target customer and roles coherent | 🟡 | Narrow to engineering teams 30–300 people |
| Critical workflows end to end | ✅ | AC-01..AC-10 pass; transfer and coverage in the browser |
| Measurable value | 🟡 | Metrics defined (Insights); no baseline from a real team |
| No developer intervention for major journeys | ✅ | Except deployment and connector app registration |
| AI outputs understandable, evidence-linked, reviewable | ✅ | Proposals modest until an eval set tunes them |
| Users can recover from failures | ✅ | Partial states, retries, reconnect, cancel/reopen |

### Functional

| Gate | Status | Note |
|---|---|---|
| No unimplemented P0 | 🟡 | 104/108 P0 FRs verified; FR-IAM-005, FR-ASSET-004, FR-INT-010 partial; FR-INT-002 external |
| No broken acceptance criteria | ✅ | |
| P1 complete or deferred | 🟡 | FR-AGENT-012 eval set outstanding |
| Every requirement traceable | ✅ | REQUIREMENT_TRACEABILITY.csv (207 rows) |

### Security

| Gate | Status | Note |
|---|---|---|
| No known critical/high code vulnerabilities | ✅ | Code review; not a pen test |
| Tenant isolation and authorization verified | ✅ | DB-level tests as the real app role |
| AI and external-write boundaries verified | ✅ | |
| Secrets/personal data handled | 🟡 | AI provider data terms unverified (S-01) |
| Retention/deletion tested | ✅ | Workspace deletion, operational retention, source purge |
| External security assessment | 🔵 | Pen test + AI red-team needed before customers |

### Reliability

| Gate | Status | Note |
|---|---|---|
| Backup and restore demonstrated | 🟡 | Local drill only; repeat on the production host |
| Worker/integration failures recover | ✅ | Outbox, stalled-job requeue, idempotent handlers |
| Migration path validated | ✅ | Round trip on every test run |
| Deployment and rollback documented | ✅ | deployment.md, deploy/README.md |
| Monitoring and alerting | ❌ | No alerting configured yet (needs a deployment) |
| No critical consistency issues | ✅ | Two consistency bugs found and fixed this cycle |

### Performance

| Gate | Status | Note |
|---|---|---|
| Budgets met at pilot scale | ✅ | Measured in-process |
| Measured on the deployed stack | 🔵 | Re-run after deployment (network + TLS) |

### Operational

| Gate | Status | Note |
|---|---|---|
| Production config complete | 🟡 | `render.yaml`, env reference; secrets to be entered |
| Reproducible deployment | ✅ | Blueprint + Compose |
| Domain/TLS clear | ✅ | |
| Backup schedule | 🟡 | Compose service / Neon PITR; unverified on host |
| Incident and rollback procedure | ✅ | docs/runbooks/incident-response.md |
| Provider limitations visible | ✅ | Health page; docs |
| Support/ownership model | ❌ | Not defined (solo founder) |

### Accessibility

| Gate | Status | Note |
|---|---|---|
| Keyboard, labels, status-not-colour, reduced motion | 🟡 | Implemented; not audited |
| WCAG 2.2 AA | 🔵 | Independent audit needed; no claim made |

## Decision

**Ready for a controlled internal pilot, with conditions.**

The core promise works end to end and is defensible: ownership moves through approved,
audited cases; handovers cite evidence and respect audience; tenant isolation and audit
integrity are enforced by the database and tested as the real application role; AI cannot
write. Performance is within the SRS budgets at pilot scale.

It is **not yet ready for a customer pilot or production** because of external and
organisational gates, not missing code:

| Blocker | Resolved by |
|---|---|
| AI provider data terms for real data (S-01, C-01) | Founder / external provider |
| Legal and privacy review; retention decision (C-02) | Legal review + product decision |
| Penetration test and AI red-team | Independent security testing |
| Restore drill and alerting on the real host | Deployment / infrastructure |
| Real-account verification of GitHub webhooks + writes, Linear, Notion, email | User configuration + external credentials |
| Source ACL mirroring stance (FR-INT-010) | Product decision (+ code if mirroring) |
| AI evaluation set | Code |
| Support and incident ownership | Organisational |

Conditions for the internal pilot: synthetic or the founder's own non-sensitive data; AI
either off or on a provider whose data terms are confirmed; one team; weekly backup
checks.

**Technical readiness ≠ external verification ≠ organisational readiness.** Relay is
technically deployable today; it still lacks independent security assurance, legal
approval and real-account verification of every connector.

## The question that matters

> Would a real organisation trust Relay to preserve and transfer critical operational
> responsibility, and what concrete evidence proves that?

For an engineering team running a supervised pilot, **yes**: the evidence is the
database-enforced isolation and append-only history (tests run as the restricted role),
the approval and readiness gates that block completion (state-machine property tests and
integration tests), the end-to-end transfer and coverage journeys passing in a real
browser on a production build, and evidence-cited handovers whose restricted content
provably does not leak. For a customer entrusting confidential data, **not yet**: that
trust requires the external verifications listed above.
