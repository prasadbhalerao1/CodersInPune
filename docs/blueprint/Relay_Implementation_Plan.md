# Relay — Implementation Plan (Founder-led, AI-assisted)

| Field | Value |
|---|---|
| Version | 0.1 — for founder review |
| Date | 8 Nov 2026 |
| Replaces | Blueprint §O (both the team plan and the §O.0 solo draft) |
| Depends on | `Relay_Architecture_Decision_Register.md` (decision IDs D1–D26, spikes S1–S7) |
| Working model | One founder (final decision-maker). Claude handles substantial implementation and technical work. ChatGPT is the product and engineering thinking partner and a second reviewer. |

---

## 1. Planning principles

1. **Sequential vertical slices.** Each milestone ends in something a real user could use or verify. No horizontal "build all models first" phases.
2. **Manual first.** The first meaningful product (M0–M4) works **without AI and without integrations**. Connectors come next (M5–M7), then AI (M8–M9).
3. **Build the parts that are expensive to retrofit on day one**, even when they're invisible:
   - tenancy and RLS;
   - the permission registry;
   - valid-time history;
   - audit;
   - the outbox;
   - idempotency;
   - evidence audiences (in the schema).
4. **Cut breadth, not correctness.** Defer features, never defer the guardrails in §5.
5. **Decisions before code.** A milestone cannot start until the decisions and spikes it depends on are approved (§3).
6. **No calendar promises.** The plan uses effort bands (§2). Re-estimate after each milestone using actual effort.

## 2. Effort bands

Bands are relative to one founder working with AI assistance. They are not dates.

| Band | Meaning |
|---|---|
| **S** | A few focused working sessions. One module, little UI. |
| **M** | Roughly 1–2 weeks of focused work. One module plus UI. |
| **L** | Roughly 2–4 weeks of focused work. Several modules plus UI plus a non-trivial test surface. |
| **XL** | More than 4 weeks of focused work. Split it if possible. |

"Focused" assumes uninterrupted building time. Calendar time depends on your availability, and I don't estimate it.

## 3. Milestone map and dependencies

```
Phase 0  Decisions & spikes (S1–S7)                                      band M (total)
   │
Phase 1  Continuity foundation — no AI, no integrations
   M0 Platform foundations ─► M1 Org & Catalog ─► M2 Coverage Risks & Home
                                             └──► M3 Manual Transfer cases ─► M4 Coverage & Departure
   ═══ First meaningful product (usable by a design partner) after M4 ═══
Phase 2  Connected sources — still no AI
   M5 Connector framework + GitHub ─► M6 Linear + approved actions ─► M7 Knowledge + Notion
Phase 3  Intelligence
   M8 AI runtime + case analysis ─► M9 Interviews, Capsules, Return Briefing
Phase 4  Pilot readiness
   M10 Pilot hardening (selected deferred items)
```

| Milestone | Band | Hard dependencies | Decisions/spikes that must be approved first |
|---|---|---|---|
| Phase 0 | M | — | — |
| M0 | L | Phase 0 (S2, S4, S6) | D5, D7, D8, D11, D23, D24, D26 |
| M1 | L | M0 | D1, D14, D15, D25 |
| M2 | M | M1 | D12 |
| M3 | XL (split into M3a/M3b) | M1 (M2 recommended) | D2 (schema), D16, D17, D21 |
| M4 | M | M3 | D4 |
| M5 | L | M3 (for suggestions → catalog), S1 GitHub | — |
| M6 | M | M5 framework, S1 Linear | D18 |
| M7 | L | M5, S1 Notion | D3, D13, D22 |
| M8 | L | M7 (evidence + knowledge), S3 | D2 (behaviour), D6, D10 |
| M9 | L | M8 | D9 |
| M10 | L | M9 + pilot needs | D19 (if billing) |

### Which milestones can be combined safely

