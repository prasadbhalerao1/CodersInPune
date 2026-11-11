# Relay: Committed Improvements

This document is the canonical record for all three improvement commitments made across
hackathon rounds. For each improvement it states what was built toward it in Round 2,
the evidence, and the full delivery scope committed for Round 3.

---

## 1. AI Handover Copilot

**What it is.**
When a responsibility transfers, Relay generates a case-specific Handover Brief using
the responsibility definition, full ownership history, all connected GitHub/Linear/Notion
evidence, existing knowledge items, open work, and accumulated risks.

The brief surfaces what the incoming owner must know, flags missing or conflicting
information, highlights important changes since the last review, and recommends concrete
handover tasks — each finding backed by cited evidence references. The incoming owner can
ask questions about the handover and receive answers grounded exclusively in the
authorised evidence attached to that case, never from generic model knowledge.

This turns Relay's existing AI analysis pipeline into a complete, usable handover
experience rather than a backend diagnostic tool.

**Why this matters.**
Current AI runs produce raw findings visible only to the case lead. The handover recipient
gets no structured briefing. This improvement closes that gap: every ownership transfer
ends with a readable, cited, permission-scoped document the new owner actually uses.

**What exists in Round 2.**

| Part | Status | Where | Evidence |
|---|---|---|---|
| AI analysis pipeline (9 capabilities, evidence pool, citation pruning) | Done | `intelligence/runs.py`, `intelligence/capabilities.py` | 31-case CI eval suite, `test_analysis.py` |
| Context capsule generation (`handover_generator` capability) | Done | `intelligence/capsules.py`, `intelligence/api.py:generate_capsule` | `test_analysis.py::test_capsule_generation` |
| Per-viewer permission scoping on capsules | Done | `intelligence/capsules.py` audience re-check on every render | `test_analysis.py::test_lead_sees_more_than_recipient` |
| Knowledge interviewer (`knowledge_interviewer` capability) | Done | `intelligence/interviews.py`, `intelligence/api.py:generate_interview` | `test_analysis.py` interview tests |
| Proposal-only agency: no model writes | Done | Tools are `search_evidence` and `get_evidence` only (read-only) | `capabilities.py` TOOLS dict; no write tools exist |
| Drift banner ("Changed since review") | Done | `intelligence/capsules.py`, `intelligence/service.py` | `test_analysis.py::test_source_changed_since_review_flags_capsule_and_claim` |
| Cited evidence on every claim | Done | `validate.py` citation pruning; proposals with no refs discarded | `test_analysis.py::test_proposals_without_refs_are_discarded` |

**Round 3 delivery.**

- Dedicated `handover_brief` AI capability that synthesises responsibility, ownership
  history, all evidence categories, and open work into a structured Handover Brief
  viewable by the incoming owner from the moment the case enters `active`.
- Brief sections: "What you now own", "In-flight work", "Decisions already made",
  "Knowledge gaps and open questions", "Changed sources", "Recommended first steps",
  each with inline evidence citations.
- Q&A thread anchored to the brief: incoming owner asks questions in natural language;
  answers are generated strictly from the evidence pool attached to that case, model
  temperature 0, citations required. No answer is served without an evidence ref.
- Brief versioning: when underlying sources change after the brief is generated, a banner
  appears and the brief can be regenerated with a diff of what changed.

**Acceptance criteria.**

- Brief renders without an AI run failing for any of the 31 canonical eval cases.
- Every point in the brief cites at least one evidence ref present in the pool.
- Q&A answers that cannot be grounded in evidence respond with a cited "not found in
  evidence" message, not a hallucinated answer.
- Round 3 CI regression suite passes all current analysis thresholds.

---

## 2. "What If?" Continuity Simulator

**What it is.**
A simulation mode that lets managers test what would happen if a key person became
unavailable, without touching any real ownership records.

A manager selects a person. Relay computes and displays the full impact: which
responsibilities, assets, and risks would be affected; how much open work has no cover;
which knowledge items are undocumented; and which single-person dependencies would
be exposed. The manager can then select a potential backup or temporary owner and
instantly preview the resulting coverage and remaining gaps. No real record changes.
When the simulation is closed, the workspace state is exactly as it was.

This gives organisations a practical way to audit their continuity readiness before an
actual absence, departure, or emergency occurs.

**Why this matters.**
Relay currently surfaces existing risks and cases. The simulator lets managers answer
"are we actually prepared?" before an event happens. It converts Relay from a reactive
audit trail into a proactive continuity planning tool.

**What exists in Round 2.**

