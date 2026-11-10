# Remediation backlog

Ordered by priority. "Owner" says who or what must resolve it.

## Done in this audit (commits on `main`, not pushed)

| Commit | Change | Requirement |
|---|---|---|
| `d5ab090` | Connector runs recorded "queued" after successful syncs (flush before refresh) | FR-INT-008 |
| `a446d18` | Record which tools each agent step called | FR-AGENT-009 |
| `c552e68` | Serialise connector syncs and AI steps per tenant | NFR-PERF-006 |
| `741d634` | Keyset pagination for responsibilities, people, assets, cases | NFR-PERF-005 |
| `1e22f11` | Conflict rule compared revisions; same-transaction items were never flagged | FR-KNOW-007, AC-07 |
| `4c07d66` | Configurable prices for models missing from the price table | FR-AGENT-011 |
| `75f965f` | Property tests over random walks of the case state machine | FR-CASE-007/008 |
| `63700d7` | Flag evidence and handovers whose sources changed after review | FR-TASK-008 |
| `13b8a02` | Risk reconcile no longer locks/rewrites unchanged rows (p95 866→342 ms) | NFR-PERF-001 |
| `01defae` | Opt-in latency benchmark at 1,000 responsibilities | NFR-PERF-001/002/004 |
| `f879fdf` | Purge source data 30 days after disconnect | FR-INT-012, D13 |
| — | Local backup/restore drill with matching counts | NFR-REL-002 |

## P0 — before any use with real customer data

| # | Item | Acceptance criteria | Owner |
|---|---|---|---|
| 1 | AI provider data terms (C-01, S-01) | Written confirmation that the provider does not train on API content for the account tier used, or switch provider; recorded in D10 | Founder (external) |
| 2 | Legal/privacy review (NFR-PRIV-A10) incl. retention C-02 | Counsel-approved retention table; DPA/subprocessor list | Founder + counsel |
| 3 | Production backups proven (NFR-REL-002) | First nightly backup on the real host restored with `deploy/restore-drill.sh`; off-host copy encrypted | Deployment |

## P1 — before a meaningful pilot

| # | Item | Acceptance criteria | Owner |
|---|---|---|---|
| 4 | Real-account verification per connector (FR-INT-002) | One real sync each for GitHub, Linear, Notion; one real GitHub webhook; one approved Linear issue write with receipt | User configuration + credentials |
| 5 | AI evaluation set (FR-AGENT-012) | ≥ 30 labelled synthetic cases; report citation validity, restricted leaks (must be 0), conflict recall; run on prompt/model change | Code |
| 6 | Handover planner usefulness | ≥ 1 accepted-quality proposal per demo analysis on the eval set | Code |
| 7 | Source ACL mirroring decision (FR-INT-010) | Either restrict imports to org-visible sources by default, or map per-user visibility for GitHub private repos | Product decision + code |
| 8 | Cancel-while-executing rule (C-05) | Documented decision; test that matches it | Product decision |
| 9 | Monitoring (NFR-OBS-A01) | Uptime check on `/health/ready`; alert on 5xx rate and worker down | Deployment |
| 10 | Run CI on a branch (NFR-SEC-A08) | SBOM, Trivy, licence jobs green; criticals fixed | User (push) |
| 11 | Usability test (NFR-UX-A02/A03) | 5 managers create a departure case and complete a handover unaided; issues logged | Product |
| 12 | Real email delivery (FR-NOTIF-002) | One Resend email received with correct content/no source text | User configuration |

## P2 — deferrable with justification

| Item | Why deferral is safe |
|---|---|
| Shared rate limiter (needed only with > 1 API replica) | Pilot runs one replica |
| Request ID propagated into job logs | Job and event IDs already correlate |
| Incremental risk table (> 3k responsibilities) | Pilot size is far below |
| Paging for teams/members/knowledge overview | Capped lists are far above pilot sizes |
| Integration/security alert emails | Health page and in-app state cover admins |
| Digest emails (FR-NOTIF-006, P2) | Later phase |
| Semantic search (FR-SEARCH-005, C-03) | D10 defers embeddings |
| Typed asset metadata (FR-ASSET-005), graph view (FR-ASSET-007) | Not needed to complete workflows |
| SSO with a real IdP (FR-IAM-008) | Provider-handled; verify with first enterprise pilot |
| Penetration test, WCAG audit | Required before a customer pilot, not an internal one |