| Combination | Safe? | Why |
|---|---|---|
| M1 + M2 | **Yes** | Rules only read catalog tables; same UI area |
| M3a + M3b | Only if M3a's state machine tests are green first | Approvals and closure depend on a correct engine |
| M4 into M3b | **Yes**, if M3b is on schedule | Coverage and Departure reuse the same engine |
| M5 + M6 | **Yes** | Same framework; Linear is the second adapter. Doing it this way also forces the framework to generalise |
| M7 + M8 | **No** | M8's evals need a stable evidence/knowledge model to test against |
| M0 + anything | **No** | Isolation and permission foundations must be proven alone |
| M8 + M9 | Not recommended | Ship one AI surface, measure acceptance rates, then expand |

---

## 4. Milestones

Each milestone below lists: **Outcome · Features · Backend · Frontend · Database · Testing · Security · Demo/verification · Dependencies · Exit criteria.** The common Definition of Done in §6 also applies to every milestone.

### Phase 0 — Decisions & spikes (band M)

- **Outcome.** All M0-blocking decisions approved, and spikes answered with one-page decision records (`docs/adr/`).
- **Work.**
  - S2: queue under `kill -9`, periodic leader, tenant locks.
  - S4: RLS + `after_begin` `set_config` + pooler + `LISTEN` + Alembic manual steps.
  - S6: AuthKit → Next.js → FastAPI JWKS + invitation by verified email.
  - S1: three hands-on connector checks. These can run later, before M5–M7.
  - S3: can wait until before M8.
  - S7: licence deny-list policy + SBOM tooling choice.
- **Spike code is throwaway** and lives outside the product repo (or in a `spikes/` folder that is deleted afterwards).
- **Exit.**
  - ADRs for D5, D7, D8, D11, D23, D24 and D26 are signed by the founder.
  - The repo conventions file (`CLAUDE.md`/`AGENTS.md`) is written: module layout, layering rules, testing rules, the guardrails in §5.

### M0 — Platform foundations (band L)

- **Outcome.** A secure, empty multi-tenant SaaS shell. A user can sign up, create a workspace, invite a member and manage teams. Every guardrail is in place and enforced by CI.
- **Features.**
  - Sign-in (AuthKit).
  - Workspace creation.
  - Invitations (accept by verified email), member list.
  - Suspend/deactivate members.
  - Workspace roles (Owner/Admin/Member/Guest/Auditor).
  - Audit log (viewer).
  - App shell (sidebar, workspace switcher, ⌘K stub).
  - State components library.
- **Backend.**
  - Package layout with import-linter contracts.
  - Tenant context dependency.
  - `after_begin` tenant `set_config`.
  - Permission registry with `authorize()`/`visible()` primitives.
  - Audit writer.
  - Outbox table + relay.
  - Queue integration with per-tenant fan-out (D26).
  - RFC 9457 errors.
  - `Idempotency-Key` middleware for commands.
  - OpenAPI generation.
  - Health endpoints.
- **Frontend.**
  - Next.js app, AuthKit session.
  - Generated API client.
  - TanStack Query.
  - shadcn/ui theme tokens.
  - Layout shell.
  - EmptyState/Error/PermissionNotice/Skeleton components.
  - Members & invitations screens.
  - Audit log table.
- **Database.**
  - `tenant`, `user`, `membership` (+ change table), `invitation`, `audit_event` (insert-only grants), `outbox_event`, `processed_event`, `idempotency_record`.
  - Queue tables.
  - Roles: owner (migrations) and app (no BYPASSRLS).
  - RLS FORCE on all tenant tables.
- **Testing.**
  - Generated cross-tenant route test.
  - RLS canary (no tenant set → zero rows).
  - Migration lint (RLS enabled+forced, unique keys include `tenant_id`).
  - Outbox at-least-once + handler dedupe test.
  - Queue crash-recovery test.
  - Playwright: sign-up → invite → accept.
- **Security.**
  - JWT verification (issuer/audience/expiry).
  - Per-request membership status check.
  - Secrets from the environment/secret manager only.
  - CSRF posture documented (bearer tokens, no cookies to the API).
  - Rate limiting on auth-adjacent endpoints.
  - Dependency/licence scanning + SBOM in CI.
- **Demo.** Two workspaces created by two users. User A cannot see, guess or reach any of B's members or audit events. The test report shows the generated isolation suite green.
- **Dependencies.** Phase 0.
- **Exit.**
  - All CI guardrail checks are enforced (failing builds block merge).
  - Deployed to staging on the chosen platform with backups on.
  - A restore drill has been run once.