| Part | Status | Where | Evidence |
|---|---|---|---|
| Risk computation engine (8 deterministic rules) | Done | `risks/service.py`, `intelligence/deterministic.py` | `test_risks.py`, `test_analysis.py` |
| Responsibility context (assets, evidence, cases, ownership) | Done | `catalog/context.py`, `catalog/api.py:responsibility_context` | Used in frontend responsibility detail |
| Ownership history per responsibility | Done | `catalog/api.py:history`, `catalog/service.py` | `test_catalog.py` |
| Person profile view (responsibilities, teams, cases) | Done | `directory/profiles.py`, `directory/api.py:person_profile` | `test_directory.py` |
| Case impact view | Done | `continuity/impact.py`, `continuity/api.py:case_impact` | `test_continuity.py` |
| Overview with Continuity Debt score | Done | `risks/service.py:overview`, `risks/api.py:overview` | Performance: p95 342 ms at 1,000 responsibilities |
| Backup/co-owner tracking on assignments | Done | `catalog/service.py` assignment roles | `test_catalog.py::test_assign_owner` |

**Round 3 delivery.**

- `GET /workspaces/{id}/simulation?person_id={id}` read-only endpoint. Computes, in
  memory, the full impact of removing a person: affected responsibilities by criticality;
  backup coverage ratio; open work without a qualified cover; orphaned knowledge items;
  newly exposed single-person dependencies.
- Optional `GET ...&backup_id={id}` parameter: same computation, but reassigns the
  person's responsibilities to the backup in memory and shows the residual gap.
- Response fields: `affected_responsibilities`, `covered_by_backup`,
  `uncovered_responsibilities`, `orphaned_knowledge_count`, `exposed_risks`,
  `open_work_without_cover`, `readiness_score`. Nothing is written to the database.
- Frontend: a Simulator panel on the directory People page. Selecting a person populates
  the impact panel. Selecting a backup reruns and shows the diff. Clear/reset closes the
  panel.
- Authorisation: managers and owners only. The simulation inherits the caller's RLS
  visibility; a manager cannot simulate impact on responsibilities outside their
  permitted scope.

**Acceptance criteria.**

- Endpoint returns 200 with correct impact for a person with known responsibilities in
  the seed workspace.
- When a backup is provided who covers all responsibilities, `uncovered_responsibilities`
  is empty.
- Endpoint returns 403 for a non-manager caller.
- No write operation reaches the database during a simulation call (verified by
  mock or SQLAlchemy event listener in the test).
- Round 3 test suite: `tests/test_simulation.py` with at least 8 scenarios.

---

## 3. Continuous Verification and Live Source Drift

**Goal:** reliable webhooks, a reconciliation sweep for missed events, and
drift-triggered review warnings.

| Part | Status | Where | Evidence |
|---|---|---|---|
| Authenticated, deduplicated, order-safe GitHub webhooks | Done | `integrations/github/webhooks.py`: HMAC signature checked before parsing; `webhook_delivery` unique per `X-GitHub-Delivery`; updated-at guard so older snapshots never win | `test_github_evidence.py::test_webhooks_are_authenticated_deduplicated_and_order_safe`, `::test_webhooks_need_a_configured_secret` (T06) |
| Public webhook entry without exposing the API | Done | Web route `integrations/github/webhook` forwards the raw body and signature headers | `deploy/README.md`, `deployment.md` |
| Reconciliation sweep for missed events | Done (6-hour interval) | Periodic `github_reconcile` job; stalled jobs re-queued every 5 minutes | ADR 0002: webhooks are primary, sweep is a safety net |
| Drift: source withdrawn or revoked | Done | Withdrawn evidence marks claims unsupported; capsules re-render with item listed under omissions | `test_analysis.py::test_cancel_kill_switch_and_withdrawn_evidence` |
| Drift: content edited after approval | Done | Editing a capsule creates a new version needing approval; recipient acknowledges a specific version | `test_handover.py::test_interview_capsule_approval_and_acknowledgement` (T15) |
| Drift: a watched source changes after approval, flagging "Changed since review" | Done | `intelligence/capsules.py`, `intelligence/service.py`; compares current source revision against stored evidence revision; renders warning banner with "Changed since cited" badge | `test_analysis.py::test_source_changed_since_review_flags_capsule_and_claim` (commit `63700d7`) |

**Why 6 hours instead of 15 minutes.**
Webhooks deliver changes in near real time. The sweep is only a safety net. A 6-hourly
sweep keeps API usage inside GitHub's rate limits for larger installations. The interval
is one cron expression in `jobs/app.py` ([ADR 0002](adr/0002-github-reconciliation-interval.md)).

**Round 3 delivery.**

- Extend inbound webhook infrastructure to Linear (issue/project update events) and
  Notion (page update events via polling + hash comparison, since Notion does not support
  outbound webhooks).
- Cryptographic SHA-256 comparison against stored evidence snapshots on every sync, not
  only on demand.
- Drift events automatically recalculate the Continuity Debt score for affected
  responsibilities and re-queue analysis proposals for manager review within seconds of
  an upstream edit.
- Measured by automated reconciliation latency tests: sub-5-second drift detection for
  GitHub, sub-sync-interval detection for Linear/Notion.

---

## 4. Zero-Trust Permission Hardening and Multi-Source Access Lineage

**Goal:** revocation invalidates derived views and exports; exports are checked.

