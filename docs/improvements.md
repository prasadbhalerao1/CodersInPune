# The three committed improvements: status

Round 1 committed to three improvements (Round 1 plan §9.3). This page shows what was built
for each, where the evidence is, and what is still open. It does not claim more than the
code does.

## 1. Continuous verification

**Goal:** reliable webhooks, a sweep for missed events, and drift-triggered review.

| Part | Status | Where | Proof |
|---|---|---|---|
| Authenticated, deduplicated, order-safe webhooks | Done | `integrations/github/webhooks.py`: HMAC signature checked before parsing, `webhook_delivery` unique per `X-GitHub-Delivery`, and an updated-at guard so older snapshots never win | `test_github_evidence.py::test_webhooks_are_authenticated_deduplicated_and_order_safe`, `::test_webhooks_need_a_configured_secret` (T06) |
| Public webhook entry without exposing the API | Done | Web route `integrations/github/webhook` forwards the raw body and signature headers | `deploy/README.md`, `deployment.md` |
| Reconciliation sweep for missed events | Done, at a different interval | Periodic `github_reconcile` job every **6 hours**, not 15 minutes | Stalled jobs are re-queued every 5 minutes |
| Drift: source withdrawn or revoked | Done | Withdrawn evidence marks claims unsupported. Capsules re-render with the item listed under omissions | `test_analysis.py::test_cancel_kill_switch_and_withdrawn_evidence` |
| Drift: content edited after approval | Done | Editing a capsule creates a new version that needs approval again. The recipient acknowledges a specific version | `test_handover.py::test_interview_capsule_approval_and_acknowledgement` (T15) |
| Drift: a watched repository changes after approval, flagging "changed since review" | Done | `intelligence/capsules.py`, `service.py`, capsule page | `test_analysis.py::test_source_changed_since_review_flags_capsule_and_claim` (commit `63700d7`). Compares current source revision against stored evidence revision and renders a warning banner with the "Changed since cited" badge |

**Why 6 hours instead of 15 minutes.** Webhooks deliver changes in near real time, and
the sweep is only a safety net. A 6-hourly sweep keeps API usage well inside GitHub's
rate limits for larger installations. The interval is one cron expression in
`jobs/app.py` ([ADR 0002](adr/0002-github-reconciliation-interval.md)).

## 2. Permission hardening

**Goal:** revocation invalidates derived views and exports, and exports are checked.

| Part | Status | Where | Proof |
|---|---|---|---|
| Lead sees A and B, recipient sees only A | Done | Evidence audience is narrowed to the intersection. Capsules render per viewer. Managers-only evidence never reaches a member | Canary test in `test_analysis.py` (T04) |
| Access removed, then denied on the next read | Done | Nothing is cached per user. Every read resolves an *active* membership and RLS. Capsule and knowledge renders re-check visibility live | `test_tenant_isolation.py`, `test_knowledge.py::test_visibility_and_isolation`, `test_email.py::test_removed_members_are_not_emailed` (T05) |
| Restricted data fails closed in the database | Done | Restrictive RLS policy on restricted responsibilities | `test_catalog_governance.py::test_restricted_responsibilities_fail_closed` |
| Revoked or uninstalled integrations | Done | Reported, not retried forever; data withdrawn | `test_members_and_github.py::test_revoked_installation_is_reported`, `test_linear.py::test_revoked_failed_and_disconnected`, `test_notion.py::test_revoked_failed_disconnected_admin_only_and_isolated` |
| Export safety | Done (JSON and CSV) | Exports are admin-only and audited. Confidential knowledge is managers-only by a database check | `test_governance_admin.py` |
| Export of PDF or Markdown handovers with byte-level checks | In progress | `catalog/knowledge_governance.py`: `export_case_markdown` exports scope, omissions report, and source versions | Committed for full PDF package in Round 3 |
| Policy epochs on reinstall | Done via withdraw | A disconnect withdraws open suggestions. A reinstall must pass a newly verified installation and a fresh sync | `test_linear.py`, `test_notion.py` |

## 3. Richer rehearsal and readiness

**Goal:** reviewer checkpoints, owned blockers with due dates, version-specific
acknowledgement, and completion rules set by the lead.