### M1 — Organisation & Catalog (band L)

- **Outcome.** An organisation can model its teams and responsibilities, including ownership history. This is the core record of Relay.
- **Features.**
  - Departments/teams with membership history.
  - Responsibilities (CRUD/archive; type, criticality, team, escalation, review cadence, `restricted`).
  - Ownership assignments: primary/co-owner/backup/temporary, user or team, effective dates, history timeline, correction with reason.
  - Assets (manual) and responsibility↔asset links (stewards/uses).
  - CSV import (people, teams, responsibilities, assignments) with dry-run.
  - Person and team pages.
  - Criticality tier definitions in settings.
- **Backend.**
  - `org` and `catalog` modules.
  - Valid-time queries (`as_of`).
  - Change-table writes (D25).
  - Import service: parse → validate → preview → commit, idempotent on natural keys.
  - `visible()` predicates honouring `restricted` (D14).
  - Scoped grants: Team Manager, Continuity Manager.
- **Frontend.**
  - Responsibilities list (TanStack Table, filters, saved views in URL).
  - Responsibility detail (Owners & History timeline).
  - Asset list/detail.
  - Import wizard with row-level errors.
  - Team/person pages.
  - Inline "assign backup".
- **Database.**
  - `department`, `team`, `team_membership`, `scoped_grant`, `responsibility`, `ownership_assignment` (`tstzrange`, `EXCLUDE` single primary, `btree_gist`), `ownership_assignment_change`, `asset` (type, metadata JSONB + schema_version), `responsibility_asset`, `import_job`/`import_row`.
- **Testing.**
  - Property tests on assignment invariants (no overlapping primaries; contiguous handover allowed; temporary must be bounded).
  - `as_of` correctness including corrections.
  - Permission matrix tests generated from the registry (catalog actions).
  - Import idempotency.
  - Restricted responsibility hidden from search/lists/counts for non-scoped users.
- **Security.**
  - Scoped grants enforced in services.
  - `restricted` existence-hiding (404).
  - Import file size/type limits.
- **Demo.** Import a 40-person org from CSV. Open "Payment Service Operations". Show that the owner changed in June, and answer "who owned it on 1 June?". Try to create a second primary → rejected with a clear message.
- **Dependencies.** M0. D1, D14, D15, D25.
- **Exit.** A design partner could keep their responsibility catalogue in Relay.

### M2 — Coverage Risks & Home (band M)

- **Outcome.** Relay tells managers where continuity is weak, before anything happens.
- **Features.**
  - Rules engine v1, all deterministic:
    - no primary;
    - no backup when the tier requires one;
    - backup = primary;
    - owner deactivated;
    - team primary without an accountable contact (critical tier);
    - single-holder concentration;
    - asset without a stewarding responsibility.
  - Findings lifecycle: open → acknowledged → in remediation → resolved / accepted risk (until date) / dismissed (reason), with auto-resolve.
  - Risks screen with inline remediation.
  - Home (role-aware).
  - "Who's irreplaceable?" panel (managers).
  - Coverage policy settings.
- **Backend.**
  - `findings` module.
  - Versioned rules as pure functions over catalog read models.
  - Per-tenant periodic evaluation + event-triggered evaluation (outbox handlers).
  - Dedupe keys.
- **Frontend.**
  - Risks list with tier chips and a "why" drawer.
  - Remediation actions.
  - Home widgets: top actions, risks summary, upcoming items.
- **Database.** `finding`, `finding_event`, `coverage_policy`.
- **Testing.**
  - Rule unit tests per rule (positive/negative).
  - Idempotent re-evaluation (no duplicate findings).
  - Dismissed findings don't reopen for the same evidence.
  - Deactivation → finding within one cycle.
- **Security.** Findings are visible only to principals who can see their subject. Restricted responsibilities produce findings visible only to scoped users.
- **Demo.** Deactivate a user → "3 critical responsibilities lost their owner" appears on Home. Assign backups inline → findings resolve.
- **Dependencies.** M1. D12.
- **Exit.** Coverage hygiene works end-to-end with no integrations.