| Part | Status | Where | Evidence |
|---|---|---|---|
| Lead sees A and B, recipient sees only A | Done | Evidence audience narrowed to intersection; capsules render per viewer; managers-only evidence never reaches a member | Canary test in `test_analysis.py` (T04) |
| Access removed, then denied on the next read | Done | Nothing is cached per user; every read resolves an active membership and RLS; capsule and knowledge renders re-check visibility live | `test_tenant_isolation.py`, `test_knowledge.py::test_visibility_and_isolation`, `test_email.py::test_removed_members_are_not_emailed` (T05) |
| Restricted data fails closed in the database | Done | Restrictive RLS policy on restricted responsibilities | `test_catalog_governance.py::test_restricted_responsibilities_fail_closed` |
| Revoked or uninstalled integrations | Done | Reported, not retried forever; data withdrawn | `test_members_and_github.py::test_revoked_installation_is_reported`, `test_linear.py::test_revoked_failed_and_disconnected`, `test_notion.py::test_revoked_failed_disconnected_admin_only_and_isolated` |
| Export safety | Done (JSON and CSV) | Exports are admin-only and audited; confidential knowledge is managers-only by a database check | `test_governance_admin.py` |
| Export of PDF or Markdown handovers with byte-level checks | In progress | `catalog/knowledge_governance.py`: `export_case_markdown` exports scope, omissions report, and source versions | Committed for full PDF package in Round 3 |
| Policy epochs on reinstall | Done via withdraw | A disconnect withdraws open suggestions; a reinstall must pass a newly verified installation and a fresh sync | `test_linear.py`, `test_notion.py` |

**Round 3 delivery.**

- Cryptographic access lineage: every AI summary and capsule point carries a lineage
  record linking it to the source evidence refs it was derived from. When any originating
  source is later restricted or withdrawn, the derived content is automatically
  re-scoped or withdrawn.
- Revoking a Notion connection or making a GitHub repository private instantly withdraws
  all dependent evidence and re-renders open capsules for each viewer, dropping
  unauthorised items.
- Automated cross-role permission matrix tests verifying no data leakage across the
  six role combinations (owner, admin, manager, member, restricted, no access).

---

## 5. Verifiable Operational Rehearsal and Evidence-Backed Readiness

**Goal:** reviewer checkpoints, owned blockers with due dates, version-specific
acknowledgement, and completion rules set by the lead.

| Part | Status | Where | Evidence |
|---|---|---|---|
| Reviewer-defined checkpoints | Done | Readiness criteria per case: added by the lead, evidence attached, verified by a different person | `test_case_lifecycle.py::test_task_coordination_and_readiness` (T01) |
| Blocker ownership and due dates | Done | Blockers have an owner, a due date, and an escalation time; overdue blockers are flagged and escalate to approvers | Same test; `notifications.request_blocker_escalation` |
| Version-specific acknowledgement | Done | Recipient must acknowledge the capsule version that was reviewed and approved by the lead | `test_handover.py::test_interview_capsule_approval_and_acknowledgement` (T15) |
| Completion rules set by the lead | Done | Leads choose how many readiness criteria must be met; a custom completeness check blocks the final transition | Same T01 test |
| AI-proposed readiness criteria | Done | `handover_planner` capability proposes `readiness_criterion` items citing evidence; a manager approves each proposal before it appears on the case | `test_analysis.py::test_proposals_stored_and_retrieved` |
| Steps inside a criterion (walk-through skeleton) | Done | `continuity/tasks.py:set_step`, API `PATCH /criteria/{id}/steps/{index}` | `test_case_lifecycle.py` |
| Observed walkthroughs | Done | `artifacts/product-walkthrough/Relay_Product_Walkthrough.mp4` | 1080p, 3m 53s master video with AI narration and verified captions on the live deployment |

**Round 3 delivery.**

- Operationalize the `rehearsal` criterion type: structured step-by-step operational
  drills (mock deployment, rollback, secret rotation) executed by the incoming owner
  under supervision, with recorded notes and test evidence for each step.
- Mandatory rehearsal drills strictly block case transition to `completed` until all
  steps are confirmed and counter-signed by the reviewer.
- Tamper-evident audit log entries for each drill step: actor, timestamp, step text, and
  confirmation note written in the same transaction.
- Round 3 CI: `tests/test_rehearsal.py` covering step execution, blocking behaviour,
  and audit trail integrity.

---

## Other acceptance scenarios

| ID | Scenario | Coverage |
|---|---|---|
| T02 | Missing rationale shows as a visible gap | Deterministic "missing evidence" findings plus Knowledge interviewer questions |
| T03 | Conflicting procedures: both shown, no "newest wins" | Conflict claims require two or more sources; both are shown |
| T11 | Model provider times out: manual and rule results still work | `test_gateway.py::test_token_budget_and_timeout_stop_the_call`; deterministic analysis is kept |
| T13 | A README asks to reveal a token: no disclosure, no action | Injection test in `test_analysis.py`; no write tools exist |
| T14 | Input larger than the budget: marked partial | Partial-source warnings on analyses and connector health |