| Part | Status | Where | Proof |
|---|---|---|---|
| Reviewer-defined checkpoints | Done | Readiness criteria per case: added by the lead, evidence attached, verified by a different person | `test_case_lifecycle.py::test_task_coordination_and_readiness` (T01) |
| Blocker ownership and due dates | Done | Blockers have an owner, a due date and an escalation time. Overdue blockers are flagged and escalate to approvers | Same test; `notifications.request_blocker_escalation` |
| Version-specific acknowledgement | Done | `capsule_ack` per version; a new version needs a new approval and acknowledgement | `test_handover.py` |
| Completion rules the lead configures | Done | The lead marks readiness checks mandatory. A case can't complete until every mandatory check is met or waived, and a waiver needs a reason | `test_case_lifecycle.py` |
| Named, expiring risk acceptance | Done | Risk accepted *until a date* with a reason. It re-opens itself when the date passes | `test_risk_lifecycle.py::test_acknowledge_accept_expire_resolve_and_recur` |
| Observed walkthroughs | Done | `artifacts/product-walkthrough/Relay_Product_Walkthrough.mp4` | 1080p, 3m 53s master video with AI narration and verified captions on the live deployment |

## Other acceptance scenarios

| ID | Scenario | Where it's covered |
|---|---|---|
| T02 | Missing rationale → a visible gap and a targeted question | Deterministic "missing evidence" findings plus Knowledge interviewer questions |
| T03 | Conflicting procedures → both shown, no "newest wins" | Conflict claims need two or more sources, and both are shown |
| T11 | Model provider times out → manual and rule results still work | `test_gateway.py::test_token_budget_and_timeout_stop_the_call`; deterministic analysis is kept |
| T13 | A README asks to reveal a token → no disclosure, no action | Injection test in `test_analysis.py`; no write tools exist |
| T14 | Input larger than the budget → marked partial | Partial-source warnings on analyses and connector health |

## Round 3: The Three Committed Improvements

These three commitments represent substantial engineering depth and architectural hardening across core system capabilities, resolving genuine continuity challenges rather than superficial features:

### 1. Continuous Verification and Live Source Drift Detection
- **Engineering Depth:** Transition Relay from periodic polling to an event-driven continuous verification system across GitHub, Linear, and Notion. Extends webhook intake and cryptographic revision hashing to automatically compare live source states against cited evidence. When code, tickets, or documentation change in connected systems, Relay dynamically flags affected knowledge and handovers with a "Changed since review" state, recalculates Continuity Debt, and surfaces targeted update proposals before stale context causes operational disruptions.
- **User Impact:** Eliminates the risk of acting on outdated runbooks or closed tickets during a critical handover. Team leads and incoming owners no longer have to manually verify whether documentation in Notion or code in GitHub has drifted; Relay continuously proves whether the operational context remains current and accurate.
- **Acceptance Criteria:** Inbound deliveries pass cryptographic signature checks, reject replay attacks, deduplicate by external delivery ID, and flag affected handovers with precise diff banners within seconds of upstream edits.

### 2. Zero-Trust Permission Hardening and Multi-Source Access Lineage
- **Engineering Depth:** Implement strict access lineage across all multi-source evidence, AI summaries, and context capsules. Every derived finding, proposal, and interview response inherits the cryptographic intersection of permissions from its originating sources. When an integration is disconnected, a repository turns private, or access is revoked, dependent views and derived context are instantly withdrawn from non-manager views, guaranteeing zero unauthorized data exposure across cross-functional teams.
- **User Impact:** Solves the primary enterprise security barrier when connecting tools like GitHub and Notion: accidental information leakage. Engineers only see handovers and AI summaries built from resources they are authorized to see, while managers retain cross-functional visibility without exposing private repositories or confidential project details.
- **Acceptance Criteria:** Derived claims and context capsules dynamically re-filter on every render based on the viewer's active permissions. Revoking a source instantly removes dependent citations from non-manager views, verified by automated cross-role permission tests.

### 3. Verifiable Operational Rehearsal and Evidence-Backed Readiness Verification
- **Engineering Depth:** Bridge the critical gap between passive documentation handover and demonstrable operational competence. Operationalize supervised rehearsal workflows directly linked to cited runbooks and tasks. The incoming owner executes structured operational drills (such as mock deployment dry-runs, access verification checks, and rollback procedures) under supervision, recording execution notes and test evidence. Completing these mandatory drills acts as an automated, audited gate before final ownership transfer can commit.
- **User Impact:** Eliminates the fear and uncertainty of the person taking over a new service. Incoming owners prove they can independently operate and troubleshoot the service before the predecessor leaves, and managers receive verifiable audit proof of operational capability rather than an unverified promise that a handover took place.
- **Acceptance Criteria:** Rehearsal drills enforce step-by-step verification with recorded actor attribution; mandatory drills strictly block case transition to completed until all operational checks are confirmed and signed off by the reviewer.