### M3 — Manual Transfer cases (band XL → split)

**M3a — Case engine & planning (band L)**
- **Outcome.** A manager can open a Transfer case, define scope items and plan the work.
- **Features.**
  - Playbook engine (code-defined, versioned, per-tenant parameters).
  - Transfer playbook.
  - Case wizard (≤4 steps, data-use notice).
  - Scope items (from/to/effective date/state; receiver "TBD" blocks the item).
  - Tasks (assignee user/team, due date, dependencies, completion evidence).
  - Case participants with relationship roles.
  - Duplicate-case warning.
  - Case list + detail (Overview, Scope, Plan, Activity tabs; right rail).
  - Next-action banner.
  - Comments and mentions.
- **Backend.**
  - `cases` module.
  - Transition functions per stage (draft → scoping → planning → executing → verifying → closed) and flags.
  - Derived "waiting on".
  - Case activity events.
  - `visible()` predicates for case participation.
- **Database.**
  - `playbook_version`, `case`, `case_stage_history`, `case_participant` (valid-time), `case_scope_item`, `task`, `task_dependency`, `comment`, `mention`.
  - **Evidence-audience schema introduced now:** `evidence_pool_entry` with an audience enum. It stays empty until M7/M8, so that D2 doesn't force a later migration of case permissions.

**M3b — Approvals, readiness, closure, inbox (band L)**
- **Outcome.** The transfer is completed *verifiably*, and ownership switches on the effective date.
- **Features.**
  - Approval requests bound to content hash; approval sheet showing what / where / who sees / reversible.
  - Consent as an approval kind (used from M4/M7).
  - Readiness criteria (6 fixed types, D21) with verifier sign-off.
  - Closure rules + SoD for critical (D16).
  - Exceptions.
  - Effective-dated ownership switch.
  - Reopen/cancel cascade.
  - My Work inbox (tasks, approvals, reviews, mentions).
  - In-app + email notifications (no sensitive content).
  - Reminders and escalation.
- **Backend.**
  - `approvals` (within `cases` or `policy`).
  - Readiness evaluator (deterministic).
  - Closure service calling `catalog.public` in one transaction.
  - `work` module (inbox materialisation, notifications, reminders).
  - Email adapter.
- **Database.** `approval_request`, `approval_decision`, `readiness_criterion`, `case_exception`, `inbox_item`, `notification`, `notification_delivery`, `reminder_schedule`.
- **Testing (M3a+b).**
  - Hypothesis state-machine tests (no illegal transitions; no closure with unmet criteria without an exception).
  - Fake-clock workflow tests (reminders, escalation caps, effective-date switch).
  - Approval hash invalidation on edit.
  - Cancel cascade.
  - Permission matrix for case actions (generated).
  - Playwright: PRD AC-01 manual variant.
- **Security.**
  - Participants see only their cases.
  - Approvers see only the approval subject.
  - Notification bodies contain links only.
  - Every command authorised and audited.
- **Demo.** Transfer 2 responsibilities to 2 receivers. A required approval is rejected and then re-approved. Readiness is signed off. Close → ownership shows "scheduled" until the effective date, then becomes current. Reopen preserves the prior closure.
- **Dependencies.** M1 (M2 recommended). D2 schema, D16, D17, D21.
- **Exit.** A complete AI-free transfer runs with no dead ends; every edge case in PRD §17.4 has a test or a documented deferral.

### M4 — Coverage & Departure (band M)

- **Outcome.** The two highest-value recurring and acute playbooks run manually. **This completes the first meaningful product.**
- **Features.**
  - Temporary Coverage playbook: bounded temporary assignments, authority notes, "extend?" reminder, early return.
  - Manual return briefing: a deterministic digest of case activity and task outcomes during the window. The AI version comes in M9.
  - Departure playbook (if D4 is approved): parent case → one Transfer item per held assignment, plus "only backup" items; consent step placeholder (owner confirms the item list).
  - Emergency flag (interviews disabled, backups promoted to temporary with one approval).
