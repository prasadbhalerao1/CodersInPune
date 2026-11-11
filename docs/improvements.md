# Relay: Committed Improvements

This document is the canonical record of the three improvements committed for Round 3.
For each improvement it states the product intent, the Round 2 foundation it builds on,
the Round 3 delivery scope, and the acceptance criteria.

---

## 1. AI Handover Copilot

**What it is.**
When a responsibility transfers, Relay generates a case-specific Handover Brief using the
responsibility definition, full ownership history, all connected GitHub/Linear/Notion
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
| `handover_generator` capability that writes per-recipient capsule with sections | Done | `intelligence/capsules.py`, `intelligence/api.py:generate_capsule` | `test_analysis.py::test_capsule_generation` |
| Per-viewer permission scoping on capsules | Done | `intelligence/capsules.py` audience re-check on every render | `test_analysis.py::test_lead_sees_more_than_recipient` |
| Knowledge interviewer (`knowledge_interviewer` capability) | Done | `intelligence/interviews.py`, `intelligence/api.py:generate_interview` | `test_analysis.py` interview tests |
| Proposal-only agency: no model writes | Done | Tools are `search_evidence` and `get_evidence` only | `capabilities.py` TOOLS dict; no write tools exist |
| Drift banner ("Changed since review") | Done | `intelligence/capsules.py`, `intelligence/service.py` | `test_analysis.py::test_source_changed_since_review_flags_capsule_and_claim` |
| Cited evidence on every claim | Done | `validate.py` citation pruning; proposals with no refs discarded | `test_analysis.py::test_proposals_without_refs_are_discarded` |
| Capsule versioning and acknowledgement | Done | `intelligence/capsules.py:approve`, `acknowledge` | `test_handover.py::test_interview_capsule_approval_and_acknowledgement` (T15) |

**Round 3 delivery.**

- Dedicated `handover_brief` AI capability that synthesises responsibility, ownership
  history, all evidence categories, and open work into a structured Handover Brief
  viewable by the incoming owner from the moment the case enters `active`.
- Brief sections: "What you now own", "In-flight work", "Decisions already made",
  "Knowledge gaps and open questions", "Changed sources", "Recommended first steps",
  each with inline evidence citations and confidence indicators.
- Q&A thread anchored to the brief: incoming owner asks questions in natural language;
  answers are generated strictly from the evidence pool attached to that case.
  Temperature 0, citations required. No answer is served without an evidence ref.
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
which knowledge items are undocumented; and which single-person dependencies would be
exposed. The manager can then select a potential backup or temporary owner and instantly
preview the resulting coverage and remaining gaps. No real record changes. When the
simulation is closed, the workspace state is exactly as it was.

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
- Optional `&backup_id={id}` parameter: same computation with the person's
  responsibilities reassigned to the backup in memory, showing the residual gap.
- Response fields: `affected_responsibilities`, `covered_by_backup`,
  `uncovered_responsibilities`, `orphaned_knowledge_count`, `exposed_risks`,
  `open_work_without_cover`, `readiness_score`. Nothing is written to the database.
- Frontend: a Simulator panel on the directory People page. Selecting a person populates
  the impact panel. Selecting a backup reruns and shows the diff.
- Authorisation: managers and owners only. The simulation inherits the caller's RLS
  visibility; a manager cannot simulate impact outside their permitted scope.

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

## 3. Project Memory Replay

**What it is.**
An interactive project history timeline that reconstructs how a project evolved using
authorised data from GitHub, Linear, and Notion.

Relay analyses Git commits, pull requests, issues, and linked documentation to group
related activity into meaningful events: major implementations, technical changes, bug
fixes, incidents, and documentation updates. AI generates concise explanations of what
happened, why it matters, and how different events are connected, with links to the
original supporting sources and clear indicators of uncertainty.

Users can explore the project chronologically, filter events by category, play back its
evolution, and inspect the evidence behind individual events.

This helps incoming team members understand not just the current state of a project, but
how it reached that state, what decisions shaped it, and what important context they need
before taking over.

**Why this matters.**
Relay already ingests GitHub PRs, issues, and commit metadata; Linear issues and project
cycles; and Notion knowledge pages. That data is currently used only for ownership
signals and evidence citations. Project Memory Replay turns the same authorised,
already-fetched data into a navigable timeline that answers "how did we get here?" — the
one question no handover document currently answers well.

**What exists in Round 2.**

| Part | Status | Where | Evidence |
|---|---|---|---|
| GitHub PR and issue ingestion (title, state, author, assignees, labels, timestamps, URL) | Done | `integrations/github/client.py:WorkItem`, `service.py:sync_work_items` | `test_github_evidence.py` |
| Linear issue ingestion (title, priority, cycle, assignees, timestamps) | Done | `integrations/linear/service.py` | `test_linear.py` |
| Notion page ingestion (title, URL, last-edited timestamp, SHA-256 revision hash) | Done | `integrations/notion/service.py` | `test_notion.py` |
| Evidence pool with timestamps and source system labels | Done | `intelligence/evidence.py:Pool` | Used in all 9 AI capability prompts |
| Knowledge item timeline (`updated_at`, `stale` flag, review tracking) | Done | `catalog/knowledge_governance.py` | `test_knowledge.py` |
| AI capability `discovery`: reconstructs current state with timelines and decisions | Done | `intelligence/capabilities.py:FOCUS["discovery"]` | `test_analysis.py::test_discovery_capability` |
| Responsibility ownership history (all owner changes with timestamps) | Done | `catalog/service.py:ownership_history`, `catalog/api.py:history` | `test_catalog.py` |

