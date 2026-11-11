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

## Round 3: The Three Deliverable Improvements

These three commitments are directly grounded in the existing modular architecture, extending partially implemented components rather than introducing speculative external dependencies:

### 1. Inbound Webhooks and Real-Time Sync for Linear and Notion
- **Scope:** Extend the proven `WebhookDelivery` pattern (`integrations/github/webhooks.py`) to Linear and Notion. Implement HMAC-SHA256 signature verification for Linear webhooks and Notion event handlers. Inbound events (Linear issue assignment and priority changes, Notion page content updates) dispatch directly through the transactional outbox to trigger immediate incremental reconciliation.
- **User Impact:** Eliminates the 6-hour polling interval and manual "Sync now" actions. Live changes in tickets or runbooks immediately update evidence, identity review queues, and Continuity Debt scores.
- **Acceptance Criteria:** Inbound deliveries pass cryptographic signature checks, reject replay attacks, deduplicate by external delivery ID, and update workspace evidence within 5 seconds without user intervention.

### 2. Verifiable Handover Dossier PDF and Markdown Export
- **Scope:** Upgrade `export_case_markdown` in `catalog/knowledge_governance.py` into a complete Handover Dossier generator. Outputs a styled, publication-ready PDF and a companion signed Markdown file containing case metadata, approved context capsules, task completion receipts, readiness signatures, and the omissions report. Includes a SHA-256 cryptographic provenance hash calculated across all cited source revisions.
- **User Impact:** HR, compliance officers, and incoming team leads receive an immutable, tamper-evident archival record suitable for HR files and IT audit logs, proving who transferred what, what was verified, and what was intentionally omitted.
- **Acceptance Criteria:** Export is restricted to authorized roles, includes exact source revisions (commit SHAs, Linear IDs, Notion hashes), verifies byte-level provenance, and renders clean PDF documents with zero external dependencies.

### 3. AI-Assisted Rehearsal Checklist Generation and Guided Operational Drills
- **Scope:** Operationalize the existing `CriterionType = "rehearsal"` and checklist state machine (`continuity/tasks.py: set_step`). When generating handover plans, the AI Handover Planner analyzes cited runbooks to synthesize concrete, executable rehearsal drills (e.g. verifying deploy access, executing dry-run rollbacks). The incoming owner works through the interactive checklist directly in Relay, recording execution notes and verification evidence before ownership transfer can be executed.
- **User Impact:** Replaces passive reading and checkbox sign-offs with demonstrated operational readiness. Incoming owners verify critical operational procedures while the outgoing owner is still present to supervise, eliminating knowledge loss at the source.
- **Acceptance Criteria:** Planner automatically drafts contextual rehearsal checklists; steps track actor and timestamp; mandatory rehearsals block case completion until all steps are confirmed and verified.