- **Backend.** New playbook definitions only. Engine changes only if a real gap appears; record it as an ADR.
- **Frontend.** Coverage timeline, return briefing page, Departure overview grouping items.
- **Database.** No new core tables. Possibly a `case.parent_case_id` column.
- **Testing.** Expiry by valid-time (no job), early return, extension, overlapping absences warning, departure with a TBD receiver blocking only that item.
- **Security.** Self-initiated coverage requires manager activation (D17).
- **Demo.** Arjun is away 10–24 Dec. Covers act automatically within the window, and the briefing is available on return. Priya's departure spawns 5 items, one blocked with no receiver, and a Risk is raised.
- **Dependencies.** M3. D4.
- **Exit.** **Design-partner ready (manual).** A 2–3 person team could run real handovers in Relay with no integrations.

### M5 — Connector framework + GitHub (band L)

- **Outcome.** Relay bootstraps the catalogue from GitHub and keeps source state fresh, honestly reporting staleness.
- **Features.**
  - Connector framework: capabilities, credentials (envelope-encrypted), scopes, full/incremental sync with checkpoints, webhook inbox (dedupe on delivery ID), health states, rate-limit handling, disconnect + retention.
  - GitHub App: orgs, teams, repos, CODEOWNERS, `catalog-info.yaml`, issues/PRs metadata, collaborator visibility (S1).
  - Identity mapping (verified email auto-match; suggestions otherwise).
  - **Ownership Suggestions** (deterministic) with bulk review.
  - Declared-ownership mismatch rule.
  - Integrations settings screen.
- **Backend.** `integrations` and `sources` modules; sync engine; `source_visibility` computation; suggestion generator.
- **Database.** `connector`, `credential`, `sync_run`, `sync_checkpoint`, `webhook_inbox`, `source_record`, `source_record_version`, `source_visibility`, `external_identity`, `identity_link`, `suggestion`.
- **Testing.**
  - Connector contract tests with recorded fixtures: pagination, 403/404, rate-limit headers, rename, deletion, token expiry.
  - Duplicate and out-of-order webhooks (AC-05).
  - Visibility recomputation on membership change.
  - A nightly live test against a test GitHub org (can start in M10 if time is short).
- **Security.**
  - Webhook HMAC verification.
  - Least-privilege App permissions (documented list).
  - No source code crawled; path allowlist.
  - Credentials never logged.
  - Unmatched identities never generate suggestions for Relay users.
- **Demo.** Connect a GitHub org → 20 suggestions → bulk accept 15, edit 3, reject 2 → Risks update. Revoke a user's repo access → their visibility of that repo's evidence disappears after the webhook or nightly refresh.
- **Dependencies.** M3 (catalogue + cases exist), S1 GitHub items.
- **Exit.** Sync is restartable, idempotent and visibly fresh or stale.

### M6 — Linear + approved external actions (band M)

- **Outcome.** Case tasks can be pushed to Linear after approval, with receipts. This is still deterministic: no AI.
- **Features.**
  - Linear connector (`actor=app`): teams, projects (+ leads), issues (open + recent), team-level visibility, status pull-back.
  - **Action Executor**: approved `action_request` → re-authorise → idempotency key → create issue → receipt → correlation marker. Unknown-outcome recovery by lookup.
  - GitHub issue creation via the same executor.
  - Open work shown on assets and scope items.
- **Database.** `action_request`, `action_execution` (unique idempotency key), `external_ref` on `task`.
- **Testing.**
  - Executor idempotency under timeout-after-success.
  - Approval hash mismatch → refuse.
  - Rate-limit backoff (Linear complexity headers).
  - External completion reconciles the task state.
- **Security.** Create-only (D18); approval required for every external write; executor runs under an auditable app identity with the requester attribution recorded.
- **Demo.** Approve 3 plan tasks → 3 Linear issues with links. Kill the worker mid-execution → exactly 3 issues, no duplicates. Complete one issue in Linear → the task completes in Relay.
- **Dependencies.** M5 framework, S1 Linear items, D18.
- **Exit.** PRD AC-04 and AC-05 pass with real systems.

### M7 — Knowledge + Notion (band L)