**Round 3 delivery.**

- `GET /workspaces/{id}/responsibilities/{resp_id}/timeline` endpoint that returns a
  chronologically ordered, paginated list of `TimelineEvent` objects built from the
  responsibility's ingested GitHub PRs/issues, Linear issues, and Notion page edits.
- Each event carries: `occurred_at`, `category` (implementation / bug fix / incident /
  documentation / technical change / ownership change), `title`, `summary`,
  `significance` (high / medium / low), `source_url`, `source_system`,
  `uncertainty_level`, and `linked_events` (refs to related events in the same window).
- AI `memory_narrator` capability: runs over the responsibility's evidence pool and
  produces structured `MemoryEvent` objects with AI-generated summaries and inter-event
  connections. All events cite the evidence refs they were derived from.
- Uncertainty labelling: events where AI confidence is low are explicitly marked with
  `uncertainty_level = "inferred"`. Events reconstructed directly from raw data
  (commit timestamp, PR merge date) are `uncertainty_level = "factual"`.
- Frontend: a Timeline tab on the responsibility detail page. Events are grouped by
  month, filterable by category, expandable to show the evidence behind each summary.
- Read-only: no event record writes. The timeline is always reconstructed from the
  live evidence pool on request.

**Acceptance criteria.**

- Timeline endpoint returns a non-empty result for the seed workspace's
  `CodersInPune` repository responsibility with at least one merged PR in evidence.
- Every `TimelineEvent` with `uncertainty_level = "inferred"` cites at least one
  evidence ref; events with no supporting ref are not returned.
- Filtering `?category=bug_fix` returns only events of that category.
- Endpoint returns 403 for a non-member caller.
- Round 3 test suite: `tests/test_memory_replay.py` with at least 6 scenarios.

---

## Round 2 delivery: status of the existing improvements

The following improvements were committed in Round 1 and are fully implemented in Round 2.
They remain part of the system; the three above are what will be delivered in Round 3.

### Continuous Verification (fully delivered in Round 2)

| Part | Status | Where | Evidence |
|---|---|---|---|
| Authenticated, deduplicated, order-safe GitHub webhooks | Done | `integrations/github/webhooks.py` | `test_github_evidence.py::test_webhooks_are_authenticated_deduplicated_and_order_safe` (T06) |
| Reconciliation sweep (6-hour interval) | Done | Periodic `github_reconcile` job | ADR 0002 |
| Drift: source withdrawn or revoked | Done | Withdrawn evidence marks claims unsupported | `test_analysis.py::test_cancel_kill_switch_and_withdrawn_evidence` |
| Drift: "Changed since review" banner | Done | `intelligence/capsules.py`, `intelligence/service.py` | `test_analysis.py::test_source_changed_since_review_flags_capsule_and_claim` |

### Permission Hardening (fully delivered in Round 2)

| Part | Status | Where | Evidence |
|---|---|---|---|
| Audience intersection per viewer | Done | Evidence audience narrowed; capsules render per viewer | `test_analysis.py` (T04) |
| Access removed, then denied on next read | Done | Live membership + RLS on every read | `test_tenant_isolation.py`, T05 |
| Restricted data fails closed in DB | Done | Restrictive RLS on restricted responsibilities | `test_catalog_governance.py::test_restricted_responsibilities_fail_closed` |
| Revoked integrations | Done | Reported, withdrawn, not retried | `test_linear.py::test_revoked_failed_and_disconnected` |

### Rehearsal and Readiness (fully delivered in Round 2)

| Part | Status | Where | Evidence |
|---|---|---|---|
| Reviewer-defined checkpoints | Done | Readiness criteria with evidence attachment | `test_case_lifecycle.py::test_task_coordination_and_readiness` (T01) |
| Blocker ownership and due dates | Done | Blockers with owner, due date, escalation time | Same T01 |
| Version-specific acknowledgement | Done | Recipient must acknowledge the approved capsule version | `test_handover.py` (T15) |
| AI-proposed readiness criteria | Done | `handover_planner` capability | `test_analysis.py::test_proposals_stored_and_retrieved` |
| Steps inside a criterion | Done | `continuity/tasks.py:set_step` | `test_case_lifecycle.py` |

---

## Other acceptance scenarios

| ID | Scenario | Coverage |
|---|---|---|
| T02 | Missing rationale shows as a visible gap | Deterministic "missing evidence" findings plus Knowledge interviewer questions |
| T03 | Conflicting procedures: both shown, no "newest wins" | Conflict claims require two or more sources; both are shown |
| T11 | Model provider times out: manual and rule results still work | `test_gateway.py::test_token_budget_and_timeout_stop_the_call`; deterministic analysis kept |
| T13 | A README asks to reveal a token: no disclosure, no action | Injection test in `test_analysis.py`; no write tools exist |
| T14 | Input larger than the budget: marked partial | Partial-source warnings on analyses and connector health |