- **Outcome.** Operational knowledge is linked, owned, verified against source revisions and kept fresh. Evidence and audiences become real.
- **Features.**
  - Linked knowledge (wraps a source record) and native knowledge (editor; 7 types).
  - Verification tied to source revision hash; stale on change or window expiry.
  - Review queue.
  - Dispute with reason.
  - Knowledge on responsibilities/assets.
  - FTS + trigram search (⌘K) across all entities using `visible()`.
  - Notion connector with **admin visibility mappings** (D3) and default-restrictive unmapped pages.
  - Evidence records and the **evidence pool admission service** (audiences per D2), including the consent "share into case?" inbox item for single-holder evidence.
  - Retention jobs (D13, D22).
- **Database.** `knowledge_item`, `knowledge_version`, `verification`, `statement` (human-authored only, until M8), `evidence`, `evidence_pool_entry` (activated), `visibility_mapping`, FTS columns/indexes, `retention_job`.
- **Testing.**
  - Stale-on-change.
  - Verification can't be performed by the system actor.
  - Mapping changes take immediate effect.
  - Unshared Notion page → withdrawn on the next reconcile.
  - **Canary-string tests**: restricted content never visible to non-audience users in search, capsule placeholders or counts.
  - Retention deletes chunks and excerpts.
- **Security.** Mapping-change audit + preview (page count and sample titles). Search permission predicates in SQL. AC-03 (revocation) and AC-07 (conflict shown manually).
- **Demo.** A Notion runbook linked to "Payment Service Operations" is edited → becomes stale → the steward verifies it from the queue. In a Departure case, Priya shares 2 of 3 private items into the pool; the receiver sees statements and an access-request task for the full page.
- **Dependencies.** M5, S1 Notion, D3, D13, D22.
- **Exit.** The evidence model is stable enough to freeze for AI evals.

### M8 — AI runtime + case analysis (band L)

- **Outcome.** Relay drafts evidence-backed impact findings and plan additions inside cases. Humans accept, edit or reject. Nothing is executed without approval.
- **Features.**
  - Capability registry (versioned, kill switch).
  - LLM gateway (`LLMPort`, Anthropic default, model tiers, budgets per run/tenant, prompt caching, token/cost accounting).
  - Tool Gateway (read-only, actor-scoped, ID allowlists).
  - Context Builder (`case_all` pool only).
  - Output validator (schema, citation IDs, URL allowlist, audience).
  - Proposal tray.
  - Run viewer (admin) + inline run summary (case).
  - Skills: `classify_relevance`, `synthesize_impact`, `propose_plan_additions`, `propose_responsibility_grouping` (for suggestions).
  - Eval harness + CI gate.
- **Backend.** `intelligence` module; workflow steps with `input_hash` idempotency; SSE progress via NOTIFY.
- **Database.** `capability`, `workflow_instance`, `workflow_step`, `agent_run`, `agent_run_event`, `llm_call`, `proposal`, `tenant_ai_budget`, `eval_result`.
- **Testing.**
  - Eval suite on the synthetic org (≈30 cases including prompt-injection pages, conflicting docs, missing sources, restricted canaries).
  - Gate on: citation validity 100%, unsupported-claim rate, injection pass rate 100%, audience leakage 0.
  - Provider failure → degraded banner, manual flow intact.
  - Budget exceeded → stop.
  - Worker crash mid-run → resume from the last step (AC-10).
- **Security.**
  - No write tools exposed to LLMs (asserted by a test over the registry).
  - Untrusted-content delimiting.
  - Sanitised rendering (no remote images).
  - Raw prompt capture off by default.
  - Model provider terms confirmed (D10).
- **Demo.** "Analyse case" on the seeded Transfer produces 6 findings (each with sources), 1 marked "AI inference, weak evidence", and 4 proposed tasks. Reject one with a reason. Flip the kill switch → the capability is disabled and the case keeps working.
- **Dependencies.** M7, S3, D6, D10, D2 behaviour.
- **Exit.**
  - Eval gate is green in CI.
  - Acceptance/edit/reject metrics are captured.
  - PRD AC-02 passes (partial-source banner).

### M9 — Interviews, Capsules, Return Briefing (band L)

- **Outcome.** Capturing tacit knowledge and onboarding the receiver become low-effort and evidence-linked. This delivers the full PRD Appendix A demo.
- **Features.**
  - Interview agent: question cards with a "why asked" reason; answers can be unknown / N/A / can't share; brain-dump structuring; optional follow-up chat.
  - Knowledge Review skills (draft from answers, compare revision, conflict check scoped to shared subjects).
  - Briefing composer: Capsule per viewer (D9), AI section summaries with citations.
  - AI Return Briefing (replaces the M4 manual digest when connectors exist).
  - Access-request tasks.
- **Testing.**
  - Interview never asks questions already answered by verified statements.
  - Every summary sentence maps to a citation (uncited sentences are dropped).
  - Per-viewer capsule audience tests.
  - Evals extended.
- **Security.** Interview answers carry an author-chosen audience. Emergency mode disables interviews for the unavailable person.
- **Demo.** The full PRD Appendix A script, including one negative path (stale Notion connector or permission denial).
- **Dependencies.** M8, D9.
- **Exit.** PRD AC-01 (full), AC-06 and AC-08 pass.

### M10 — Pilot hardening (band L, scope chosen by the pilot)

- **Candidates** (pick by the pilot's needs):
  - Insights v1 (coverage, case outcomes, knowledge health, AI quality).
  - Weekly Risks digest.
  - Scoped Ask (needs hybrid search: pgvector + embeddings, D10).
  - Onboarding playbook.
  - Approver delegation.
  - Transparency page.
  - SSO (WorkOS).
  - Data export.
  - Billing (D19).
  - Accessibility audit fixes.
  - Load test on the realistic connector sizes.
  - External pentest.
  - Nightly live connector tests.
  - Runbooks (deploy, restore, incident).
- **Exit.** PRD Appendix C launch checklist complete for the pilot's scope.

---

## 5. Architecture guardrails (non-negotiable; enforced by CI where possible)

| # | Guardrail | Enforcement |
|---|---|---|
| G1 | Tenant comes only from the verified token and membership | Code review + route test |
| G2 | Every tenant table has `tenant_id`, RLS enabled **and forced**, and a fail-closed policy | Migration lint |
| G3 | Every unique key includes `tenant_id`; FKs are composite `(tenant_id, id)` | Migration lint |
| G4 | No application role has `BYPASSRLS`; cross-tenant work fans out per tenant (D26) | DB role check in CI |
| G5 | Every command service method calls `authorize()`; every list/search uses `visible()` | Static check (decorator registry) + generated permission tests |
| G6 | Modules import only each other's `public` API | import-linter |
| G7 | Pydantic DTOs ≠ ORM models; `extra="forbid"` on inputs | Lint/test |
| G8 | No lazy loading in async paths (`lazy="raise"`) | Test config |
| G9 | Facts with periods use `tstzrange` `[)`; mutations write change rows; no hard deletes of history | Review + tests |
| G10 | Domain writes and their events share a transaction (outbox); handlers are idempotent | Tests |
| G11 | Commands with side effects require `Idempotency-Key`; external writes only via the Action Executor | Tests |
| G12 | LLMs hold no write tools; LLM output becomes proposals only; never `verified` | Registry test |
| G13 | AI context only from audience-eligible pool entries; output audience = narrowest input | Validator + canary tests |
| G14 | No sensitive content in logs or notifications; raw prompt capture off by default | Log scrubber tests |
| G15 | No new infrastructure (Redis, vector DB, Temporal, graph DB, broker, microservice) without an ADR showing that a named trigger was met | Founder sign-off |
| G16 | No production dependency with an AGPL/GPL/SSPL/BSL/SUL licence; SBOM generated each build | Licence scanner |
| G17 | The frontend never contains business rules or DB access; Python is the only backend | Review |
| G18 | No migration drops or renames in the same release as the code change (expand/contract) | Review checklist |

## 6. Definition of Done

**Every milestone:**
1. The demo scenario runs on **staging** from a clean seed, scripted where possible.
2. All guardrail checks green. Generated tenant-isolation and permission tests cover every new route and action.
3. Unit + DB integration tests for all new domain rules. State machines have property tests.
4. Every new screen has empty, loading, error, no-permission and stale/partial states (where data-driven).
5. Keyboard path through the new primary flows. Status is never shown by colour alone.
6. Migrations are reviewed by the founder line by line (RLS, constraints, grants).
7. An ADR for any deviation from the Blueprint or Register.
8. A short changelog entry plus updated seed/demo data.
9. No `TODO` touching security, tenancy or permissions left open.
10. Re-estimate the remaining milestones from actual effort.

**Milestone-specific exit criteria** are listed in §4.

## 7. Testing strategy (founder-scale)

| Layer | Always (from M0) | Added at |
|---|---|---|
| Domain unit + Hypothesis state machines | ✓ | — |
| DB integration (testcontainers Postgres + pgvector) | ✓ | — |
| Generated tenant-isolation route matrix | ✓ | — |
| Generated permission matrix from registry | ✓ | — |
| Migration lint (RLS/unique/FK/grants) | ✓ | — |
| Fake-clock workflow tests | — | M3 |
| Playwright E2E: one happy path + one negative path per milestone | ✓ (growing) | — |
| Connector contract tests with recorded fixtures | — | M5 |
| Executor idempotency/fault injection | — | M6 |
| Canary-string leakage tests (search, capsules, AI context) | — | M7 |
| Agent evals + CI gate | — | M8 |
| Live connector nightly, load, accessibility audit, pentest | — | M10 |

Generated test suites (isolation and permissions) matter most for an AI-assisted solo build. They stop an assistant, or a tired founder, from shipping a route without authorisation.

## 8. Founder-led development strategy

### 8.1 Roles

| Who | Primary use | Must not |
|---|---|---|
| **Founder** | Decisions, priorities, design-partner conversations, final review of migrations, `authorize()`/`visible()` code, RLS policies, prompts, connector scopes | Delegate approval of security-relevant changes |
| **Claude** | Implementation of slices, tests, migrations (drafted), refactors, technical research, code review of its own and others' diffs against the guardrails | Merge without founder review; add infrastructure; change decisions silently |
| **ChatGPT** | Product thinking, UX critique, second-opinion review of ADRs and risky diffs, copywriting | Be the only reviewer of security changes |

### 8.2 Working loop per slice

A slice is about one PR, typically a few sessions.

1. **Slice brief** (founder, 5–10 lines): outcome, acceptance criteria, decisions touched.
2. **Design note** (Claude): tables, endpoints, permissions and events touched, plus the test list. The founder approves it before any code.
3. **Implement** (Claude), with tests written alongside the code.
4. **Self-review** (Claude) against the §5 guardrails and the §6 checklist, as a written report in the PR.
5. **Second review** (ChatGPT) for risky slices: migrations, auth, permissions, AI context.
6. **Founder review and merge.** Deploy to staging and run the demo step.

### 8.3 Keeping AI sessions effective and token-efficient

- Keep `CLAUDE.md`/`AGENTS.md` short and authoritative: layout, layering, guardrails, commands, test conventions. Reference the Register and this plan instead of pasting them.
- One slice per session. Start each session with the slice brief and the relevant ADRs only.
- Prefer generated artefacts (OpenAPI client, permission/test matrices) over hand-maintained duplicates. They reduce both drift and the context needed.
- Keep docs as the memory: decisions in ADRs, not in chat history.

### 8.4 Scope-control rules

- New feature ideas go into a backlog file, not into the current milestone.
- If a milestone grows beyond its band by about 50%, stop, split it, and re-plan with an ADR.
- A milestone that slips must cut features, never guardrails.

### 8.5 Design-partner involvement

No user research exists yet. Every product assumption in the Register (U9) is unvalidated.

[REC] Find 2–3 design partners (engineering-led teams of roughly 20–200 people) before M3's scope freezes. Show them the M2 build (catalogue + risks) and validate:
- (a) whether they'd maintain a catalogue;
- (b) how often they do coverage and transfers;
- (c) whether Departure framing and readiness verification are acceptable.

Adjust M3/M4 based on what you hear.
