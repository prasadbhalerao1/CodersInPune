# Relay — Architecture and Product Implementation Blueprint

| Field | Value |
|---|---|
| Version | 0.1 — for review |
| Date | 8 Nov 2026 |
| Inputs | `docs/round1/relay_srs_prd.md` (PRD/SRS v1.0), `docs/round1/Relay_Competitive_Study_Open_Source_Review.md` (v1.0) |
| Status | Proposal. Nothing here is approved until reviewed. No code has been written. |

## How to read this document

Every substantive statement is tagged so you can see where it comes from:

| Tag | Meaning |
|---|---|
| **[SPEC]** | Explicitly stated in the PRD/SRS or competitive study. Section references like `PRD §9.5` or `FR-CASE-008` point to the source. |
| **[REC]** | My architectural or product recommendation. Each one gives its reasoning. |
| **[NEW]** | A feature or requirement I propose that is not in either document. |
| **[ASSUME]** | An assumption that needs validation (a customer interview, an API spike or legal review). |
| **[CHANGE]** | A recommendation that modifies or reverses something the spec states. The reason is always given. |

Priorities use the PRD's scheme: **P0** = needed for the first usable release, **P1** = needed before paid pilots, **P2** = later.

---

## 0. Executive summary

**What we're building.** Relay is the system of record for *who is accountable for what*, together with a managed workflow for *moving that accountability safely when something changes*. Its knowledge, AI and integrations exist to make those two things accurate and cheap to maintain. They are not the product on their own.

**The architecture in one paragraph.** One Next.js frontend, and one Python modular monolith (FastAPI) running two process types: `api` and `worker`. PostgreSQL is the single source of truth and also provides the job queue, full-text search, vectors (pgvector) and row-level security. Case workflows run on a deterministic, database-persisted workflow engine. AI runs as typed *capabilities* (steps) inside that engine. LLMs only ever produce **proposals**. They never hold tools that write to external systems. Approved proposals are executed by deterministic code with idempotency keys and receipts. There is no Redis, Celery, Temporal, LangGraph, Neo4j, Qdrant or microservice in the first release. Each section below names the condition that would justify adding one later.

**The five biggest problems in the current specification** (detail in §B):
1. **Cold start.** The product depends on a responsibility catalogue that no customer has on day one, and the spec has no feature for populating it.
2. **The hero story contradicts the scope.** Every narrative (§1.3, Appendix A, the first JTBD row) is about an engineer *leaving*, but offboarding is marked "later phase".
3. **Source-permission mirroring is assumed but is not fully achievable** with the chosen first connectors. Notion in particular does not appear to expose per-user page permissions through its API [ASSUME — spike S1].
4. **Ten "agents" where about three need an LLM loop.** Most listed agents are deterministic logic. Keeping them as LLM agents adds cost, latency and failure modes without adding value.
5. **Inconsistent core taxonomies.** These include four different fact/inference label sets, case "roles" mixed into RBAC, an 11-state case machine that mixes lifecycle with conditions, and two separate ownership systems (responsibilities and assets).

**The most important decisions to make** (full list in §P): the ownership model (D1), how the evidence pool and source permissions work (D2, D3), whether a light Departure playbook ships in v1 (D4), the workflow engine and queue (D5), the LLM framework (D6), the auth provider (D7), and the hosting and data region (D8).

**Proposed sequence** (§O): first a manual, AI-free continuity product (catalogue → coverage risks → manual transfer cases), then connectors that bootstrap the catalogue, then knowledge with verification, then AI capabilities layered onto workflows that already work. Each milestone produces something a pilot customer could use.

---

## A. Product understanding

### A.1 Relay in my own words

Organisations already have systems of record for people (the HRIS), work (Linear/Jira), code (GitHub) and documents (Notion/Confluence). None of them is the system of record for **accountability that outlives a single task**: "Priya runs payment-service deploys, Arjun is her backup, the runbook is here, and Finance must be told before any schema change." That information sits in people's heads, CODEOWNERS files, project-lead fields and tribal knowledge.

Relay makes that accountability **explicit, time-aware and evidenced**, then makes it **transferable**. When someone leaves, goes on leave, changes teams, or when a project or service changes hands, Relay opens a Continuity Case. The case works out what is affected, assembles the context the receiver needs, coordinates the work across the tools where it actually happens, and closes only when the transfer has been verified.

### A.2 Central value proposition

> **Relay makes accountability transferable — and proves the transfer happened.**

Three supporting claims, in order of how hard they are for competitors to copy:
1. **A time-aware responsibility and coverage model across functions.** Who owns what, who backs them up, and since when, for services, processes, accounts and projects, not just software.
2. **Verified transfer.** A case does not close because a document was generated. It closes because tasks, approvals and readiness criteria are met, or because an exception is explicitly accepted, and then the ownership record changes on the effective date.
3. **Continuous continuity hygiene.** Missing backups, single-person dependencies, stale critical runbooks and owners who have been deactivated show up as an actionable backlog *before* a disruption.

### A.3 The two engines, and why both matter commercially

| Engine | Cadence | What it produces | Why it matters |
|---|---|---|---|
| **Catalogue engine** (Responsibilities, Coverage, Knowledge freshness, Risks) | Continuous / weekly | Accurate ownership, coverage gaps, review queues | This is the **recurring** value. Without it, Relay is used only when someone leaves, and episodic tools churn. |
| **Case engine** (Transfers, Absence, Onboarding, Departure…) | Episodic | Managed, verified transfers | This is the **acute** value and the demo story. It also *feeds* the catalogue, because every case corrects ownership records. |

[REC] Both engines must ship in the first release. A cases-only product is an offboarding checklist. A catalogue-only product is a weaker OpsLevel.

### A.4 Core loop

```
             ┌───────────────────── Catalogue (steady state) ─────────────────────┐
             │ Responsibilities ─ Ownership history ─ Assets ─ Knowledge ─ Sources │
             └───────▲──────────────────────────┬──────────────────────────────────┘
                     │ ownership updated          │ rules detect gaps / changes
                     │ on effective date          ▼
   Close & retain ◄── Verify ◄── Coordinate ◄── Plan ◄── Assess impact ◄── Case opened
   history            readiness   approved        (proposed,    (evidence      (manual, risk,
                                  actions         reviewed)      pool)          or trigger)
```

### A.5 Why engineering first is a sound entry point, not a limitation

[REC] Engineering organisations already keep *machine-readable* ownership signals: CODEOWNERS, Backstage `catalog-info.yaml`, Linear project leads, GitHub team maintainers. Relay can therefore populate its catalogue quickly and show value within an hour. Other functions rarely have that. The generic model (Responsibility → Asset of any type → Knowledge) is what carries Relay into other departments. Engineering-specific fields go into typed asset metadata, never into core tables.

---

## B. Product audit

### B.1 What the spec gets right (keep these)

- Responsibility + Continuity Case as the two primary objects. This is the right abstraction.
- Explicit refusal to do performance scoring, surveillance or autonomous employment actions.
- Evidence-first outputs, labelling of AI inference, human approval for consequential actions.
- Modular monolith, PostgreSQL as the source of truth, "no Redis/Celery by assumption".
- A strong edge-case catalogue (§17) and acceptance scenarios (§18.2). These become the test plan almost directly.
- Graceful incompleteness: manual workflows must keep working without integrations or AI.

### B.2 Contradictions

| # | Where | Contradiction | Recommendation |
|---|---|---|---|
| C1 | PRD §6.2 vs FR-CASE-002 vs §19.2 | Initial case types are listed as 4 (including project handover) in §6.2 and as 3 elsewhere. | [CHANGE] v1 ships **one transfer primitive** and four playbooks: *Responsibility Transfer* (covers ownership, service and project handover), *Temporary Coverage*, *Onboarding*, and a light *Departure* playbook (see C2). |
| C2 | §1.3, Appendix A, JTBD row 1 vs §6.2/§9.9 | The hero story is a departing engineer, but offboarding is "later phase". | [CHANGE] Ship a **Departure** playbook in v1 *without* HRIS integration. A departure is a parent case that spawns one Transfer per responsibility the person holds, plus the consent/review step from ServiceNow's pattern. HRIS-triggered offboarding stays P2. Without this, the demo story describes a feature that isn't in the release. |
| C3 | §7.1, §9.4, §10.7 `basis`, FR-KNOW-014 | Four different label sets for facts and inferences ("verified fact / source observation / AI inference / human decision"; "direct source fact / deterministic rule / AI inference / human decision"; etc.). "Verified" is a *status*, not a *basis*. | [CHANGE] Use **two orthogonal fields** everywhere. `basis` ∈ {`source_observed`, `rule_derived`, `human_stated`, `ai_inferred`}. `verification` ∈ {`unverified`, `verified`, `disputed`, `stale`}. One UI chip vocabulary. (§I.4) |
| C4 | §8.1 role catalogue and §8.3 matrix | "Current/Outgoing Owner" and "Incoming Owner" are listed as roles, but they are *relationships to a specific case*. Mixing them into RBAC produces rules like "Incoming Owner: create case — no by default", which makes no sense. | [CHANGE] Three tiers: workspace roles, scoped grants and relationship roles (§F). |
| C5 | PRD §10.3 vs study §10.2 vs PRD §19.2 | Three different agent catalogues: Coordination, Simulation, Onboarding Guide and Incident Assistant appear in some and not others. | [CHANGE] One capability registry (§I.2). Most items become deterministic services. |
| C6 | FR-CASE-008 vs §17.1 | §17.1 uses an "Awaiting Assignment" state that is not in the state list. "Blocked" and "Reopened" are conditions or transitions, not lifecycle stages. | [CHANGE] A 6-stage lifecycle plus orthogonal flags (§K.3). |
| C7 | §6.5 / FR-ASSET-003 vs §9.3 / FR-RESP | Both Assets and Responsibilities "have owners", so there are two ownership systems that will disagree. | [CHANGE] Decision D1: **ownership assignments attach only to Responsibilities.** An asset's "owner" is derived from the responsibility that stewards it. Importing from GitHub creates "Maintain *payment-service*" responsibilities automatically. |
| C8 | PRD §7.2 vs study §11.1 vs your screen list | "Projects & Systems" is primary nav in one place and absent elsewhere. "Continuity Debt / Insights" is merged into one item. | [CHANGE] Assets live as a tab under Responsibilities. Risks (work queue) and Insights (reports) are separate (§H). |
| C9 | §10.5 "initiating user's permissions" vs Continuity Monitor and absence change-tracking | Background jobs have no initiating user. | [REC] Define a **system actor** with an explicit policy scope. Its outputs are visible only through per-viewer filtering (§M.4). |
| C10 | §2.5 "not a chatbot" vs FR-SEARCH-003 (P0 AI answers) | Unclear whether there is a general "Ask" surface. | [REC] Scoped Ask *inside* a case, responsibility or knowledge item is P1. Global search returns records (P0). A global AI answer panel is P2. |
| C11 | "Knowledge Steward" is both a persona and an agent name | Naming collision in UI, docs and permissions. | [CHANGE] Rename the capability to **Knowledge Review**. "Knowledge Steward" stays a human role. |
| C12 | Study §9.4 "portable package" vs PRD §6.6 "links/excerpts, permission-checked" | An exported ZIP cannot re-check permissions after export. | [REC] Decision D9: a capsule is a **live, per-viewer rendered view** (P0). A frozen export is P2, admin-gated and audited, and includes an omissions report (knowledge-transfer pattern). |
| C13 | §10.3-H Readiness Verifier as an agent vs FR-TASK-011 | Readiness is mostly deterministic (criteria met or not). Treating it as an AI agent encourages exactly the "AI says ready" claim the spec forbids. | [CHANGE] Readiness is a deterministic evaluator. The LLM may only *summarise free-text evidence for a human reviewer* and can never output `pass`. |

### B.3 Ambiguities that need a definition

| # | Ambiguity | Proposed definition |
|---|---|---|
| A1 | "New-owner onboarding" (FR-CASE-002) vs "new employee onboarding" (§9.7) | Two different things. *Receiving a responsibility* is part of every Transfer. *Onboarding a new hire* is a separate playbook with no outgoing owner. |
| A2 | Criticality: who sets it and what it means | 4 tiers with workspace-editable definitions: `critical / high / standard / low`. Team managers set up to `high`; `critical` requires Continuity Manager or Admin approval. Each tier drives a policy (e.g. critical ⇒ backup required, review every 90 days, closure needs separate approver). |
| A3 | What "readiness" means | Typed criteria (§C.3.6): attestation, task-completed, artefact-linked, supervised-demonstration sign-off, access-confirmed, Q&A reviewed. A criterion always resolves to a *human or system event*, never an AI judgement. |
| A4 | "Confidence" (§10.7: "calibrated") | LLM self-reported confidence is not calibrated. [CHANGE] Replace it with deterministic **evidence strength** (`strong / moderate / weak / none`), computed from the evidence count, the authority of each source, recency and whether a human confirmed it. |
| A5 | Approval "bound to content version" (FR-TASK-007) | An approval stores `subject_type, subject_id, subject_version, content_hash` (SHA-256 of the canonical JSON of the proposal). Execution re-hashes and refuses on mismatch. |
| A6 | "Relevant changes during absence" (§9.6) | **Asset-scoped, not person-scoped.** Collect events on the responsibilities and assets that were covered, never the absent person's own activity. This keeps it from becoming surveillance. |
| A7 | "Ownership mismatch with observed system state" (FR-CI-004) | Compare *declared* sources only: CODEOWNERS, `catalog-info.yaml`, Linear project lead, Notion page owner vs. Relay records. Never commit volume. |
| A8 | What "complete" means for multi-responsibility cases | A case contains **scope items** (one per responsibility). Each has its own state. The case completes when every item is `transferred`, `retained` or `excepted`. |
| A9 | Template versioning for in-flight cases | Cases pin a playbook version at creation. A playbook update never changes in-flight cases unless an admin explicitly migrates them. |

### B.4 Missing requirements

| # | Missing | Why it matters | Proposed | Priority |
|---|---|---|---|---|
| M1 | **Catalogue bootstrap** | No customer has a responsibility catalogue. Without one, cases can't discover anything and risks can't fire. This is the #1 adoption risk. | [NEW] *Ownership Suggestions*: derive candidate responsibilities from CODEOWNERS, `catalog-info.yaml`, GitHub team maintainers, Linear team/project leads and Notion page owners. Admins and managers review them in bulk (accept / edit / merge / reject). | P0 |
| M2 | **CSV/sheet import** | Non-engineering departments and integration-less orgs need a way in. | [NEW] Import people, teams and responsibilities from CSV with a dry-run preview and per-row errors. | P0 |
| M3 | **Scope items within a case** | Real cases move 3–10 responsibilities, often to *different* receivers. | [NEW] `case_scope_item` (responsibility, from, to, effective date, state). Tasks, readiness and knowledge hang off items. | P0 |
| M4 | **Workspace first-run setup** | Time-to-value. | [NEW] Setup checklist: teams → people → connect GitHub → review suggestions → set criticality → see first risks. | P0 |
| M5 | **Comments and @mentions** on cases, items, tasks and knowledge | Coordination happens in conversation. Without comments, users go back to Slack and the record is lost. | [NEW] Threaded comments, mentions → inbox. | P0 |
| M6 | **Reminders, escalation, timers, working calendars, time zones** | Cases stall (PRD risk table). | [NEW] Per-playbook reminder and escalation policies. Due dates stored as local date + case time zone. Escalation goes to the case coordinator, then the scoped manager. Reminders are capped. | P0 |
| M7 | **Access prerequisites as first-class items** | The incoming owner must *not* inherit source permissions (§17.6), so they will hit "can't see the runbook". | [NEW] When a capsule item is not visible to the receiver, Relay generates an **access-request task** addressed to the source admin. Relay never grants access. | P0 |
| M8 | **Relay-native knowledge editor and Notion write-back policy** | Interview answers and handover notes need an editor. "Draft updates, never overwrite" has no defined UX. | [REC] A lightweight rich-text/Markdown editor for Relay-native items. For Notion: v1 produces a *proposed change* that the owner applies in Notion. Append-only write-back ("add a Relay handover callout block") is P2 and approval-gated. | P0 / P2 |
| M9 | **Deactivated-owner detection** | When a user is suspended or deactivated in Relay (or later via SCIM), their responsibilities silently go unowned. | [NEW] A rule that raises a critical finding immediately and suggests a Departure case. | P0 |
| M10 | **Delegation / fallback approvers** | Approvers go on leave too (§17.4 "person unavailable for approval"). | [NEW] Out-of-office delegation for approvals, plus a policy-defined fallback chain. | P1 |
| M11 | **"What Relay knows about me"** transparency page | Employee trust is the hidden adoption risk. If staff think Relay is surveillance, interviews fail. | [NEW] Each person can see their responsibilities, cases that involve them, the statements attributed to them, and their consent history. | P1 |
| M12 | **Billing, plans and usage metering** | It's meant to be a SaaS product. | [REC] Plan limits (seats, connectors, AI budget). Stripe integration P1. Metering of AI spend per tenant is P0 anyway for budgets. | P1 |
| M13 | **Customer data export and tenant deletion** | Enterprise procurement and DPA requirements. | [NEW] Full tenant export (JSON + attachments) and verified tenant deletion job. | P1 |
| M14 | **Responsibility templates per department** | Cross-functional expansion (G6). | [NEW] Template library: e.g. "Customer account owner", "Payroll approver", "On-call primary" with suggested knowledge types and readiness criteria. | P1 |
| M15 | **Evidence pool and consent rule** | The spec says "manager authority ≠ access to everything the employee authored" (§8.4) but gives no mechanism. | [NEW] §M.4. | P0 |
| M16 | **Audit vs activity separation** | The PRD conflates the security audit log with the product activity timeline. They have different retention, access and integrity needs. | [REC] Two stores (§K.2). | P0 |
| M17 | **MCP / public API** | AI coding agents asking "who owns X / what's the runbook" is a natural distribution channel. SourceAnt already does this for engineering. | [NEW] Read-only, permission-filtered MCP server and REST API. | P2 |
| M18 | **Legal/commercial: DPA, subprocessors, LLM zero-retention terms** | Customer content is sent to model providers. | [REC] Decide the model provider and data terms before the first pilot (D10). | P0 (decision) |

### B.5 Impractical or over-complicated as written

| # | Item | Problem | Recommendation |
|---|---|---|---|
| I1 | **Source ACL mirroring** (FR-INT-010, AC-03) for all connectors | GitHub: feasible (repo visibility, team and collaborator access). Linear: team-level access, including private teams, is likely feasible. **Notion: the public API does not appear to expose who can see a page.** An integration only sees pages shared with it [ASSUME — spike S1]. | [CHANGE] Per-connector permission strategy (§M.3). For Notion, use admin-defined **visibility mappings** (teamspace/page tree → Relay teams), optionally confirmed by per-user OAuth checks at read time. State this limitation honestly in the connector UI. |
| I2 | "Calibrated confidence" | Not achievable from LLM outputs without labelled data. | Deterministic evidence strength (A4). |
| I3 | Global contradiction / duplicate detection (FR-KNOW-007) | This is O(n²) and LLM-expensive across a whole corpus, with many false positives. | Scope comparisons to items **linked to the same responsibility or asset**, triggered by changes. Use embedding similarity as the candidate filter and an LLM only for the final pairwise check. P1. |
| I4 | Ten agents (§10.3) | Each LLM agent adds latency, cost, eval burden and prompt-injection surface. | 6 LLM *skills* + 2 bounded agents. Everything else is deterministic (§I.2). |
| I5 | 11-state case lifecycle | Hard to reason about and hard to test. Several states derive from task state. | 6 stages + flags (§K.3). |
| I6 | Handover Rehearsal with sandbox tasks | Building sandbox infrastructure is a product of its own. | v1: supervised demonstration with sign-off by a named verifier. Sandbox links are just artefacts. P2 for anything richer. |
| I7 | Bi-directional external task sync for every system | Conflict resolution across systems is a deep rabbit hole. | v1: Relay creates the external task (approved), then **pulls** status. Relay never edits external tasks after creation except to close them through an approved action. |
| I8 | Separation of duties by default | Small orgs (the ICP) will be blocked. | Off by default. On for the `critical` tier. Exceptions are recorded (as the spec already allows). |
| I9 | Continuity Simulation (§10.3-J) as an AI feature | It is a query, not an AI problem. | [CHANGE] **"Who's irreplaceable?"**: a deterministic query listing responsibilities where person X is the only active primary or backup. Cheap, valuable, P1. |
| I10 | Decision Lineage, Incident-to-Knowledge | Valuable but each is a sub-product. | P2. Keep the `decision` knowledge type and `supersedes` relation in the v1 schema so it doesn't need a migration later. |

### B.6 Overlap between modules

| Overlap | Resolution |
|---|---|
| Overview vs My Work | Overview = situational awareness (role-aware, read-mostly). My Work = actionable inbox. Overview shows *at most* the top 5 inbox items, with a link. |
| Continuity Debt vs Insights | Risks = work queue of findings (triage, assign, resolve). Insights = reports and trends. They are separate screens. |
| Responsibilities vs Assets vs Projects & Systems | One "Catalog" area: Responsibilities (primary) and Assets (secondary tab). |
| Knowledge Steward (agent) vs Knowledge Steward (role) vs Knowledge review queue | Human role = Steward. Capability = Knowledge Review. Queue = Knowledge › Review tab and My Work. |
| Context Capsule vs Return Briefing vs Onboarding path | One **briefing composer** service with three templates: Capsule (for receivers), Return Briefing (for returners) and Onboarding Path (for new hires). |
| Coordination Agent vs Notifications vs Task creation | One deterministic **Action Executor**. Notifications are just another action type. |

### B.7 Product risks (additions to PRD §21.1)

| Risk | Why | Mitigation |
|---|---|---|
| Cold-start catalogue | Covered in M1. | Ownership suggestions, CSV import, "first case seeds the catalogue". |
| Episodic usage → churn | Departures are rare per team. | Temporary Coverage (frequent), weekly Risks digest, knowledge review cadence. |
| Employee distrust | "My manager is mining my docs." | Consent step, evidence pool, transparency page, no person-activity metrics. |
| Bundling by incumbents | Atlassian, Glean or ServiceNow could ship "handover" inside their suites. | Win on cross-tool, cross-function responsibility records and verified closure. Target mid-market engineering-led orgs that don't run ServiceNow HRSD [ASSUME]. |
| Permission leakage via AI synthesis | A synthesised paragraph can leak restricted content even when citations are filtered. | Evidence pool (§M.4): synthesis only reads evidence every case viewer may see, or that was explicitly shared. |

---

## C. Final product modules

Module hierarchy (P0 = first usable release):

```
1  Workspace & Identity      2  Catalog                     3  Continuity Cases
   1.1 Workspace setup  P0      2.1 Responsibilities  P0       3.1 Playbooks           P0
   1.2 Members & invites P0     2.2 Ownership & history P0     3.2 Case creation       P0
   1.3 Teams & depts    P0      2.3 Coverage policy   P0       3.3 Scope items/transfers P0
   1.4 Identity mapping P0      2.4 Assets & deps     P0       3.4 Plan & tasks        P0
   1.5 SSO/SCIM         P1/P2   2.5 Ownership suggest. P0      3.5 Approvals & consent P0
                                2.6 CSV import        P0       3.6 Readiness           P0
                                2.7 Irreplaceable q.  P1       3.7 Closure & effective-dated switch P0
                                2.8 Relationship graph P2      3.8 Case activity       P0
4  Knowledge                 5  Risks (Continuity Debt)     6  Work & Communication
   4.1 Linked knowledge P0      5.1 Rules engine      P0       6.1 My Work inbox       P0
   4.2 Native knowledge P0      5.2 Findings triage   P0       6.2 Notifications/email P0
   4.3 Verification     P0      5.3 Prioritisation    P1       6.3 Reminders/escalation P0
   4.4 Review queue     P0      5.4 Remediation→case  P0       6.4 Comments/mentions   P0
   4.5 Interviews       P0                                     6.5 Digests             P1
   4.6 Briefings/capsules P0 7  Insights                    8  Integrations
   4.7 Search           P0      7.1 Coverage report   P1       8.1 Connector framework P0
   4.8 Scoped Ask       P1      7.2 Case outcomes     P1       8.2 GitHub / Linear / Notion P0
   4.9 Conflict detect. P1      7.3 Knowledge health  P1       8.3 Health & diagnostics P0
                                7.4 AI quality        P1       8.4 Approved write actions P0
9  Intelligence (admin)      10 Governance
   9.1 Capability registry P0   10.1 Roles & permissions P0   10.4 Retention & deletion P0/P1
   9.2 Run viewer       P0      10.2 Audit log         P0     10.5 Data export        P1
   9.3 Policies/budgets P0      10.3 Workspace settings P0    10.6 Billing            P1
   9.4 Evals dashboard  P1                                    10.7 Transparency page  P1
```

Below, each feature has: **Problem · Function · Users · In → Out · Depends on · AC** (acceptance criteria).

### C.1 Workspace & Identity

**1.1 Workspace setup** — P0 [SPEC FR-ORG-001, NEW checklist]
- Problem: Admins don't know what to configure first, so time-to-value is long.
- Function: Create the workspace, set the time zone and criticality definitions, then follow a guided setup checklist (M4).
- Users: Workspace Owner, Admin. In → Out: org details → workspace + checklist state. Depends on: auth.
- AC: A new owner reaches "first risks visible" without docs. Every checklist step can be skipped and resumed later. Skipping integrations leaves a fully manual workspace usable.

**1.2 Members & invitations** — P0 [SPEC FR-IAM-004, FR-IAM-009]
- Function: Invite by email or domain. States: pending, active, suspended, deactivated. Member types: employee, contractor, guest.
- AC: Deactivating a user ends their sessions within the configured window, keeps their historical attribution, and fires the deactivated-owner rule (M9).

**1.3 Departments & teams** — P0 [SPEC FR-ORG-002/003/004]
- Function: Hierarchy (department → team, optional), memberships with effective dates, team leads.
- AC: Membership changes are historised. "Members of team T on date D" is queryable.

**1.4 Identity mapping** — P0 [SPEC §12.5, FR-IAM-006/007, FR-ORG-007/008]
- Function: Link Relay users to GitHub/Linear/Notion identities. Auto-match only on verified email. Everything else is a suggestion. Admins resolve conflicts.
- In → Out: connector identities → `identity_link` (state: `suggested / confirmed / rejected`).
- AC: Users are never merged on display name. Unmatched identities are listed. Signals attributed to an unmatched identity never create ownership suggestions for a Relay user.

**1.5 SSO (OIDC/SAML) P1, SCIM P2** [SPEC FR-IAM-008]
- Comes from the auth provider (D7). SCIM deprovisioning triggers M9.

### C.2 Catalog

**2.1 Responsibilities** — P0 [SPEC §6.3, §9.1, FR-RESP-*]
- Problem: Accountability is implicit and scattered.
- Function: CRUD and archive. Fields: name, description, type (from a template library), criticality, owning team, escalation path, review cadence, required knowledge, access prerequisites, verification state. Has a detail page with tabs: Overview, Owners & history, Assets, Knowledge, Cases, Risks, Activity.
- Users: Team Managers (edit), everyone (view within scope).
- AC: Filter by team, owner, backup, type, criticality and review state (FR-RESP-011). Inferred responsibilities show as `suggested` until confirmed (FR-RESP-010).

**2.2 Ownership assignments & history** — P0 [SPEC §9.3, §13.3, FR-RESP-002…006]
- Function: Roles `primary` (exactly one at any time per policy), `co_owner`, `backup`, `temporary`. Assignee is a user or team. A team assignment requires a named accountable contact for `critical`. Effective-dated, backdated corrections allowed (recorded with a reason), never overwritten.
- AC: "Who owned R on 1 June?" returns a correct answer, including after a backdated correction. Overlapping primaries are rejected by a DB constraint (§K.4). A future-dated assignment takes effect with no job running (temporal query).

**2.3 Coverage policy** — P0 [SPEC FR-CI-001/002, REC]
- Function: Per-criticality tier rules: backup required, max-review-age for linked runbooks, team-ownership-needs-named-contact, SoD on closure.
- AC: Changing a policy re-evaluates findings within one scheduler cycle.

**2.4 Assets & dependencies** — P0 (dependencies P1) [SPEC §6.5, FR-ASSET-*]
- Function: Generic assets with a type registry (`repository`, `service`, `project`, `process`, `account`, `vendor`, `document_collection`, custom). Typed metadata is validated against a per-type JSON schema. Assets link to source records. Dependencies are typed edges (`depends_on`, `part_of`, `escalates_to`, `documents`) with provenance.
- AC: Assets display "stewarded by responsibility R (owner X)" (D1). An archived or deleted source asset shows as unavailable, not as missing.

**2.5 Ownership Suggestions** — P0 [NEW, M1]
- Problem: The catalogue is empty on day one.
- Function: The deterministic extractor reads CODEOWNERS, `catalog-info.yaml` (`spec.owner`), GitHub team repo maintainers, Linear team leads and project leads, and Notion page/database owners. It proposes responsibilities and assignments. An LLM skill *optionally* proposes human-readable names and groupings (e.g. merging 4 repos into "Payments platform"). Bulk review UI.
- In → Out: source records → `suggestion` records → confirmed responsibilities and assignments.
- AC: Every suggestion shows its source evidence. Bulk accept requires a confirmation that names the count. Rejected suggestions are not re-proposed unless the source changes.

**2.6 CSV import** — P0 [NEW, M2]
- AC: Dry-run preview, per-row validation errors, idempotent re-import (natural keys), audit entry.

**2.7 "Who's irreplaceable?"** — P1 [CHANGE, I9]
- Function: For a person, team or department: responsibilities with a single active holder, no backup, or a backup who is the same person as the primary's backup elsewhere (concentration).
- AC: Deterministic. Shown on the person page (to permitted viewers) and as Risk findings. It must not be presented as a measure of the person.

**2.8 Relationship explorer (graph)** — P2 [SPEC FR-ASSET-007]
- Optional tab on the responsibility and asset detail pages, depth ≤ 2. Never required for any workflow.

### C.3 Continuity Cases

**3.1 Playbooks** — P0 [SPEC §9.2, CHANGE C1]
- Function: Versioned definitions *in code* (typed Python/YAML) with per-tenant parameters: stages, required participants, task templates, approval rules, readiness criteria, reminder policy, closure rules, retention class. Tenants configure parameters. There is no builder until P2/P3 [SPEC §4.3].
- v1 playbooks: **Responsibility Transfer**, **Temporary Coverage**, **Onboarding (new hire)**, **Departure (light)**. P2: Internal Move (= Departure-like, person stays), Account Handover, Emergency (a flag on Transfer/Departure in v1, see §G.7), Vendor/Process transition.
- AC: Cases pin a playbook version. Tenant parameter changes are audited.

**3.2 Case creation** — P0 [SPEC §7.7, FR-CASE-001/004/009]
- Function: A wizard with at most 4 steps: type → subject (person or responsibilities) → people & dates → scope/sources & data-use notice. Duplicate-case warning. Cases can be created from a Risk finding, a person page or a responsibility page with fields prefilled.
- AC: Creatable with zero integrations. Data-use notice text is stored with the case. The duplicate check runs on subject overlap among active cases.

**3.3 Scope items (transfers)** — P0 [NEW, M3]
- Function: One item per responsibility: `from`, `to` (may be "TBD"), assignment role to transfer, effective date, state (`proposed → confirmed → in_transfer → ready → transferred | retained | excepted`).
- AC: The case can't move to *Verifying* while any item has `to = TBD` unless the item is `retained` or `excepted`.

**3.4 Plan & tasks** — P0 [SPEC FR-TASK-001…005]
- Function: Playbook tasks are generated deterministically. AI-proposed extra tasks land in a proposal tray (§I). Each task has assignee (user or team), due date, dependencies, `native | external`, external ref and sync state, plus completion evidence.
- AC: An external task shows its source link and last-sync time. A task completed in Linear reconciles within one sync cycle.

**3.5 Approvals & consent** — P0 [SPEC §10.8, FR-TASK-006/007/008, §9.9 consent]
- Function: Approval requests are bound to a subject version and content hash (A5). The approval sheet shows: what will happen, where, who will see it, the source data involved, and whether it's reversible [SPEC §10.8]. Consent is a special approval by the outgoing owner for sharing items into the evidence pool.
- AC: An edit after approval invalidates it (material changes) or flags it (cosmetic changes, per policy). The executor refuses on hash mismatch (AC-04).

**3.6 Readiness** — P0 [SPEC FR-TASK-009/010/011, CHANGE C13]
- Criteria types: `attestation` (receiver confirms they understood X), `task_completed`, `artefact_linked` (e.g. a PR they merged), `supervised_demo` (verifier signs off), `access_confirmed` (receiver confirms access to listed systems), `qa_reviewed` (receiver's questions answered by the outgoing owner or an SME).
- Results: `pass / fail / needs_review / unable_to_assess` per criterion [SPEC].
- AC: No criterion can be passed by an AI. Document views and chat activity are never criteria.

**3.7 Closure & effective-dated switch** — P0 [SPEC §9.5 step 12, FR-CASE-012]
- Function: Closure validates the rules (all items resolved, required approvals present, readiness met or excepted with an approver). It then writes new ownership assignments effective on each item's date. Outcomes: `completed`, `completed_with_exceptions`, `cancelled`.
- AC: Critical-tier closure requires an approver distinct from the initiator (SoD, if enabled). Reopening creates a new status segment and preserves the prior closure.

**3.8 Case activity** — P0 [SPEC §7.8 Activity]
- A timeline of human actions, system events, connector changes and agent runs, each linking to its run trace.

### C.4 Knowledge

**4.1 Linked knowledge** — P0 [REC, SPEC §6.6]
- Problem: Knowledge already lives in Notion, GitHub and elsewhere. Copying it creates competing truth.
- Function: A Relay knowledge item *wraps* a source record: type, owner/steward, scope, review cadence, verification and an excerpt. Content stays in the source.
- AC: Opening a linked item shows the current source revision, the last verified revision, and "changed since verified" if they differ.

**4.2 Native knowledge** — P0 [SPEC FR-KNOW-002/005]
- Function: Relay-authored items (handover notes, interview outputs, contacts, gotchas) with an editor and immutable versions.
- v1 types [CHANGE, reduced from 11]: `procedure/runbook`, `decision`, `overview` (system/project/process), `contact/escalation`, `gotcha/known-issue`, `handover-note`, `faq`. Each type has a light structured template (e.g. a runbook has preconditions, steps, rollback, escalation). Others come later.

**4.3 Verification** — P0 [SPEC Guru lesson, REC]
- Function: "Verify" records `(verifier, at, source_revision_hash, validity_until)`. A source change produces a deterministic transition `verified → stale (changed since verified)`. Expiry of the validity window does the same.
- AC: Verification can't be performed by the system or by AI. Stale is never displayed as wrong, only as "needs re-check" [SPEC §17.2].

**4.4 Review queue** — P0 [SPEC §7.11]
- Function: Stewards and owners see stale, expiring, disputed and AI-drafted items with their evidence. Actions: verify, edit-and-verify, dispute with reason, archive, reassign steward.

**4.5 Knowledge Capture Interviews** — P0 [SPEC §10.3-E, study §9.5]
- Function: **Asynchronous question cards**, not a mandatory chat. The Interview capability generates questions from gaps (missing escalation, a runbook without rollback, an undocumented deploy). Each card shows *why it's being asked*. Answer types: text, link, "unknown", "not applicable", "can't share". There is also a free-form **brain-dump** intake: the outgoing owner pastes notes and Relay structures them into draft statements. An optional chat mode exists for follow-ups.
- AC: No question repeats something already verified. Answers carry author, time and visibility. Draft knowledge needs owner review before entering the evidence pool for other participants.

**4.6 Briefings (Capsule / Return Briefing / Onboarding Path)** — P0 (Return Briefing in M8) [SPEC §6.6, §10.3-I, CHANGE]
- Function: One composer service. Sections are deterministic (responsibilities, contacts, open work, procedures, risks, open questions). An optional LLM summary paragraph per section must cite statements. It is rendered **per viewer**: items the viewer can't see appear as "1 item requires access" plus an access-request action (M7).
- AC: Every sentence in an AI summary maps to at least one cited statement. Uncited sentences fail validation and are dropped.

**4.7 Search** — P0 (hybrid P1) [SPEC §11.5, FR-SEARCH-*]
- Function: ⌘K search across responsibilities, assets, people, cases and knowledge. Postgres FTS plus trigram for identifiers. Permission predicate applied in SQL. Hybrid semantic search (pgvector + reciprocal-rank fusion) in P1, after a retrieval eval baseline.

**4.8 Scoped Ask** — P1 [CHANGE C10]
- Function: "Ask about this case/responsibility" using the evidence pool or the viewer's visible scope. The answer is cited, states its limitations, and records feedback.
- AC: Answers never use content the asker can't access (FR-SEARCH-007). "I don't have evidence" is a valid answer and is tested for.

**4.9 Duplicate/conflict suggestions** — P1 [SPEC FR-KNOW-007, CHANGE I3]
- Scoped to items sharing a responsibility or asset. A conflict produces a finding with both sources and timestamps (AC-07).

### C.5 Risks (Continuity Debt)

**5.1 Rules engine** — P0 [SPEC §6.7, FR-CI-*]
- Deterministic rules in v1: no primary; no backup (per policy); owner deactivated; owner is the only holder of N critical responsibilities; linked runbook stale or expired; critical responsibility with no linked procedure; asset without a stewarding responsibility; declared-ownership mismatch (A7); case overdue; readiness exception unresolved past its due date; connector stale affecting critical scope.
- Rules are versioned code. Each finding stores `rule_id@version`, evidence and affected scope.

**5.2 Findings triage** — P0
- States: `open → acknowledged → in_remediation → resolved | accepted_risk (until date, by whom) | dismissed (reason)`. Auto-resolves when the rule no longer matches (with history).
- AC: Every finding answers *what, why, evidence, suggested fix, owner*. Dismissed findings do not reopen for the same evidence.

**5.3 Prioritisation** — P1 [SPEC FR-CI-009]
- Displayed as transparent tiers (Urgent / High / Normal), computed from criticality × exposure (e.g. the owner is leaving within 30 days) × age. The factors are shown and there is no false-precision score [SPEC §6.7].

**5.4 Remediation actions** — P0
- From a finding: assign a backup (opens an inline assignment flow), request a review, create a case, accept the risk.

### C.6 Work & Communication

**6.1 My Work inbox** — P0 [SPEC §6.1, §7.5]
- Tabs: *To do* (tasks), *Approvals*, *Questions for me* (interview cards), *Reviews* (knowledge), *Mentions*, *Done*. Each item shows its origin case or responsibility, its due date and the next action.
- AC: Bulk actions only for safe kinds (mark read, snooze, complete Relay-native tasks with no evidence requirement). There is no bulk approve for critical items.

**6.2 Notifications** — P0 in-app + email [SPEC §7.15, FR-NOTIF-*]
- Bodies contain no sensitive content, only secure links. Deduped by `(recipient, event_key)`.

**6.3 Reminders & escalation** — P0 [NEW, M6]
- Playbook-defined schedules, capped reminders, then escalation to the case coordinator, then the scoped manager.

**6.4 Comments & mentions** — P0 [NEW, M5]

**6.5 Digests** — P1 (weekly Risks digest per manager is the main recurring-engagement mechanism).

### C.7 Insights — P1 [SPEC §6.9]

Reports, each with definition, denominator, filters, exclusions and data coverage [SPEC]:
- Coverage (critical responsibilities with a primary and a backup, by team).
- Case outcomes (cycle time, completion with or without exceptions, overdue).
- Knowledge health (verified within window, stale, disputed).
- Integration freshness.
- AI quality (proposal accept / edit / reject rates per capability).

No per-person rankings [SPEC FR-CI-010].

### C.8 Integrations

**8.1 Connector framework** — P0 [SPEC §12.1, FR-INT-*]. See §J.5.

**8.2 GitHub, Linear, Notion** — P0 [SPEC §12.2]. Read scope and the single write action per connector:

| Connector | Read (v1) | Write (v1, approval-gated) | Permission strategy |
|---|---|---|---|
| GitHub (GitHub App) | orgs, teams, repos, CODEOWNERS, `catalog-info.yaml`, README/docs paths, open issues/PRs (metadata + body) | create issue | repo visibility + team/collaborator mapping |
| Linear (OAuth app) | teams, projects (+ leads), issues (open + 90-day closed), cycles, labels | create issue | team membership incl. private teams |
| Notion (public integration) | pages/databases shared with integration, hierarchy, block content for candidate knowledge | none in v1 (proposed changes only) | admin visibility mapping (I1) |

No source code is crawled [SPEC §12.2]. File-path allowlist for docs only.

**8.3 Health & diagnostics** — P0 [SPEC §7.13, §12.4]. "Healthy" is never shown when the last successful sync is older than the freshness objective [SPEC].

**8.4 Approved write actions** — P0. Executed by the Action Executor (§I.3) with idempotency and receipts.

### C.9 Intelligence (admin-facing)

- **9.1 Capability registry** P0: capabilities with version, model policy, tool allowlist, budget and an on/off kill switch [SPEC FR-AGENT-010].
- **9.2 Run viewer** P0: inputs (references), evidence used, tool calls, output, validation, proposals created, approvals, cost [SPEC §10.6].
- **9.3 Policies & budgets** P0 (per-tenant monthly AI budget; per-run caps P0) [SPEC FR-AGENT-011 is P1 — CHANGE to P0, because a runaway cost is a launch blocker].
- **9.4 Evals dashboard** P1: offline eval scores per capability version plus online acceptance rates.

### C.10 Governance

- **10.1 Roles & permissions** P0 (§F).
- **10.2 Audit log** P0, append-only, searchable, exportable by Auditor/Admin [SPEC FR-ADMIN-004/005/006].
- **10.3 Workspace settings** P0.
- **10.4 Retention & deletion** P0 for connector disconnect + source deletion propagation [SPEC FR-ADMIN-010]; configurable retention P1.
- **10.5 Data export** P1. **10.6 Billing** P1. **10.7 Transparency page** P1 (M11).

---

## D. Competitive differentiation

> Claims about competitors below are taken from the competitive study, which cites vendor documentation checked 8 Nov 2026. I have not independently re-verified them. Re-check before using any of this in public positioning [SPEC study §1, PRD §3.2].

### D.1 Competitor map against Relay capabilities

| Competitor | What they do (per study) | Overlap with Relay | What to learn | Relay's distinct position |
|---|---|---|---|---|
| ServiceNow HRSD offboarding KT | Agentic offboarding: discovers employee-authored docs, categorises, creates KT tasks, employee reviews/consents | **High** for Departure | Manager initiation vs employee consent; explicit discovery scope & time range | Not limited to HR-triggered offboarding; responsibility records with history; readiness verification; absence & coverage; mid-market without ServiceNow |
| Guru | Verification, review cycles, freshness, knowledge agents | Medium (Knowledge module) | Verification state, SME routing, correction propagation | Verification tied to *external source revision*; knowledge is a means to transfer, not the product |
| Glean | Permission-aware enterprise search, people/expertise discovery, connectors with ACL maps | Medium (search/discovery) | ACL-aware connectors, freshness as a first-class concern | Relay uses retrieval as an input to workflows; not competing on breadth of search |
| Atlassian Rovo | Agents, reusable skills, tools, confirmation for consequential actions, user-permission inheritance | Medium (agent pattern), threat of bundling | Skill/tool separation; confirmation UX | Cross-vendor (GitHub + Linear + Notion); responsibility model; verified closure |
| OpsLevel | Service catalogue, ownership, scorecards → remediation | Medium (engineering catalogue, coverage) | Scorecard-to-remediation flow | Cross-functional responsibilities; transfer workflow; knowledge capture |
| GitLab Duo Agent Platform | Governed developer agents, observability | Low | Show what agent planned/read/changed | Not a developer agent platform |
| Backstage (OSS) | Software catalogue, ownership metadata, plugins | Medium (engineering catalogue) | Entity model, lifecycle, `owner ≠ authorization` | Relay *ingests* `catalog-info.yaml` rather than competing |
| SourceAnt (OSS core) | Typed engineering knowledge (decisions, constraints, workarounds), governance states, MCP context | **High** for engineering knowledge | Typed knowledge, status model, scoped context packs, staleness on change | Relay's unit is the responsibility and the transfer, not the codebase |
| knowledge-transfer (OSS) | Developer handover ZIP: onboarding doc, privacy-filtered memories, dry-run import, receipts | Medium (capsule) | Omissions report, dry-run, per-item receipts, verify-against-current-source | Live per-viewer capsule within a governed case |

### D.2 Table stakes (we must have these, they won't win deals)

Permission-aware search; knowledge verification and review cycles; ownership catalogue; AI drafting with citations; human approval for agent actions; connector health; audit log; SSO (for mid-market and up).

### D.3 Where meaningful differentiation is possible

| # | Differentiator | Why it's defensible | Proof point in v1 |
|---|---|---|---|
| 1 | **Temporal, cross-functional responsibility model with coverage policy** | Competitors model software entities, documents or HR records, not obligations that span them. | "Who owned R on date D", backup policy findings, the Irreplaceable query |
| 2 | **Verified transfer with effective-dated ownership switch** | Closes the loop that document-centric tools leave open. | Case closes only on criteria; the ownership record updates on the date |
| 3 | **Evidence pool with consent** | A precise answer to the "manager mining employee data" problem; it also makes AI synthesis permission-safe. | Outgoing owner shares items in; synthesis reads only the pool |
| 4 | **Recurring coverage (absence + return briefing)** | High-frequency use case that drives engagement; competitors list it as "unverified / workflow-dependent". | Temporary Coverage playbook |
| 5 | **Cross-tool coordination with receipts** | One case drives Linear and GitHub actions with idempotent, auditable execution. | Approved Linear issue with external ID and receipt |
| 6 | **Catalogue bootstrap from declared ownership signals** | Time-to-value measured in minutes for engineering orgs. | Suggestions from CODEOWNERS / catalog-info / Linear leads |

[REC] Positioning: lead with #2 and #3 in demos. #1 and #6 are the retention story.

---

## E. Build vs. borrow strategy

Decision vocabulary: **BUILD** (we write it, core IP) · **BORROW** (adopt a pattern or design, no code dependency) · **INTEGRATE** (use as a library, managed service or data source) · **DEFER** (re-evaluate when a named trigger fires) · **AVOID** (licence or scope makes it a poor fit).

### E.1 Capability decisions

| Capability | Decision | Rationale | Revisit trigger |
|---|---|---|---|
| Responsibility, ownership, coverage model | BUILD | Core differentiation | — |
| Case engine, playbooks, approvals, readiness | BUILD | Core workflow | — |
| Workflow durability | BUILD (Postgres state machine + job queue) | Cases wait days on humans; that is *data*, not long-running process state. A DB state machine handles it. | Steps begin to need cross-service sagas, sub-second timers at volume, or >1 engineer-month/quarter is spent on engine bugs → evaluate Temporal |
| Job queue / scheduler | INTEGRATE a Postgres-backed queue (Procrastinate, spike S2) or BUILD a minimal `SKIP LOCKED` queue | No new infrastructure; transactional enqueue with domain writes | Sustained >~200 jobs/s or queue contention measured → Redis-backed queue |
| Agent orchestration | BUILD (deterministic engine owns flow) | One source of workflow truth | — |
| LLM step runner | INTEGRATE PydanticAI behind our own `llm` port, *or* thin custom layer over provider SDK (spike S3) | Typed outputs + tool schemas without a second state machine | — |
| Connector framework | BUILD narrow contract; INTEGRATE official SDKs/HTTP | Need precise permission/sync semantics | >6 connectors and demand for long tail → study Onyx connector designs / evaluate embedding a connector platform |
| Search | INTEGRATE Postgres FTS + pg_trgm; pgvector for hybrid (P1) | Same DB, same permission predicates, same transaction | Measured recall/latency fails at target corpus → evaluate a dedicated engine |
| Temporal ownership | BUILD in Postgres (ranges + exclusion constraints) | Simple, testable, transactional | "As-of" reasoning over extracted *unstructured* facts at scale → evaluate Graphiti |
| Knowledge extraction | BUILD small typed pipeline | Narrow, evidence-preserving | Eval shows extraction quality ceiling → evaluate Cognee |
| Document parsing | INTEGRATE standard parsers only when files are supported (P2) | v1 sources are API-structured (Markdown/blocks) | Customers need complex PDFs/tables → evaluate RAGFlow components |
| Wiki/editor | AVOID building a wiki; INTEGRATE an editor component for native items | [SPEC] don't replace Notion | — |
| Authorization engine | BUILD in-app policy module | Rules need domain context (case participation, evidence pool) and SQL list filtering | Customer-defined custom roles/relations at scale → evaluate OpenFGA/SpiceDB |
| AuthN / SSO / SCIM | INTEGRATE managed provider (D7) | Commodity, security-critical | — |
| Email | INTEGRATE (Postmark / Resend / SES) | Commodity | — |
| Observability | INTEGRATE OpenTelemetry + Sentry (or equivalent) | Commodity | — |
| LLM tracing for dev/evals | Optional INTEGRATE (e.g. Langfuse self-hosted) | Product-grade run records live in our DB regardless (they're user-visible) | — |
| Automation builder | DEFER | [SPEC §4.3] | ≥3 customers need playbooks we can't express by parameters |
| Graph visualisation | DEFER (P2, React Flow) | Secondary [SPEC] | — |
| HR lifecycle | INTEGRATE HRIS later (P2) | [SPEC] not an HRMS | Pilot demand names a specific HRIS |

### E.2 Project-by-project decisions

Licence notes come from the competitive study unless marked *(mine)*. **All licences must be re-verified at the pinned version, including subdirectories and transitive dependencies, before any code reuse** [SPEC study §5]. "Study" means reading for patterns. It is not code reuse.

| Project | Problem it solves | Relay overlap | Concept to learn | Build ourselves | Integrate? | Unnecessary | Licence / commercial implication | Decision |
|---|---|---|---|---|---|---|---|---|
| ServiceNow (commercial) | HR-driven offboarding KT | Departure | Consent step, discovery scope/time range | Departure playbook | No | — | Proprietary; no reuse | BORROW (pattern) |
| Guru (commercial) | Trusted knowledge | Knowledge | Verification + review cadence, SME routing | Verification tied to source revision | Possible P2 connector (import Guru cards as linked knowledge) | Full KM authoring | Proprietary | BORROW |
| Glean (commercial) | Enterprise search | Search | ACL-aware connectors, freshness | Targeted search | No | Broad search | Proprietary | BORROW |
| Atlassian Rovo (commercial) | Agents in Atlassian | Agent UX | Skill vs tool, confirmations | Capability registry | Jira/Confluence connectors P2 | — | Proprietary | BORROW |
| OpsLevel (commercial) | Service catalogue | Eng. catalogue | Scorecard → remediation | Risks | P2 connector (import ownership) for customers using it | Scorecards for eng. standards | Proprietary | BORROW + DEFER connector |
| GitLab Duo (commercial) | Dev agents | Low | Run transparency | Run viewer | GitLab connector P2 | — | Proprietary | BORROW |
| Backstage | Dev portal / catalogue | Eng. catalogue | Entity kinds, lifecycle, `owner ≠ authz` | Asset model | **INTEGRATE as data**: parse `catalog-info.yaml` from GitHub (P0, cheap, high value) | Deploying Backstage | Apache-2.0; we only read customer YAML (no code reuse) | BORROW + INTEGRATE (data format) |
| SourceAnt | Engineering knowledge for AI tools | Eng. knowledge, MCP | Typed knowledge, status, scoped context packs, staleness | Knowledge types, statuses | DEFER: possible future connector reading a customer's SourceAnt knowledge | Code review, code graph | MIT core per study; verify `LICENSE.md` and hosted/EE parts | BORROW; DEFER integration |
| codebase-memory-mcp | Code graph via MCP | Eng. impact | Symbol/call impact | — | DEFER optional repo-intelligence adapter | Making code graph core | MIT per study | DEFER |
| knowledge-transfer | Dev handover package | Capsule | Omissions report, dry-run, receipts, verify-vs-source | Capsule, receipts, export (P2) | No (it's a coding-agent skill) | — | MIT per study; reuse possible but low value | BORROW |
| Graphiti | Temporal knowledge graph | Ownership history | Valid-time vs record-time, invalidation not deletion | Bitemporal assignments in Postgres | DEFER | Graph DB | Apache-2.0 per study; requires a graph backend (Neo4j or alternatives) — operational cost | BORROW; DEFER |
| Cognee | AI memory / extraction pipeline | Extraction, retrieval | Ingest → dedupe → enrich → index stages; forget semantics | Typed pipeline | DEFER (eval vs our pipeline) | Using it as domain model | Apache-2.0 per study | BORROW; DEFER |
| Onyx | RAG platform w/ 50+ connectors | Connectors, search | Connector checkpoints, permission sync, reindex flows | Narrow connectors | DEFER | Embedding a second product | MIT CE / separate EE licence for `ee` dirs — **must exclude EE code** | BORROW; DEFER |
| OpenMetadata | Metadata governance | Provenance, lineage | Typed entity schemas, change events, versioning | Provenance model | No | Data-asset focus | Apache-2.0 | BORROW |
| Temporal | Durable execution | Workflow engine | Activities vs orchestration, signals, timers, replay | DB state machine with same concepts | DEFER (trigger above) | — | MIT server per study; SDK licence to verify *(I believe the Python SDK is MIT)*; self-hosting adds Cassandra/Postgres + ops, or Temporal Cloud cost | BORROW; DEFER |
| Kestra | Declarative orchestration | Low | Execution logs, retries UI | — | No | Second engine | Apache-2.0 | BORROW (UX only); AVOID as dependency |
| LangGraph *(mine)* | Agent graph + checkpointing + interrupts | Agent orchestration | Interrupt/resume for HITL | — | No | It would duplicate our workflow engine's state, creating two sources of workflow truth | MIT *(verify)* | AVOID for v1 |
| PydanticAI *(mine)* | Typed LLM agents/tools | LLM steps | — | — | INTEGRATE behind port (spike S3) | — | MIT *(verify)* | INTEGRATE (conditional) |
| Procrastinate *(mine)* | Postgres task queue for Python | Background jobs | — | — | INTEGRATE (spike S2) | — | MIT *(verify)* | INTEGRATE (conditional) |
| Mem0 | Agent memory | Low | Memory scopes, deletion | — | No | Personal memory store | Apache-2.0 per study | AVOID (scope risk: personal memory) |
| AnythingLLM | Doc chat app | Low | Provider config UX | — | No | Doc-chat product | MIT per study | BORROW (UX) |
| RAGFlow | Document parsing/RAG | Parsing | Layout-aware chunking | — | DEFER | — | Apache-2.0 label; verify components | DEFER |
| Docmost | Wiki | Knowledge UX | Page history, comments | — | No | Wiki | **AGPL-3.0** core + EE — no code reuse without legal review | BORROW (UX only) |
| Outline | Wiki | Knowledge UX | Navigation, minimalism | — | No | Wiki | **BSL 1.1**, not OSI open source; document-service restriction | BORROW (UX only) |
| Frappe HR | HRMS | HR lifecycle | Leave/transfer sequencing | — | No | HRMS | **GPL-3.0** | BORROW (concepts only) |
| n8n | Automation | Low | Trigger/action vocabulary, run debugging | — | No | Builder | **Sustainable Use License** (not OSI) — no embedding/resale | BORROW (UX only) |
| UI libs *(mine)*: shadcn/ui, Radix, TanStack Query/Table, React Flow, Tiptap | UI building blocks | — | — | — | INTEGRATE | — | MIT *(verify)*; **Tiptap Pro extensions are commercial** — core only | INTEGRATE |

---

## F. User roles and permissions

### F.1 Model [CHANGE C4]

Authorisation is the conjunction of five layers [SPEC §8.2, restructured]:

```
allowed(actor, action, resource) =
      tenant_member(actor, resource.tenant)                     -- L1 tenant boundary (+ RLS)
  AND (workspace_role grants action                              -- L2
       OR scoped_grant(actor, role, scope ∋ resource) grants action      -- L3 dept/team/collection
       OR relationship(actor, resource) grants action)           -- L4 case participant, owner, steward
  AND source_visible(actor, resource.evidence)  (for source-derived content)   -- L5
  AND action_policy(action, resource) satisfied                  -- approvals, SoD, sensitivity, budget
```

**Tier 1 — Workspace roles** (exactly one per member): `Owner`, `Admin`, `Member`, `Guest` (contractor/external: sees only what they're explicitly attached to), `Auditor` (read-only governance; can be scoped).

**Tier 2 — Scoped grants** (any number, each bound to a scope = workspace | department | team | knowledge collection):
`Continuity Manager`, `Team Manager`, `Knowledge Steward`, `Integration Manager` [NEW: lets admins delegate connector setup for a scope without full admin].

**Tier 3 — Relationship roles** (derived from data, never assigned in a roles screen):
- On responsibilities: `Primary`, `Co-owner`, `Backup`, `Temporary`.
- On cases: `Coordinator` (accountable manager), `Outgoing`, `Receiving`, `Approver` (per approval request), `Contributor/SME`, `Observer`.
- On knowledge: `Steward/Owner`, `Author`.

### F.2 Permission matrix

Legend: ✅ allowed · S = within their scope · R = when the relationship exists · P = allowed subject to action policy/approval · — = not allowed. *Guest* = only on resources they're attached to.

**Workspace & governance**

| Action | Owner | Admin | Cont. Mgr | Team Mgr | Steward | Integ. Mgr | Member | Guest | Auditor |
|---|---|---|---|---|---|---|---|---|---|
| Transfer workspace ownership, billing | ✅ | — | — | — | — | — | — | — | — |
| Manage settings, policies, retention | ✅ | ✅ | — | — | — | — | — | — | — |
| Invite / suspend members | ✅ | ✅ | — | S (invite to team) | — | — | — | — | — |
| Assign workspace roles | ✅ | ✅ (not Owner) | — | — | — | — | — | — | — |
| Assign scoped grants | ✅ | ✅ | S (below own) | S (Steward in team) | — | — | — | — | — |
| Connect/configure connectors | ✅ | ✅ | — | — | — | S | — | — | — |
| Resolve identity matches | ✅ | ✅ | — | — | — | S | — | — | — |
| Configure capabilities, budgets, kill switch | ✅ | ✅ | — | — | — | — | — | — | — |
| View agent run traces | ✅ | ✅ | S | S | S (knowledge runs) | — | R (runs in their cases, redacted) | — | S (read) |
| Read audit log | ✅ | ✅ | S | S (team/case) | S (knowledge) | S (connector) | own actions | — | S ✅ |
| Export data | P | P | P (scope) | — | — | — | — | — | P |

**Catalog**

| Action | Owner/Admin | Cont. Mgr | Team Mgr | Steward | Member | Guest | Auditor |
|---|---|---|---|---|---|---|---|
| View responsibilities | ✅ | S | S | S | ✅ non-restricted* | R | S |
| Create/edit responsibility | ✅ | S | S | — | propose | — | — |
| Set criticality ≤ high | ✅ | S | S | — | — | — | — |
| Set criticality = critical | ✅ | S | P (approval by Cont. Mgr/Admin) | — | — | — | — |
| Change ownership assignment (outside a case) | P | S·P | S·P | — | — | — | — |
| Assign backup | ✅ | S | S | — | R (primary may *propose*) | — | — |
| Accept suggestions (bulk) | ✅ | S | S | — | — | — | — |

\* [ASSUME] By default, responsibility records (not their evidence) are visible to all members. That is what makes "find who owns X" work. Admins can mark a responsibility `restricted`.

**Cases**

| Action | Admin | Cont. Mgr | Team Mgr | Coordinator | Outgoing | Receiving | Approver | Contributor | Member | Auditor |
|---|---|---|---|---|---|---|---|---|---|---|
| Create case | ✅ | S | S | — | P (self-initiated transfer, policy) | — | — | — | request | — |
| View case | ✅ | S | S | R | R | R | R (subject only) | R (assigned items) | — | S |
| Edit scope, dates, participants | ✅ | S | S | R | propose | propose | — | — | — | — |
| Share own items into evidence pool | — | — | — | — | R ✅ | R ✅ (own) | — | R (own) | — | — |
| Answer interview questions | — | — | — | — | R | R | — | R | — | — |
| Edit outgoing context (their statements) | — | review | review | review | R ✅ | comment | — | own | — | — |
| Accept/reject AI proposals | ✅ | S | S | R | R (own context) | — | — | — | — | — |
| Approve actions/transfers | P | S·P | S·P | R·P | consent | accept receipt | R ✅ | — | — | — |
| Assign tasks | ✅ | S | S | R | — | — | — | — | — | — |
| Pass readiness criterion | — | — | — | R (if verifier) | R (if verifier) | self-attest only | — | R (if verifier) | — | — |
| Close case | P | S·P | S·P | R·P (SoD for critical) | — | — | — | — | — | — |
| Reopen / cancel | ✅ | S | S | R | — | — | — | — | — | — |

**Knowledge**

| Action | Admin | Steward | Owner/Author | Team Mgr | Member | Guest |
|---|---|---|---|---|---|---|
| View knowledge item | ✅ (within L5) | S | R | S | scope + L5 | R + L5 |
| Create native item | ✅ | S | — | S | ✅ (draft) | — |
| Link source item as knowledge | ✅ | S | — | S | propose | — |
| Edit | ✅ | S | R | — | suggest | — |
| Verify | — (unless Steward) | S | R (own items, if policy) | if Steward | — | — |
| Dispute | ✅ | ✅ | ✅ | ✅ | ✅ | R |
| Publish to broader audience | P | S·P | P | S·P | — | — |

### F.3 Source-level access (L5)

The rule: **Relay never shows source-derived content to a user unless the source would show it to them, or a person who could see it explicitly shared it into a case (consent), or an admin visibility mapping grants it.** Per-connector mechanisms are in §M.3. Evidence carries `visibility_basis` ∈ {`source_acl`, `visibility_mapping`, `shared_by_consent`, `relay_native`}.

### F.4 Action policies

Defined per tenant, defaults per criticality tier:
- **Approval rules:** `(action_type, condition) → required approver set, count, SoD constraints, expiry`. Examples: external task creation → case coordinator; critical closure → Continuity Manager ≠ initiator; publishing knowledge to the workspace → Steward of the scope.
- **Standing approvals** (P1, autonomy L2 "pre-approved policy" [SPEC study §10.5]): e.g. "Coordinator pre-approves Linear issue creation into team X for this case". The approval is still bound to the action type and target, logged per execution, and revocable.
- **Restricted actions (L3)** — access grants or revocation, employment state, deleting source content: **not implemented** [SPEC §10.4].

### F.5 Implementation

[REC] A **permission registry** in code: every action is an enum entry with its resource type and policy function. Two primitives:
- `authorize(actor, action, resource) -> Decision(allowed, reason)`, used at the application-service layer on every command.
- `visible(actor, resource_type) -> SQL predicate`, used for all lists and search, so filtering happens in the database and pagination stays correct.

Postgres RLS enforces *only* the tenant boundary (defence in depth). Fine-grained rules live in the app because they need domain context. The registry is also what generates the permission test matrix (§N).

---

## G. User journeys

Each journey lists: trigger, actors, steps (✱ = AI capability involved; ☐ = human gate), completion, and key edge cases (with references to PRD §17).

### G.1 Employee offboarding → **Departure playbook** (light in v1, HRIS-triggered P2)

- **Trigger:** A manager opens a Departure case for Priya (last day 30 Nov). P2: HRIS termination event.
- **Actors:** Coordinator (manager), Outgoing (Priya), Receivers (per item), Approvers, SMEs.
1. Wizard: person, last day, purpose. Data-use notice shown and stored.
2. Relay lists all active assignments held by Priya (deterministic) → each becomes a scope item. Also detects responsibilities where she is the *only backup* (these become items too).
3. ✱ Discovery (scoped to her responsibilities' assets, not "everything she authored"): open work, linked knowledge, stale runbooks, items only she can see.
4. ☐ **Consent step**: Priya sees items visible only to her and chooses: share into case / private / not relevant [SPEC §9.9, ServiceNow pattern]. She can dispute AI-drafted statements.
5. ☐ Coordinator picks a receiver per item (or "TBD" → blocks that item, raises a finding).
6. ✱ Gap questions are sent to Priya as interview cards. Brain-dump intake is offered.
7. ✱ The plan is proposed: playbook tasks plus AI extras. ☐ Coordinator accepts or edits.
8. ☐ Approve external task creation → the executor creates Linear issues with receipts.
9. Receivers work through their per-item capsule, readiness criteria and access requests.
10. ☐ Closure: all items transferred/retained/excepted → ownership switches on the effective date.
- **Completion:** case closed. Priya's deactivation (separate, in the HR/IdP system) no longer triggers critical findings because her assignments have already ended.
- **Edge cases:** leaves early or unexpectedly → Emergency flag (G.7) [§17.1]. Receiver declines → item reverts to `to: TBD` [§17.1]. Priya disputes content → `disputed` state, routed to the coordinator [§17.2]. Access removal stays outside Relay [§17.1 contractor].

### G.2 Temporary absence → **Temporary Coverage playbook**

- **Trigger:** Arjun is away 10–24 Dec. The manager (or Arjun himself, by policy) opens a case.
1. Relay lists Arjun's assignments. Items default to "cover" with suggested covers = existing backups (deterministic). Missing backup → highlighted.
2. ✱ Discovery of *time-bounded* work: due dates inside the window, scheduled releases, open approvals.
3. ☐ Manager approves covers and authority boundaries ("can approve deploys: yes/no").
4. Temporary assignments are written with `valid_period = [10 Dec, 24 Dec]`. They expire automatically by construction, with no job. A reminder before expiry asks "extend?" [§17.1 extended].
5. Covers get a capsule per item. Tasks are issued.
6. During the absence: an **asset-scoped** change digest is collected (A6).
7. ✱ Return Briefing on the return date: what changed, decisions, incidents, completed and open work, each cited and time-bounded.
8. Arjun acknowledges and takes back items. Any permanent change becomes a separate Transfer.
- **Edge cases:** early return → end temporary assignments now, generate the briefing immediately [§17.1]. Cover becomes unavailable → finding plus a reassignment prompt. Overlap with another absence case for the same cover → warning.

### G.3 Internal transfer → **Departure-shaped case, person stays** (P2 as a distinct playbook; v1 = Departure with "internal move" reason)

- Same as G.1 but: the outgoing person stays reachable, so the consent and interview steps carry less risk. A **transition period** is allowed in which the person stays a `backup` for N weeks (a temporary backup assignment on each item). Their new team gets an Onboarding-lite path.
- **Edge cases:** manager changes mid-case (both old and new managers) → coordinator handover per policy, prior actions preserved [§17.1].

### G.4 New employee onboarding → **Onboarding playbook**

- **Trigger:** Manager creates the case (P2: HRIS hire event).
1. Choose role/team and the responsibilities the hire will eventually hold (optional: start as `backup`).
2. ✱ Onboarding Path composed: team overview, responsibility capsules, contacts, required knowledge, starter tasks. ☐ Manager reviews.
3. Access prerequisites → access-request tasks to source admins (M7). Relay never grants access.
4. Milestones (week 1/2/4) as tasks. Mentor assigned as verifier.
5. Readiness: attestations, artefacts (first PR), supervised demo.
6. Completion: hire becomes `backup` → later `primary` via a Transfer.
- **Edge cases:** start date slips → reminders recompute [§17.4]. Hire can't see linked docs → "requires access" items, not silent omission.

### G.5 Project handover → **Responsibility Transfer** with project asset

- The responsibility is "Lead project X", stewarding a Linear project and its Notion space.
1. ✱ Discovery: milestones, open issues, risks, decisions (decision-type knowledge), stakeholders (Linear members, contacts).
2. ✱ Impact: issues without assignee after transfer; decisions without rationale; stakeholders not yet informed.
3. Outgoing owner confirms or corrects project state (statements become `human_stated`).
4. ☐ Approved actions: update the Linear project lead (P1 write action), create a handover issue.
5. Receiver readiness: stakeholder intro attestation, Q&A reviewed.
- **Edge cases:** source of truth changes mid-case (project re-scoped) → findings refresh, outdated proposals invalidated [§17.4].

### G.6 Service ownership transfer → **Responsibility Transfer** with service/repo assets (engineering-specific variant)

- Specifics: CODEOWNERS/catalog-info mismatch after transfer → rule finding until updated. ✱ Plan suggests a PR task updating CODEOWNERS (created as a GitHub *issue* in v1, not a PR). Readiness includes a supervised deploy or on-call shadow sign-off.
- **Edge cases:** repo renamed → stable source identity keeps links [§17.3]. Team rather than person becomes owner → named accountable contact required for critical [§17.1].

### G.7 Emergency continuity → **Emergency flag** on Transfer/Departure (v1), dedicated playbook P2

- **Trigger:** owner unexpectedly unavailable.
1. Coordinator flags emergency. Interview steps are **disabled** for the unavailable person [SPEC §9.10]. Questions route to SMEs and backups.
2. Existing backups are promoted to `temporary` immediately (☐ one-click approval).
3. ✱ Discovery uses only already-authorised sources and the existing catalogue. There are no consent-gated items from the absent person; they remain unavailable. Unknowns stay explicit [SPEC].
4. Compressed reminders. A daily status digest to the coordinator.
- **Edge cases:** person returns → convert to Coverage closure plus Return Briefing. Elevated access: out of scope; link to the source system's break-glass process [SPEC §9.10].

### G.8 Knowledge maintenance → **not a case; continuous loop**

1. A source change (webhook/sync) on a page linked as a verified runbook → deterministic `stale` transition.
2. ✱ Knowledge Review compares the new revision against the verified one and drafts a "what changed and whether the procedure still holds" note.
3. Steward receives a review task in My Work: verify, edit-and-verify, dispute, archive.
4. Review cadence expiry triggers the same path. A weekly digest goes to stewards.
5. Unresolved stale critical runbook past its SLA → Risk finding.
- **Edge cases:** newer source isn't authoritative → source authority config wins [§17.2]. Duplicate pages → canonical suggestion, never auto-delete [§17.2].

---

## H. Information architecture and UX

### H.1 Navigation [CHANGE C8]

```
┌ Workspace switcher ▾          ⌘K Search      + Create ▾       🔔 Inbox   Avatar ▾ ┐
│ ── Work ──────────────                                                           │
│  Home                          (role-aware overview)                             │
│  My Work               (12)    (inbox)                                           │
│  Cases                                                                           │
│ ── Organisation ──────                                                           │
│  Responsibilities              tabs: Responsibilities · Assets · Suggestions     │
│  Knowledge                     tabs: All · Review queue · Interviews             │
│  Risks                  (5)    (Continuity Debt backlog)                         │
│  Insights                      (managers+, hidden for Members)                   │
│  People & Teams                                                                  │
│ ── (bottom) ──────────                                                           │
│  ⚙ Settings   → Workspace · Members · Roles & Permissions · Integrations ·      │
│                 Agents & Automations · Policies · Audit Log · Data & Retention · │
│                 Billing                                                          │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Rationale:
- Seven primary items, grouped by job. Admin surfaces live in Settings (their own sub-navigation, like Linear), not in the main sidebar [SPEC §7.2 "permission-aware"].
- **"Risks"** is used as the UI label instead of "Continuity Debt", because it's clearer to first-time users. "Continuity Debt" stays the name of the backlog metric. Open decision D12.
- A Member's sidebar: Home, My Work, Cases (only those they're in), Responsibilities, Knowledge, People & Teams. No Insights, no Settings except the profile.

### H.2 Global shell

- **⌘K command palette**: search and actions ("New transfer for…", "Assign backup to…", "Go to case…").
- **Create menu:** New case, New responsibility, Add knowledge, Invite, Connect integration (permission-filtered).
- **Notifications** dropdown, with My Work as the full view.
- **Workspace indicator** always visible. A coloured workspace avatar prevents acting in the wrong org [SPEC §7.3].
- **Freshness indicator** for admins: a compact dot in the header, red only when a connector is stale against its objective.

### H.3 Screen specifications

Every screen answers four questions: *What am I looking at? Why does it matter? What needs attention? What can I do next?* The table gives each screen's answers and its key components.

| Screen | What / why | Attention | Next actions | Key components |
|---|---|---|---|---|
| **Home** | Your continuity situation in your scope | Top inbox items; cases at risk (overdue/blocked); new Risks; upcoming absences/departures (30 days) | Open item, create case, assign backup | ActionList, CaseRiskCard, RiskSummary (counts by tier with links), UpcomingTimeline, setup checklist (until done) |
| **My Work** | Everything waiting on you | Overdue first, then due soon | Complete, approve/reject, answer, review, reassign (if permitted), open source | Tabbed inbox, ItemRow (origin, due, why-me), approval sheet drawer, question card drawer, snooze |
| **Cases list** | Active and past continuity work | Overdue, blocked, awaiting me | Filter, saved views, create | Linear-style dense table: type, subject, coordinator, stage, progress (items done/total), due, flags; saved views ("My cases", "Overdue in my dept") |
| **Case detail** | One managed change | Header **Next action** banner ("Choose receiver for 2 items"); blockers | The next action; per-item actions | See H.4 |
| **Responsibilities list** | Who is accountable for what | Missing owner/backup, stale knowledge, pending suggestions | Filter, bulk assign backup, import, create | Table: name, criticality, primary, backup, team, health chips; filter bar; Suggestions tab with bulk review |
| **Responsibility detail** | One obligation and its history | Health strip (owner ✓ backup ✗ runbook stale) | Assign backup, request review, start transfer | Header with health strip; tabs Overview · Owners & History (timeline) · Assets · Knowledge · Cases · Risks · Activity · (P2) Relationships |
| **Asset detail** | A thing the org depends on | Unstewarded, source unavailable | Link responsibility, open source | Source card (sync state), stewarding responsibility, dependencies, knowledge |
| **Knowledge list** | Trusted operational knowledge | Stale/disputed critical items | Search, filter, verify, add | Table with type, steward, linked responsibilities, verification chip, last verified, source |
| **Knowledge detail** | One item and how far to trust it | "Changed since verified" diff banner | Verify, edit, dispute, open source | Trust panel (basis, verification, revision, steward), content/excerpt, version history, linked cases |
| **Review queue** | What stewards must re-check | Sorted by criticality × age | Verify / edit / dispute / archive | Split view: list + evidence/diff |
| **Risks** | Continuity weaknesses before they bite | Urgent tier | Assign, remediate inline, create case, accept risk, dismiss | Finding row: what / why / evidence / suggested fix / owner; tier chips; rule explanation drawer |
| **Insights** | Trends and outcomes | Declining coverage, rising cycle time | Drill to filtered lists, export (permitted) | Report cards with definition, denominator, coverage note; date range; scope picker |
| **People & Teams** | Org structure and coverage | Identity conflicts (admins), teams with coverage gaps | Invite, edit team, resolve identity, view person | Directory, team pages (members, responsibilities, coverage), person page (responsibilities, cases visible to viewer, Irreplaceable panel for managers) |
| **Integrations** (Settings) | Data feeding Relay and how fresh it is | Attention-required connectors | Connect, configure scope, test, resync, pause, renew, disconnect | Connector cards with the 11 health states [SPEC §12.4]; detail: identity/installation, scopes, include/exclude, last success, errors, permission strategy note |
| **Agents & Automations** (Settings) | What AI does and what it costs | Failed runs, budget near limit, low acceptance | Toggle capability, set budget, inspect run | Capability catalogue (version, model tier, tools, approval rules, acceptance %), run list, run trace view, budget meter |
| **Roles & Permissions** (Settings) | Who can do what | Users with broad grants | Assign roles/grants, view effective permissions | Role reference (read-only definitions), member grants table, **"Explain access"** tool (user × resource → allowed? why?) [NEW] |
| **Audit Log** (Settings) | Accountability record | Security events | Filter, export (audited) | Immutable event table, actor/target/action filters, correlation drill-through |
| **Settings: Workspace/Policies/Data** | Configuration | — | Edit criticality definitions, coverage policies, playbook parameters, retention | Forms with change history |

### H.4 Case detail workspace (primary operational screen)

```
┌ ← Cases   Transfer: Payment Service Operations → Arjun     ● Planning   Due 30 Nov   ⋯ ┐
│ ▶ NEXT: Approve 3 proposed Linear tasks            [Review]   ⚠ 1 item blocked (no receiver) │
├──────────────────────────────────────────────────────────────┬─────────────────────────────┤
│ Overview | Scope & Impact | Plan | Knowledge | Approvals | Activity │ People               │
│                                                              │  Coordinator  Meera          │
│ Scope items                                                  │  Outgoing     Priya          │
│ ┌ Payment Service Ops   Priya → Arjun   ● in_transfer  4/7 ┐  │  Receiving    Arjun          │
│ ├ Refund approvals      Priya → TBD     ⚠ blocked         ┤  │  Approvers    Meera, Ravi    │
│ └ Release calendar      Priya → Arjun   ✓ ready           ┘  │ Dates  Eff. 1 Dec (IST)      │
│                                                              │ Sources ● GitHub ● Linear    │
│                                                              │         ◐ Notion stale 2d    │
│                                                              │ AI  Last analysis 2h ago ↻   │
└──────────────────────────────────────────────────────────────┴─────────────────────────────┘
```

- **Tabs** [CHANGE from PRD §7.8]: *People* moves to the right rail. *Impact* becomes **Scope & Impact** (items plus findings per item). *Tasks* is renamed **Plan** (tasks plus readiness criteria per item).
- **Proposal tray:** AI output appears as a tray of proposals with accept / edit / reject per row and "accept all non-critical" with a confirmation [SPEC FR-AGENT-016].
- **Statement component:** text + **basis chip** (`Source` / `Rule` / `Person` / `AI`) + **verification badge** + evidence popover (source, revision, timestamp, excerpt if permitted) + "restricted evidence" placeholder when applicable.
- **Partial-analysis banner:** "Notion was stale during analysis; results may be incomplete" (AC-02).

### H.5 States catalogue (shared components) [SPEC §7.17]

| State | Component | Rule |
|---|---|---|
| Empty (first-use) | `EmptyState` with a one-line why + primary action (e.g. "No responsibilities yet — Import from GitHub · Import CSV · Create") | Never a blank table |
| Empty (filtered) | "No results for these filters" + clear | — |
| Loading | Skeletons matching layout; no spinners over 300 ms for lists | — |
| Partial | `PartialDataBanner` naming the missing sources | Required whenever analysis ran with a stale/failed connector |
| Stale | `StaleBadge` with last-sync time | Required on any source-derived item older than the freshness objective |
| Error | `ErrorPanel`: what happened, retry, correlation ID, support link | No raw stack traces |
| No permission | `PermissionNotice`: "You don't have access. Ask a Team Manager of Payments." — reveals no restricted content | [SPEC §17.7] |
| Source unavailable | `UnavailableSource`: archived/deleted/revoked + next action | — |
| Conflict | `ConflictCard` showing both versions + timestamps + resolve action | AC-07 |
| AI degraded | "AI assistance unavailable — you can continue manually" | NFR-REL-005 |
| Success | Toast with next step ("Task created in Linear — Open") | — |

### H.6 Accessibility, responsiveness, onboarding

- Target WCAG 2.2 AA [SPEC §15.7]. Radix primitives give keyboard and focus behaviour. Status always has icon + text, never colour alone. Axe checks in CI.
- Desktop-first for coordinators and admins. Mobile supports My Work, approvals, question cards, reading capsules and the case summary. Settings shows a "best on desktop" notice [SPEC §7.16].
- Onboarding: the setup checklist (M4), sample data in a **separate demo workspace** (never mixed into the real one), and contextual first-run hints on Case detail and Responsibilities.

---

## I. Agent architecture

### I.1 Principle

> **The orchestrator is deterministic code. AI is a step, not a planner. LLMs propose; humans approve; deterministic code executes.**

[REC] An LLM never decides which workflow step runs next, never holds a tool that writes to an external system, and never changes the status of a case, approval or verification. This one rule makes prompt injection a *quality* problem (a bad proposal that a human sees) instead of a *security* problem (an unwanted side effect).

### I.2 Capability classification [CHANGE C5, I4]

| PRD/study "agent" | Becomes | Type | Why |
|---|---|---|---|
| Continuity Monitor | **Rules engine** (findings module) | Deterministic | Coverage, staleness and deactivation are exact rules [SPEC §10.3-A already says "most checks deterministic"] |
| Discovery / Context Retriever | **Discovery service** + `classify_relevance` skill | Deterministic + small LLM skill | Graph walk over catalogue + source-record queries + FTS. LLM only labels ambiguous items as relevant or not, with a reason |
| Impact Analyst | Deterministic impact queries + **`synthesize_impact`** skill | Hybrid | Open work, dependents and unassigned-after-transfer are SQL. LLM groups, explains and proposes gap hypotheses (labelled `ai_inferred`) |
| Knowledge Steward | **Knowledge Review** skills: `draft_knowledge`, `compare_revision`, `check_conflict` | LLM skills | Drafting and comparison are real language tasks |
| Knowledge Interviewer | **Interview** agent | **Bounded LLM agent** (multi-turn, read-only tools) | Needs adaptive follow-ups |
| Handover Planner | Playbook expansion + **`propose_plan_additions`** skill | Hybrid | Base plan is deterministic. LLM proposes case-specific extra tasks and criteria |
| Coordination Agent | **Action Executor** | Deterministic | Executing approved actions must be exact, idempotent and receipted. An optional `draft_message` skill writes notification text |
| Readiness Verifier | **Readiness evaluator** + `summarize_evidence_for_reviewer` skill | Deterministic + LLM summary | LLM never outputs pass/fail |
| Return Briefing Generator | **Briefing composer** + `summarize_section` skill | Hybrid | Change digest is SQL; summary is cited LLM text |
| Context Capsule | **Briefing composer** (same) | Hybrid | Same service, different template |
| Continuity Simulation | **Irreplaceable query** | Deterministic | It's a query (I9) |
| Onboarding Guide (study) | **Briefing composer** (Onboarding Path) + Scoped Ask | Hybrid | — |
| Incident Knowledge Assistant (study) | P2: `link_incident` + Knowledge Review skills | LLM skills | Later phase |
| [NEW] Ownership Suggestions | Deterministic extractor + `propose_responsibility_grouping` skill | Hybrid | Bootstrap (M1) |
| [NEW] Scoped Ask | **Ask** agent | **Bounded LLM agent** (read-only tools) | Q&A over the evidence pool or the viewer's scope |

Result: **2 bounded agents** (Interview, Ask) and **about 9 single-shot skills**. Everything else is deterministic.

### I.3 Runtime components

```
 UI / API command ──► Application service ──► Workflow Engine (DB state machine)
                                                 │  step = deterministic | skill | agent | gate | action
                                                 ▼
                                Job queue (Postgres) ──► Worker
                                                 │
            ┌────────────────────────────────────┼────────────────────────────────────┐
            ▼                                    ▼                                    ▼
   Deterministic services             Capability Runner                         Action Executor
   (discovery, rules, impact,        ├─ Capability Registry (versioned)          (approved actions only)
    readiness, briefing)             ├─ Context Builder → Evidence Pool          ├─ re-authorize
                                     ├─ LLM Gateway (provider port, routing,     ├─ verify approval hash
                                     │   caching, budgets, redaction, retries)   ├─ idempotency key
                                     ├─ Tool Gateway (READ-ONLY tools,           ├─ connector adapter
                                     │   actor-scoped, ID allowlists)            └─ receipt + audit
                                     └─ Output Validator (schema, citations,
                                         link allowlist) → Proposal Store
```

| Component | Responsibility |
|---|---|
| **Workflow Engine** | Persists `workflow_instance` and `workflow_step`. Advances on events (task done, approval decided, timer, run completed). Pure transition functions per playbook stage. Timers are rows (`due_at`) polled by the scheduler. |
| **Capability Registry** | `capability_id@version`: purpose, input schema, output schema, prompt template ref (in repo, hashed), model policy (tier, max tokens), tool allowlist, budget, eval suite, enabled flag (global + per tenant). |
| **Context Builder** | Assembles a bounded input from the **evidence pool** only (§M.4): statements, source excerpts with provenance headers, size-capped and prioritised. |
| **LLM Gateway** | Provider port (Claude by default, see D10). Model routing by tier. Prompt caching. Retries on 429/5xx with jitter. Token and cost accounting per run/tenant. Budget enforcement *before* each call. PII/secret redaction of logs. Structured-output enforcement. |
| **Tool Gateway** | Read-only tools for agents: `get_case_context`, `get_responsibility`, `get_ownership_history(as_of)`, `search_evidence(query)` (pool-restricted), `get_statement`, `list_gaps`, `get_open_work(asset)`. Each tool: Pydantic args (`extra="forbid"`), executes as the **run actor**, IDs must belong to the run's allowed set, output wrapped as untrusted data with provenance, size limits. |
| **Output Validator** | Schema validation. Every claim must cite ≥1 evidence ID from the provided set (unknown IDs → reject). URLs may only come from evidence records. One automatic repair attempt, then `failed_validation`. |
| **Proposal Store** | All AI output becomes `proposal` rows (`pending → accepted | edited | rejected | superseded | expired`). Acceptance writes domain records with `basis = ai_inferred` (or `human_stated` if edited materially, keeping lineage). |
| **Action Executor** | Executes `action_request` rows only when an approval with a matching hash exists (or a valid standing approval applies). Re-authorises the actor. Uses idempotency keys. Writes receipts. |

### I.4 Contracts

**Statement** (the unit of trust shown in the UI):
```
statement { id, tenant_id, subject_ref, text, basis: source_observed|rule_derived|human_stated|ai_inferred,
            evidence_ids[], evidence_strength: strong|moderate|weak|none (computed),
            verification: unverified|verified|disputed|stale, verified_by?, verified_at?,
            produced_by: {actor|run_id, capability@version}, created_at }
```

**Finding** (revises PRD §10.7): `claim, category, evidence[], basis, evidence_strength, freshness {oldest_evidence_at, stale_sources[]}, impact_scope[], recommendation, requires_review (+reason), limitations[]` [SPEC fields kept; `confidence` → `evidence_strength`, CHANGE A4].

**Proposal envelope:** `{ proposal_id, run_id, kind (task|criterion|statement|knowledge_draft|grouping|message), payload (typed per kind), content_hash, evidence_ids[], rationale (short, user-visible), limitations[] }`.

### I.5 Execution flow: "Analyse case"

1. Command `case.analyse` → authorise (coordinator) → create `workflow_step(analyse, input_hash)`. If a completed step with the same `input_hash` exists, return it (idempotent).
2. Job: **Discovery service** (deterministic) fills candidates → evidence pool admission rules (§M.4) → items needing consent go to the outgoing owner's inbox.
3. `classify_relevance` skill on ambiguous candidates (small model, batched).
4. Deterministic impact queries → structured facts (`rule_derived`).
5. `synthesize_impact` skill → findings and gap hypotheses (`ai_inferred`) → validator → proposals.
6. `propose_plan_additions` skill → proposed tasks and criteria → proposals.
7. Step completes. SSE event updates the case page. Next-action banner: "Review 9 proposals".

Each sub-step is its own `workflow_step` row, so a crash resumes from the last completed sub-step (AC-10).

### I.6 State persisted

`workflow_instance`, `workflow_step` (name, state, attempt, input_hash, output_ref, error, started/ended), `agent_run` (capability@version, actor, purpose, scope, status per PRD §10.6 lifecycle), `agent_run_event` (tool call args/results redacted, validation outcomes), `llm_call` (model, tokens in/out/cached, cost, latency, prompt_hash — not raw prompts by default), `proposal`, `approval`, `action_request`, `action_execution` (idempotency_key, external_id, status, receipt).

[REC] Store **no hidden chain-of-thought**. Store concise rationale, evidence and structured output only [SPEC study §10.6]. Raw prompt/response capture is an admin-enabled, short-retention debug setting per tenant.

### I.7 Approval gates

- Gate types: **content approval** (publish knowledge, share capsule beyond case), **action approval** (external write, notification beyond participants), **transition approval** (closure for critical, ownership change outside a case), **consent** (outgoing owner shares items).
- The binding: approval stores `content_hash`. The executor recomputes it at run time. On mismatch → `approval.invalidated` → re-request [SPEC FR-TASK-007/008].
- Approval UI always shows the five facts from PRD §10.8: *what, where, who sees it, source data involved, reversible?*

### I.8 Failure recovery & idempotency

| Failure | Handling |
|---|---|
| Provider 429/5xx/timeouts | Retry with exponential backoff + jitter (max 3). Then run → `failed` with reason. Workflow stays usable manually (NFR-REL-005) |
| Schema/citation validation failure | 1 repair attempt with the validator error, then `requires_human_review` with partial output discarded |
| Budget exceeded | Stop before the call. Run → `budget_exceeded`. Admin notified. No silent continuation [SPEC §17.5] |
| Worker crash mid-step | Step lease expires → requeued. Idempotent by `input_hash`. Completed sub-steps are not repeated |
| External write timeout (unknown outcome) | Before retrying: look up by correlation key (Linear: issue with Relay marker/attachment URL; GitHub: issue search by marker). Found → record receipt; not found → retry with the same idempotency key [SPEC §17.3] |
| Duplicate trigger (webhook, double click) | `Idempotency-Key` on commands; unique constraints on `(tenant, source_event_id)`; step `input_hash` |
| Permission revoked mid-run | Tool Gateway re-checks per call; Action Executor re-checks before execution → `permission_denied`, security event if cross-tenant [SPEC §17.5] |
| Kill switch | Checked at step start and before every LLM/tool call; in-flight runs → `cancelled` |
| Case cancelled | Cascade: cancel queued steps/runs, expire pending proposals and action requests, keep history [SPEC §17.4] |
| Source changed during case | `source.record.changed` for pool evidence → affected proposals `superseded`, findings flagged "evidence changed", re-analysis offered [SPEC §17.4] |

### I.9 Prompt-injection and data-exfiltration defences [SPEC §10.9, FR-AGENT-013]

1. **No write tools for LLMs** (I.1). This is the primary control.
2. Untrusted content is passed in delimited data blocks with a provenance header. The system prompt states that data blocks are never instructions.
3. Tool arguments are validated server-side. IDs must be in the run's allowlist (case scope / evidence pool). Unknown fields are rejected.
4. **Link/exfiltration control:** output may contain URLs only if they match evidence records. Rendered Markdown is sanitised, with no remote images and no auto-loading embeds. This blocks exfiltration via image URLs.
5. Instruction-like content heuristics flag source chunks ("ignore previous instructions", tool-call syntax) → excluded from synthesis or down-weighted, and shown to admins.
6. An eval suite with injection fixtures in GitHub issues, Notion pages and PR bodies runs on every prompt/model change (§N).

### I.10 Cost and token management

- Model tiers per capability (D10): **small/fast** (Claude Haiku 5.5 class) for relevance classification and grouping; **standard** (Claude Sonnet 5.5 class) for synthesis, drafting, interview and Ask; **top tier** (Claude Opus 5.5 class) only where evals show it is needed, and for eval judging. [ASSUME: final routing comes from eval results, not this table.]
- Bounded context: evidence bundles capped per capability. Dedupe by content hash. Prompt caching for stable system prompts and case context.
- Embeddings only for knowledge-eligible content (linked knowledge, docs paths, issue/PR bodies in scope), not for everything synced. Re-embed only on content-hash change.
- Budgets: per-tenant monthly hard cap + soft alert at 80%; per-run cap; per-capability daily cap. Cost shown on run viewer and Agents page.

### I.11 Evaluation

- **Offline:** a synthetic organisation fixture expanded from PRD Appendix B (3 teams, 10 people, 3 repos, 2 Linear projects, ~60 Notion pages including stale, conflicting, restricted and injection pages). Per-capability golden sets with metrics: citation precision (every claim supported?), unsupported-claim rate, missing-data detection, relevance precision/recall, plan task usefulness (human-rated rubric), injection resistance (pass/fail), tool-argument validity, cost/latency.
- **Judging:** deterministic checks first (citations resolve, schema, ID allowlist). LLM-as-judge only for rubric dimensions, and calibrated against a human-labelled subset.
- **CI gate:** any change to a prompt, model, retrieval or tool schema runs the suite. Regression beyond threshold blocks merge [SPEC §18.3].
- **Online:** accept / edit / reject rates per capability version, from the proposal tray; reasons for rejection captured (one-tap reasons + optional text).

### I.12 Framework decision (D6)

[REC] **No LangGraph.** Its core value (graph state, checkpointing, human interrupts) duplicates our workflow engine and would create a second source of workflow truth, which [SPEC §16.4] warns against. Use **PydanticAI** (typed outputs, tool definitions, provider-agnostic) *inside* the Capability Runner behind our own `LLMPort`, **or** a ~500-line custom layer over the provider SDK. Spike S3 decides: implement `synthesize_impact` and the Interview agent both ways and compare code clarity, structured-output reliability, streaming, testability and provider portability.

---

## J. Technical architecture

### J.1 System architecture

```
                 Browser (Next.js app, TanStack Query, generated TS client)
                        │ HTTPS (REST /api/v1, SSE /api/v1/streams)
        ┌───────────────┴───────────────┐
        │  Next.js server (auth session, │   Vercel or container
        │  SSR shell only; no domain     │
        │  logic, no DB access)          │
        └───────────────┬───────────────┘
                        │ bearer token (JWT from IdP, verified in API)
┌───────────────────────▼────────────────────────────────────────────────────────┐
│  relay (one Python codebase, one container image)                               │
│   process: api     — FastAPI, uvicorn, N replicas, stateless                    │
│   process: worker  — job queue consumers (lanes: interactive-ai, sync, default) │
│   process: scheduler — periodic jobs, timers, outbox relay (1 replica / leader) │
└───────┬──────────────────────────┬─────────────────────────┬───────────────────┘
        │                          │                         │
 PostgreSQL 16+ (managed, PITR)   Object storage (exports,   External: GitHub, Linear, Notion,
  domain + queue + FTS + pgvector  attachments; P1)           LLM provider, embeddings, email, IdP
  RLS, outbox, audit
```

### J.2 Repository layout

```
relay/
  apps/web/                 Next.js (App Router), feature folders mirror backend modules
  apps/api/                 Python package `relay`
    relay/platform/ identity/ org/ policy/ catalog/ sources/ integrations/
          knowledge/ cases/ findings/ intelligence/ work/ insights/ audit/ search/
    relay/shared/           db session, outbox, ids, time, errors, pagination
    migrations/             Alembic
    tests/
  packages/api-client/      generated from OpenAPI (CI checks it's up to date)
  evals/                    fixtures, golden sets, runner
  infra/                    IaC, Dockerfiles, CI
```

[REC] A monorepo with one Python package. Module boundaries are enforced by **import-linter** contracts in CI: modules may import another module's `public` API (services + DTOs) only, never its `models` or `repositories`.

### J.3 Backend architecture (per module)

```
module/
  api.py          FastAPI routers — HTTP only: parse, call service, map errors
  schemas.py      Pydantic request/response DTOs (never ORM models)
  service.py      Application services: transaction boundary, authorize(), orchestrate domain, emit events
  domain.py       Pure entities/value objects/state machines/rules — no I/O, fully unit-tested
  models.py       SQLAlchemy 2.x mapped classes (module-private)
  repository.py   Queries (incl. visible() predicates); raw SQL allowed for reports
  public.py       What other modules may import
  events.py       Domain event definitions (versioned Pydantic)
```

- **Unit of work:** one `AsyncSession` per request or job [SPEC §11.3]. `expire_on_commit=False`. No lazy loading in async paths (`lazy="raise"` by default, with explicit `selectinload`).
- **Tenant context:** resolved from the verified token → membership lookup → `SET LOCAL app.tenant_id` at transaction start (for RLS) + an explicit `tenant_id` argument to repositories (belt and braces).
- **Cross-module workflows:** synchronous calls to `public` services within one transaction where atomicity matters (e.g. case closure writes ownership assignments via `catalog.public`). Asynchronous reactions go via outbox events.
- **Errors:** RFC 9457 problem details with stable `code`s.

### J.4 Database architecture

- One PostgreSQL database. **One Postgres schema per module** (`catalog.responsibility`, `cases.case`…) to make boundaries visible. Cross-schema FKs allowed. Alembic manages all of them.
- Extensions: `vector` (pgvector), `pg_trgm`, `btree_gist` (exclusion constraints on ranges with equality), `citext`. Use pgcrypto only if needed.
- Primary keys: UUIDv7 (time-ordered, index-friendly). All timestamps `timestamptz` in UTC. Business dates `date` + case/tenant time zone.
- **Every tenant-owned table:** `tenant_id NOT NULL`, RLS policy `tenant_id = current_setting('app.tenant_id')::uuid`, and **composite FKs `(tenant_id, x_id)`** so a row can't reference another tenant's row even by a bug. The app connects as a non-owner role without `BYPASSRLS`. Migrations use a separate owner role.
- Enumerations: `text` + `CHECK` (easier migrations than PG enums).
- Typed metadata: `jsonb` validated by the per-asset-type Pydantic schema at the service layer. Version recorded in the row.
- Large/append-heavy tables (`audit_event`, `source_record_version`, `llm_call`, `agent_run_event`, `activity_event`) are time-partitioned when volume warrants; design keys for it now.
- Connection pooling: transaction-mode pooler for API/worker; **a dedicated direct connection for `LISTEN/NOTIFY`** (transaction poolers break LISTEN).

### J.5 Integration architecture

```
Connector (per source) implements:
  capabilities()            → {read_kinds, write_actions, webhooks, acl_strategy}
  authorize()/refresh()     → credential lifecycle
  validate_connection()
  list_scopes()             → selectable repos/teams/teamspaces
  full_sync(scope, checkpoint) -> AsyncIterator[SourceRecordDraft]   (paged, checkpointed)
  incremental_sync(checkpoint)
  parse_webhook(headers, body) -> list[SourceEvent]   (signature verified first)
  fetch_acl(record) / visibility(record)
  execute(action, payload, idempotency_key) -> ActionResult
  find_by_correlation(key) -> ExternalRef | None
```

- **Sync engine** (generic): schedules full/incremental syncs per connector with per-tenant concurrency limits (job-queue lock keys). Writes `source_record` (stable `(connector_id, external_id)`) and `source_record_version` (content hash). Emits `source.record.changed` only when the hash changes. Tracks `sync_run` with counts and errors.
- **Webhook inbox:** `POST /webhooks/{connector}/{installation}` → verify signature → insert into `webhook_inbox` (unique on delivery ID) → 200 fast → worker processes. Duplicates are a no-op. Out-of-order deliveries are reconciled by source `updated_at`/version plus a nightly reconciliation sync [SPEC FR-INT-014].
- **Credentials:** OAuth tokens/installation keys encrypted with envelope encryption (cloud KMS key → data key). Stored in `integrations.credential`. Never logged. Expiry → connector state `credentials_expired` + admin notification.
- **Rate limits:** per-connector token bucket in the DB (or in-process per worker with conservative limits). Honour `Retry-After`. Expose `rate_limited` state.
- **Disconnect:** stop schedules → state `deletion_pending` → retention job removes source content and embeddings per policy, keeps audit metadata [SPEC FR-INT-012].

### J.6 Background processing

| Lane | Jobs | Notes |
|---|---|---|
| `interactive-ai` | case analysis, interview turns, Ask, briefing summaries | Low latency; small concurrency per tenant |
| `sync` | full/incremental sync, webhook processing, ACL refresh, embeddings | Per-tenant and per-connector concurrency caps [SPEC NFR-PERF-006] |
| `default` | outbox relay, notifications/email, rules evaluation, reminders, retention, reports | — |

Periodic: rules evaluation (every 15 min and on relevant events), freshness checks (hourly), reminders/escalations (every 5–15 min), nightly reconciliation sync, retention (daily), digest emails (weekly).

**Outbox:** domain writes and `outbox_event` insert in the same transaction → relay process dispatches to handlers/jobs → handlers are idempotent on `event_id`.

[REC] Spike S2: Procrastinate (Postgres queue, async, periodic tasks, locks) vs a minimal in-house `SKIP LOCKED` queue. Pick one. **No Redis/Celery** unless measured throughput or latency requires it.

### J.7 AI infrastructure

- LLM provider via `LLMPort` (D10). Embeddings via `EmbeddingPort` (separate decision: provider APIs vs a self-hosted open model). Anthropic does not offer a first-party embeddings API, so this needs its own choice.
- pgvector: one `chunk` table with `tenant_id`, `source_record_version_id`, `section_ref`, `embedding vector(n)`, HNSW index. Queries always filter on tenant + visibility predicate. Use pgvector's iterative index scans for filtered queries [ASSUME — validate with pgvector version available on the chosen managed Postgres].
- Hybrid ranking: FTS (`tsvector`) + vector + reciprocal-rank fusion. Reranking only if evals show benefit.
- Run telemetry stored in Postgres (user-visible run viewer). OpenTelemetry spans for engineering observability.

### J.8 Real-time

SSE endpoints for run progress, case updates and notifications. API instances `LISTEN` on a channel. Workers `NOTIFY` with `(tenant_id, topic, id)` and no payload content. The client refetches via TanStack Query. Redis pub/sub is only needed if Postgres NOTIFY fan-out becomes a measured bottleneck.

### J.9 Frontend architecture

- Next.js App Router. The authenticated app is mostly client components with TanStack Query. The Next server handles the auth session and SSR shell only. **No business logic in Server Actions or route handlers.** Python is the only backend [your requirement].
- Typed client generated from FastAPI's OpenAPI (e.g. hey-api/openapi-ts or orval) and committed. CI fails if it's stale.
- shadcn/ui + Radix + Tailwind tokens. TanStack Table for all lists (virtualised). URL-synced filters/saved views (e.g. `nuqs`). react-hook-form for forms. Editor: Tiptap core (MIT core; avoid Pro extensions) for native knowledge. React Flow for the P2 graph tab.
- Feature folders mirror backend modules. Shared design-system package for Statement, EvidencePopover, ApprovalSheet, ProposalTray, StateBanners and EmptyState.

### J.10 Deployment architecture

| Concern | Recommendation | Status |
|---|---|---|
| Environments | local (docker compose: postgres+pgvector, api, worker, web, mailpit), CI ephemeral, staging (synthetic data only), production | [SPEC §11.8] |
| Hosting | Start: Vercel (web) + container PaaS or AWS ECS Fargate (api/worker/scheduler) + managed Postgres with pgvector & PITR (RDS/Aurora, Crunchy, Neon…) in the **same region** | Open D8 |
| Region / residency | One region at launch (e.g. EU or US based on pilots); design `tenant.region` now so a second region is possible later | Open D8 [ASSUME] |
| Secrets | Cloud secrets manager + KMS | — |
| CI/CD | GitHub Actions: lint, type-check (mypy/pyright, tsc), tests, import-linter, evals (on prompt changes), image build, migrate (pre-deploy job), deploy | — |
| Migrations | Expand/contract pattern; backward-compatible for one release; run as a separate job before rollout | [SPEC §18.4] |
| Backups/DR | PITR + daily snapshot, quarterly restore drill. Provisional targets RPO ≤ 15 min, RTO ≤ 4 h [ASSUME] | [SPEC NFR-REL-002] |
| Observability | OpenTelemetry → vendor (Grafana/Datadog/Honeycomb); Sentry for errors; correlation ID across request → job → run → connector call | [SPEC §15.8] |
| Single vs multi-tenant | Pooled multi-tenant with RLS; dedicated-DB tier possible later because tenant_id is everywhere | Open D11 |

---

## K. Domain and database model

### K.1 Entities by module

| Module | Entities (key fields / notes) |
|---|---|
| platform | `tenant` (name, region, timezone, plan, settings jsonb), `tenant_policy` (criticality defs, coverage rules, SoD, retention) |
| identity | `user` (global identity from IdP), `membership` (tenant, user, workspace_role, type employee/contractor/guest, status, valid_period), `external_identity` (connector, external_id, login, email, display), `identity_link` (user ↔ external_identity, state suggested/confirmed/rejected, method, decided_by) |
| policy | `scoped_grant` (membership, role, scope_type, scope_id, valid_period, granted_by), `approval_rule`, `standing_approval` |
| org | `department`, `team` (parent dept), `team_membership` (valid_period, is_lead) |
| catalog | `responsibility` (type, criticality, team_id, status active/suggested/archived, review_cadence, escalation jsonb, restricted flag), `ownership_assignment` (bitemporal, §K.4), `asset` (type, name, lifecycle, metadata jsonb, schema_version, source_record_id?), `responsibility_asset` (relation stewards/uses), `dependency` (from_ref, to_ref, relation, provenance, valid_period), `suggestion` (kind, payload, evidence_ids, state) |
| sources | `connector` (tenant, kind, installation, state, freshness_objective), `credential`, `sync_run`, `sync_checkpoint`, `webhook_inbox`, `source_record` (connector, external_id, kind, url, title, state active/archived/deleted/revoked, current_version_id), `source_record_version` (content_hash, fetched_at, source_updated_at, content ref/text per retention), `source_visibility` (record → principal set: teams/users/mapping, refreshed_at), `chunk` (version, section_ref, tsv, embedding), `evidence` (source_record_version_id or relay ref, locator, excerpt?, captured_at, visibility_basis) |
| knowledge | `knowledge_item` (type, mode linked/native, steward, scope, status draft/active/archived, source_record_id?), `knowledge_version` (immutable; content or source revision ref; author/run), `verification` (item, version/revision hash, verifier, at, valid_until, superseded_at), `statement` (§I.4), `interview` (case/item, interviewee, state), `interview_question` (gap ref, why, state, answer, answer_type, visibility) |
| cases | `playbook` (code-defined; DB row per version for FK), `case` (type, playbook_version, title, coordinator, stage, flags, priority, tz, purpose, data_use_notice, effective dates), `case_participant` (role, valid_period, reason-included), `case_scope_item` (responsibility, from_assignment, to_assignee, role, effective_date, state), `case_stage_history`, `task` (case/item, assignee, due, status, kind native/external, external_ref, deps), `task_dependency`, `readiness_criterion` (item, type, verifier, status, evidence_ids), `approval_request` (subject, content_hash, approver set, policy ref, deadline, state), `approval_decision`, `consent_record`, `evidence_pool_entry` (case, evidence, admitted_by, basis), `exception` (case/item/criterion, reason, approved_by) |
| findings | `finding` (rule_id@version or run, category, subject_ref, tier, state, evidence_ids, recommendation, dedupe_key), `finding_event` |
| intelligence | `capability` (+version), `workflow_instance`, `workflow_step`, `agent_run`, `agent_run_event`, `llm_call`, `proposal`, `action_request`, `action_execution`, `tenant_ai_budget`, `eval_result` |
| work | `inbox_item` (materialised per recipient: kind, ref, due, state), `notification` (+ delivery), `comment`, `mention`, `reminder_schedule` |
| audit | `audit_event` (append-only), `activity_event` (product timeline) |

### K.2 Audit vs activity [CHANGE M16]

| | `audit_event` | `activity_event` |
|---|---|---|
| Purpose | Security and accountability evidence | Human-readable timeline in the UI |
| Content | actor, action, target, tenant, ip/ua, correlation_id, before/after hashes, decision reason | Rendered event type + refs |
| Integrity | DB role has INSERT only; no UPDATE/DELETE grants; optional hash chain (P2) | Normal |
| Retention | Long (policy, e.g. 1–7 years) | Tied to case retention |
| Visibility | Admin / Auditor / scoped | Case participants |

### K.3 Lifecycle state machines

**Case** [CHANGE C6, I5]:
```
draft → scoping → planning → executing → verifying → closed{completed | completed_with_exceptions | cancelled}
           ↑__________ reopen (from closed: new segment, reason required) __________|
Flags (orthogonal): blocked(reason), emergency, overdue (derived), at_risk (derived)
"Waiting on" (derived from open tasks/approvals/questions): input | review | approval | receiver
```
Mapping from the PRD's states: Investigating→scoping, Awaiting Input/Review→derived "waiting on", Ready for Transfer→planning complete, In Progress→executing, Verification→verifying, Blocked→flag, Reopened→transition.

**Scope item:** `proposed → confirmed → in_transfer → ready → transferred | retained | excepted`. Any state → `blocked` flag.

**Task:** `todo → in_progress → done | cancelled`. `blocked` flag. External: `sync_state ∈ {pending_creation, synced, drifted, source_deleted}`.

**Approval request:** `pending → approved | rejected | expired | invalidated (content changed) | withdrawn`.

**Proposal:** `pending → accepted | edited | rejected | superseded | expired`.

**Knowledge item:** `draft → active → archived`. Verification is orthogonal: `unverified → verified → stale (source changed / window expired) → verified…`, plus `disputed`.

**Finding:** `open → acknowledged → in_remediation → resolved | accepted_risk(until) | dismissed(reason)`. Auto-resolve when the rule stops matching.

**Connector:** the PRD §12.4 states, modelled as `{lifecycle: connected|paused|disconnected|deletion_pending} × {health: healthy|syncing|stale|partial_failure|credentials_expired|permission_changed|rate_limited|source_unavailable}`.

**Agent run:** PRD §10.6 states kept, plus `failed_validation` and `budget_exceeded`.

**Identity link:** `suggested → confirmed | rejected`. Confirmed → `revoked`.

### K.4 Temporal data

[REC] **Bitemporal ownership** (Graphiti lesson, implemented in Postgres):
```
ownership_assignment(
  id, tenant_id, responsibility_id, assignee_type (user|team), assignee_id,
  role (primary|co_owner|backup|temporary),
  valid_period tstzrange NOT NULL,          -- when it is/was true in the organisation
  recorded_at timestamptz NOT NULL,         -- when Relay learned it
  superseded_at timestamptz NULL,           -- set when a correction replaces this row
  superseded_by uuid NULL,
  source (manual|case|import|suggestion), source_ref, case_id NULL, change_reason, created_by
)
EXCLUDE USING gist (tenant_id WITH =, responsibility_id WITH =, valid_period WITH &&)
  WHERE (role = 'primary' AND superseded_at IS NULL);
```
- "Owner as of D": `valid_period @> D AND superseded_at IS NULL`.
- "What did Relay believe on D2 about D": `valid_period @> D AND recorded_at <= D2 AND (superseded_at IS NULL OR superseded_at > D2)`.
- Corrections never update a row in place. They insert a new row and supersede the old one.
- [CHANGE / D1] **Exactly one primary at a time is a hard invariant.** Shared ownership uses `co_owner`. This turns FR-RESP-006's "configured policy" into one clear rule. Tenants who want "no primary" for some responsibilities leave it empty, and that raises a finding if the tier requires one.

Other temporal tables with `valid_period`: `membership`, `team_membership`, `scoped_grant`, `case_participant`, `dependency`, `source_visibility` (refreshed_at), `verification` (valid_until).

### K.5 Important constraints

- Uniques: `(tenant_id, connector_id, external_id)` on `source_record`; `(source_record_id, content_hash)` on versions; `(connector_id, delivery_id)` on `webhook_inbox`; `(tenant_id, idempotency_key)` on `action_execution` and on command idempotency; `(tenant_id, dedupe_key) WHERE state IN open-states` on `finding`; `(workflow_instance_id, step_name, input_hash)` on `workflow_step`.
- Composite tenant FKs everywhere (§J.4).
- `CHECK` that `approval_decision.content_hash = approval_request.content_hash`.
- `case_scope_item` unique `(case_id, responsibility_id)`. A partial unique index prevents two *active* Transfer/Departure cases touching the same responsibility (warning and override via linking, not a silent block; enforced in service, surfaced in UI).
- Optimistic concurrency: `version int` on case, responsibility, knowledge_item, task, approval_request. Updates require `WHERE version = :v` (If-Match).
- Soft delete only where retention requires (`archived_at`). Hard delete via retention jobs for source content and embeddings [SPEC FR-KNOW-011].

---

## L. API and event architecture

### L.1 Conventions [SPEC §16.1 + REC]

- REST JSON under `/api/v1`. Resources are plural nouns. **State transitions are explicit command endpoints** (`POST /cases/{id}/actions/close`), never `PATCH stage`, so each command gets its own authorisation, validation and audit.
- Cursor pagination (`?cursor=&limit=`). Filters as query params. Sorting whitelisted.
- `Idempotency-Key` header required on commands with side effects. Server stores `(key, request_hash, response)` for 24 h.
- `If-Match: <version>` on mutable sensitive resources → 412 on conflict.
- Errors: RFC 9457 `application/problem+json` with `code`, `detail`, `correlation_id`.
- Tenant comes from the token/membership, never from the path or body [SPEC]. Multi-workspace users send `X-Relay-Workspace` and the server verifies membership.
- OpenAPI is the contract. The TS client is generated from it.

**Assumptions behind the groups below:** single REST API serving the web app (no separate public API in v1); SSE for streams; no GraphQL (one client, and REST maps well to command semantics); endpoint names are illustrative until each milestone's design review.

### L.2 Main API groups and important operations

| Group | Resources | Key commands / queries |
|---|---|---|
| Session & workspace | `/me`, `/workspaces`, `/settings`, `/policies` | `GET /me` (memberships, effective grants), setup checklist state |
| Members & org | `/members`, `/invitations`, `/departments`, `/teams`, `/teams/{id}/memberships` | invite, suspend, deactivate, `GET /teams/{id}?as_of=` |
| Identity | `/identity-links` | `actions/confirm`, `actions/reject` |
| Grants | `/grants` | grant, revoke; `GET /access/explain?user=&resource=` |
| Catalog | `/responsibilities`, `/responsibilities/{id}/assignments`, `/assets`, `/dependencies`, `/suggestions`, `/imports` | `GET /responsibilities/{id}/assignments?as_of=`; `actions/assign-backup`; `suggestions/actions/bulk-decide`; `imports` (dry-run → commit); `GET /people/{id}/irreplaceable` |
| Cases | `/cases`, `/cases/{id}/scope-items`, `/tasks`, `/readiness-criteria`, `/approvals`, `/exceptions`, `/participants` | `actions/analyse`, `actions/advance`, `actions/close`, `actions/reopen`, `actions/cancel`; `scope-items/{id}/actions/set-receiver`; `GET /cases/{id}/next-actions`; `GET /cases/{id}/briefing?for=me` |
| Consent & pool | `/cases/{id}/pool`, `/cases/{id}/consent-requests` | `actions/share`, `actions/withhold` |
| Proposals & approvals | `/proposals`, `/approval-requests` | `proposals/{id}/actions/accept|reject|edit`; `approval-requests/{id}/actions/approve|reject` (body includes `content_hash`) |
| Knowledge | `/knowledge`, `/knowledge/{id}/versions`, `/knowledge/{id}/verifications`, `/interviews`, `/questions` | `actions/verify`, `actions/dispute`; `questions/{id}/actions/answer`; `GET /knowledge/{id}/diff?from=&to=` |
| Findings | `/findings` | `actions/acknowledge|accept-risk|dismiss|create-case` |
| Search & Ask | `/search`, `/ask` (P1) | `GET /search?q=&types=`; `POST /ask` → run id + SSE |
| Work | `/inbox`, `/notifications`, `/comments` | mark read, snooze, bulk-complete (safe kinds) |
| Integrations | `/connectors`, `/connectors/{id}/scopes`, `/connectors/{id}/sync-runs`, `/connectors/{id}/visibility-mappings` | connect (OAuth start/callback), `actions/test|resync|pause|resume|disconnect` |
| Webhooks (inbound) | `/webhooks/{kind}/{installation}` | signature-verified, inbox insert |
| Intelligence | `/capabilities`, `/agent-runs`, `/agent-runs/{id}/events`, `/budgets` | `capabilities/{id}/actions/enable|disable`; `agent-runs/{id}/actions/cancel|retry` |
| Insights | `/reports/{report_id}` | parameterised; each returns `definition`, `denominator`, `coverage` |
| Governance | `/audit-events`, `/exports`, `/retention` | export jobs (audited) |
| Streams | `/streams/case/{id}`, `/streams/me` | SSE |

### L.3 Domain events (internal, via outbox)

Envelope [SPEC §16.3]: `event_id, type, version, tenant_id, occurred_at, actor {type,id}, subject {type,id}, correlation_id, payload`.

| Event | Main consumers |
|---|---|
| `membership.deactivated` | findings (deactivated-owner rule), inbox (reassign approvals) |
| `ownership.assignment.created/ended/superseded` | findings, search index, activity, notifications |
| `responsibility.created/updated/criticality_changed` | findings, search |
| `source.record.changed / deleted / visibility_changed` | knowledge (stale), cases (pool evidence changed), embeddings, findings |
| `connector.health_changed`, `connector.sync.completed/failed` | findings (stale critical scope), admin notifications |
| `knowledge.verified / became_stale / disputed` | findings, inbox |
| `case.created / stage_changed / closed / reopened / cancelled` | workflow engine, inbox, notifications, activity |
| `case.scope_item.state_changed` | workflow engine |
| `task.assigned / completed / external_synced` | inbox, workflow engine |
| `approval.requested / decided / invalidated` | inbox, action executor, workflow engine |
| `consent.decided` | evidence pool, workflow engine |
| `proposal.created / decided` | inbox, eval metrics |
| `agent.run.started / completed / failed` | SSE, run viewer, budgets |
| `action.executed / failed` | activity, audit, task sync |
| `finding.created / resolved` | inbox, digests |

[REC] No Kafka or other external broker. Outbound customer webhooks are P2, built on the same outbox.

### L.4 Integration patterns

- **Inbound:** webhook → inbox → normalise → upsert source record (hash-compare) → event → reactions. Periodic incremental sync as a safety net. Nightly reconciliation.
- **Outbound writes:** proposal → approval (hash) → `action_request` → executor (`find_by_correlation` → execute with idempotency key → receipt) → event. Correlation marker: a Relay URL attachment/link in the created issue so it can be found again.
- **Identity:** connector users → `external_identity` → link suggestions → admin confirmation.

---

## M. Security and reliability

### M.1 Authentication (D7)

- Managed IdP for authentication only (candidates: WorkOS AuthKit, Clerk, Auth0; self-hosted Keycloak/Zitadel if self-hosting matters). It issues OIDC tokens that FastAPI verifies (JWKS, audience, expiry). **Relay's DB is authoritative for memberships, roles and grants.** IdP organisations are not authoritative.
- Session revocation on deactivation: short-lived access tokens (≤ 10 min) + a membership status check on each request (cached per request, not across requests) [SPEC FR-IAM-009].
- SSO (SAML/OIDC) P1, SCIM P2 via the provider.

### M.2 Authorisation & isolation

- §F.5 primitives on every command and list. A route-level dependency enforces "authenticated + tenant resolved". Service-level `authorize()` is mandatory: a lint/test checks every command service method calls it.
- Tenant isolation layers: (1) tenant from token, (2) explicit `tenant_id` on repositories, (3) RLS, (4) composite FKs, (5) per-tenant job keys, (6) vector queries filtered by tenant, (7) caches keyed by tenant (only in-process caches exist in v1), (8) automated cross-tenant tests (§N) [SPEC AC-09].
- OWASP API Top 10 baseline: object-level auth (BOLA) is covered by `authorize` on every ID, mass assignment by Pydantic `extra="forbid"`, resource consumption by pagination caps, rate limits and AI budgets [SPEC §15.4].

### M.3 Source permission strategy per connector [CHANGE I1] — validate in spike S1

| Connector | What the API likely offers [ASSUME] | Relay strategy | Revocation detection |
|---|---|---|---|
| GitHub (App) | Repo visibility; org teams & their repo permissions; collaborators | `source_visibility` = principals with read on the repo (teams + direct collaborators) mapped via identity links. Private-repo content only to mapped principals | `member`, `team`, `repository` webhooks + periodic ACL refresh |
| Linear (OAuth) | Teams incl. private teams; team memberships | Visibility = members of the issue's team (public teams → all members of the workspace mapping) | Team membership refresh (scheduled) + webhooks where available |
| Notion | Integration sees only pages shared with it; per-user page ACLs likely **not** exposed | **Admin visibility mappings** (teamspace/page subtree → Relay teams/“everyone”). Default for unmapped pages = *only the connecting admin + explicit case sharing*. Optional P1: per-user Notion OAuth to verify access at read time | Mapping changes are immediate; page unshare from integration → `revoked` on next sync |

The UI must show each connector's strategy honestly ("Notion visibility is managed by Relay mappings, not Notion permissions").

### M.4 Evidence pool and per-viewer filtering [NEW — central design]

Problem: AI synthesis can leak restricted content even when citations are hidden. The PRD requires that "a manager must not receive private content solely because an employee is leaving" (§17.6), and that the incoming owner must not inherit source permissions.

Rule set:
1. Each case has an **evidence pool**. Only pool evidence can be passed to LLM capabilities for that case.
2. Evidence is **admitted** if (a) it is visible to every *core participant* (coordinator, outgoing, receivers) under L5, or (b) a person who can see it **shares it into the case** (consent record), or (c) it is Relay-native and authored within the case.
3. Evidence that fails (a) and has no consent is shown *only to those who can see it*, as "candidates to share", in their inbox.
4. Statements derived from pool evidence are visible to case participants. A receiver who can't open the underlying source still sees the *statement* (because it was shared or is visible to all) and gets an access-request action for the source itself (M7).
5. Background capabilities (system actor) outside cases, such as Knowledge Review on a stale page, only read content visible to the item's steward, and their output is visible only to principals who can see the source.
6. Every pool admission is audited (`admitted_by`, basis).

### M.5 Auditability

Audited: auth events, role/grant changes, connector config, credential events, consent decisions, approvals, external writes, exports, deletions, kill-switch use, permission denials of interest (cross-tenant attempts are security events). Correlation IDs link request → job → run → connector call.

### M.6 Data retention (defaults to confirm, D13)

| Data | Default retention | Deletion trigger |
|---|---|---|
| Source content snapshots & chunks/embeddings | While connected and in scope | Source delete/revoke → removed within 24 h; disconnect → per policy (default 30 days) |
| Evidence excerpts in closed cases | Case retention (e.g. 2 years) or until source deletion if policy says "follow source" | — |
| Relay-native knowledge | Until deleted by owner/steward | — |
| Agent run metadata | 1 year | — |
| Raw prompts/responses (debug mode only) | ≤ 14 days | auto |
| Audit events | 1–7 years (policy) | Legal hold overrides |
| Tenant | Deletion request → 30 days soft → hard delete including backups' expiry window | Verified job + certificate |

### M.7 Privacy & employee trust

- Default exclusions: private messages, HR/comp/health data, personal Notion pages not shared with the integration, source code [SPEC §8.4, §12.2].
- No person-level activity metrics anywhere [SPEC FR-CI-010]. Irreplaceable views are framed as *responsibility concentration*.
- Transparency page (M11). The data-use notice is stored per case.
- Model provider: zero-data-retention / no-training terms required before pilots (D10).

### M.8 Platform security

TLS everywhere; encryption at rest (managed); envelope-encrypted credentials; secrets never in client bundles; webhook signature verification; SSRF protection (no arbitrary URL fetching in v1: connectors only call allowlisted API hosts); upload type/size limits (P1); dependency and container scanning; rate limiting per user/tenant on auth, search, Ask and commands.

### M.9 Reliability & failure recovery

- Stateless API, horizontally scalable. Workers scale separately. The scheduler is a single leader (advisory lock).
- Workflow and approvals live in the DB, independent of any process [SPEC NFR-REL-006/007]. Jobs are leased with visibility timeouts and idempotent handlers.
- Degraded modes: LLM down → manual workflow continues with a banner; connector down → stale banners and partial-analysis flags; email down → in-app still works, retry queue.
- Backups and restore drills (§J.10).

---

## N. Testing strategy

| Layer | Scope | Tools | Gate |
|---|---|---|---|
| Unit (domain) | State machines, rules, policy functions, temporal queries' logic, content hashing, playbook expansion | pytest, **Hypothesis** (property tests for state machines: no illegal transitions, closure invariants) | Every PR |
| Integration (DB) | Repositories, RLS, exclusion constraints, migrations up/down, outbox, job queue semantics | pytest + **testcontainers** Postgres w/ pgvector | Every PR |
| API contract | OpenAPI conformance, fuzzing | **Schemathesis** against the app | Every PR (smoke), nightly (full) |
| **Tenant isolation** | For every endpoint & job: tenant B cannot read/write/list/search tenant A's IDs; vector search; SSE; exports | Auto-generated test matrix from route table + seeded 2-tenant fixture | **Release blocker** [SPEC §18.4] |
| **Permission matrix** | Each registry action × role/grant/relationship → expected allow/deny | Generated from permission registry + fixture personas | **Release blocker** |
| Connector contract | Normalisation, pagination, rate-limit handling, webhook signature, out-of-order/duplicate events, rename, deletion, token expiry | Recorded fixtures (respx/VCR-style); fault injection | Every PR |
| Connector live | Real GitHub org / Linear workspace / Notion workspace (test accounts) | Nightly scheduled job | Nightly; alerts |
| Workflow | End-to-end case flows with a **fake clock**: reminders, expiries, escalations, temporary assignment expiry, reopen, cancel cascade | pytest with time control | Every PR |
| Recovery/chaos | Kill worker mid-step; LLM provider 500s; external write timeout after success; duplicate webhooks (AC-05, AC-10) | Fault-injection harness | Nightly |
| Agent evals | §I.11 metrics, injection suite, permission filtering of context | `evals/` runner, golden sets | On prompt/model/tool/retrieval change; weekly full |
| E2E | Demo script (PRD Appendix A) + negative paths (stale connector, missing backup, permission denial, rejected draft, AI unavailable) | **Playwright** | Pre-merge on main; release |
| Accessibility | Keyboard paths, focus, labels, contrast on core flows | axe-core in Playwright + manual audit before pilots | Release |
| Load | Case lists, search, sync of a 5k-issue Linear workspace, queue throughput | k6/Locust | Before pilots and major releases |
| Security | SAST, dependency audit, secret scanning, container scan; pre-pilot external pentest | CI tools; third party | Release / pre-pilot |
| Usability | 5–8 target users per milestone on unscripted tasks | Moderated sessions | Milestone exit |

The PRD acceptance scenarios AC-01…AC-10 are each implemented as named automated tests (E2E or workflow level).

---

## O. Implementation roadmap

> **Team update:** Relay is built by one person working with AI assistants (ChatGPT, Claude). **§O.0 is the plan of record.** The team-based table further down is kept only as the long-term shape of the product.

### O.0 Solo-builder plan (plan of record)

**Principle:** cut *breadth*, never *correctness*. Some things are cheap to build now and very expensive to retrofit later, so they stay in from day one:
- tenant isolation (`tenant_id`, RLS, composite foreign keys);
- the permission registry with `authorize()` and `visible()`;
- bitemporal ownership;
- idempotency keys;
- the audit log;
- the rule that LLMs only produce proposals and never hold write tools.

**Simplifications against §J:**

| Area | Team plan | Solo plan |
|---|---|---|
| Processes | api, worker, scheduler | **api + worker.** The worker also runs periodic jobs, with a Postgres advisory lock so only one instance runs them. |
| Hosting | Vercel + PaaS/AWS + IaC | Vercel (or the same PaaS for both) + one PaaS (Render, Railway or Fly) + managed Postgres with pgvector and point-in-time recovery. No IaC until a second environment is painful to manage by hand. |
| Auth | Choose after spike S6 | **Managed only** (Clerk or WorkOS). Never self-hosted. |
| Search | FTS, then hybrid | FTS + trigram only. pgvector waits until after the first pilot. |
| Notion permissions | Visibility mappings + per-user OAuth | Unmapped pages are visible only to the admin who connected Notion, plus anything shared into a case. Mappings come later. |
| Testing | Full matrix (§N) | Unit + DB integration tests, generated tenant-isolation and permission tests, and one Playwright run of the demo path (with one failure case). Eval set of about 30 cases, including prompt-injection cases. Load, chaos, pentest and live nightly connector tests wait until just before pilots. |
| Spikes | S1–S7 | S1 (connector permission APIs), S2 (job queue), S4 (async SQLAlchemy + RLS), each kept to about a day. Pick PydanticAI or a thin custom layer by building the first capability with it. |

**Deferred until after the first pilot signs up:** Insights, hybrid search, scoped Ask, digests, transparency page, SSO, approver delegation, data export, billing, the Onboarding playbook, conflict detection and the graph view.

**Solo milestones.** Each one is something you can show to a real user.

| # | Delivers | Demo |
|---|---|---|
| S1 | Foundations: auth, tenancy + RLS, members, teams, permission registry, audit, app shell. Then Catalog: responsibilities, bitemporal ownership, criticality, CSV import, rules engine, Risks, Home | Import an org from CSV; see "no backup" risks; assign a backup and watch the risk resolve |
| S2 | Manual Transfer case: playbook engine, scope items, tasks, approvals, readiness, closure with the ownership switch on the effective date, My Work, comments, email | A full transfer with no AI |
| S3 | GitHub connector: connector framework, webhook inbox, health states, identity mapping, Ownership Suggestions | Connect GitHub; bulk-accept suggested responsibilities |
| S4 | AI runtime + case analysis: registry, LLM gateway, budgets, validator, proposals, run viewer, evidence pool + consent | "Analyse case" produces evidence-backed findings and proposed tasks |
| S5 | Linear connector (read + approval-gated issue creation with receipts), Interviews, Capsule, access-request tasks | **PRD Appendix A demo**, with knowledge as manual links |
| S6 | Notion connector + knowledge verification + review queue; Temporary Coverage + Return Briefing; light Departure | Absence case with auto-expiring cover; a Notion runbook goes stale and gets re-verified |
| S7 | Pilot hardening (the deferred items, chosen by what the pilot needs) | — |

[ASSUME] Roughly 4–6 months full-time to reach S6. This depends heavily on hours available and how much code review the AI-generated code needs.

**Working effectively with AI assistants:**
- Keep conventions and module boundaries in a `CLAUDE.md` / `AGENTS.md`, and record decisions as short ADRs in `docs/adr/`.
- Generate the tenant-isolation and permission tests from the registry, so the assistant can't quietly skip authorisation.
- Use strong typing, an OpenAPI-generated client and import-linter rules. They catch the mistakes AI code tends to make.
- Work in one vertical slice per branch. Read every migration and every `authorize()` call yourself.

---

*Team-based plan (long-term reference). Assumptions [ASSUME]: 3–5 engineers and one product owner.*

### Phase 0 — Validation & spikes (≈2–3 weeks, in parallel with M0)

- Customer discovery (8–12 interviews, using the competitive study's §13 questions). Validate: Departure in v1, Temporary Coverage frequency, readiness acceptance, the "Risks" label.
- Spikes (each ends in a one-page decision record):
  - **S1** Permission APIs: GitHub, Linear, Notion (what is actually exposed, and webhooks for membership/visibility).
  - **S2** Job queue: Procrastinate vs in-house `SKIP LOCKED` (crash recovery, periodic jobs, per-tenant concurrency).
  - **S3** LLM layer: PydanticAI vs thin custom (structured output reliability, tools, streaming, tests).
  - **S4** SQLAlchemy async + RLS + `SET LOCAL` + pooler behaviour + LISTEN/NOTIFY.
  - **S5** Embeddings provider + FTS/hybrid baseline on the synthetic corpus.
  - **S6** Auth provider (B2B orgs, SSO path, pricing, FastAPI JWT verification).
  - **S7** Legal: model provider DPA/zero-retention, licence register template (SBOM).

### Phase 1 — First usable release (manual-first, then connectors, then AI)

| Milestone | Delivers (vertical slice) | Demo | Exit criteria |
|---|---|---|---|
| **M0 Foundations** (≈3 wks) | Monorepo, CI, auth, tenant + RLS + composite FKs, members/invites, teams, permission registry skeleton, audit log, app shell (sidebar, ⌘K stub, states library), generated API client | Sign up, create workspace, invite, create teams; audit log shows it | Tenant-isolation and permission test generators running in CI |
| **M1 Catalog + Risks (no AI, no integrations)** (≈3 wks) | Responsibilities, bitemporal ownership, criticality & coverage policy, assets (manual), CSV import, rules engine v1, Risks screen, Home v1, person/team pages, "as of" history | Import a CSV org; see "3 critical responsibilities without backup"; assign backup inline; finding resolves | **Usable on its own** for coverage hygiene |
| **M2 Manual Transfer case** (≈4 wks) | Playbook engine, Transfer playbook, wizard, scope items, tasks, approvals (hash-bound), readiness criteria, closure + effective-dated switch, My Work inbox, comments/mentions, in-app + email notifications, reminders/escalation, case activity | Full transfer of 2 responsibilities to 2 receivers, with approvals and readiness, **no AI**; ownership flips on the effective date | AC-01 (manual variant), cancel/reopen paths pass |
| **M3 GitHub + connector framework** (≈3 wks) | Connector contract, sync engine, webhook inbox, health states, identity mapping, GitHub App (repos, teams, CODEOWNERS, catalog-info, issues/PRs), **Ownership Suggestions** (deterministic), mismatch rule | Connect GitHub → 20 suggested responsibilities → bulk accept → Risks updates | AC-05 (dup webhooks), stale/partial states visible |
| **M4 Linear + Notion + Knowledge** (≈4 wks) | Linear and Notion connectors, visibility mappings, linked + native knowledge, verification tied to source revision, stale-on-change, review queue, FTS search (⌘K), open work on assets | A Notion runbook edit flips it to stale; steward verifies from the queue | AC-03 (revocation), AC-07 (conflict, manual) |
| **M5 AI runtime + case analysis** (≈4 wks) | Capability registry, LLM gateway, budgets, tool gateway, validator, proposals, run viewer, evidence pool + consent, Discovery service, `classify_relevance`, `synthesize_impact`, `propose_plan_additions`, eval harness + CI gate | "Analyse case" → evidence-backed findings + proposed tasks; outgoing owner consents to share 2 items; kill switch demo | AC-02, AC-04 (no writes yet), AC-10, injection suite green |
| **M6 Interviews, briefings, approved actions** (≈4 wks) | Interview cards + brain-dump, Knowledge Review drafting, briefing composer (Capsule), access-request tasks, Action Executor (Linear + GitHub issue creation), receipts, reconciliation | The full **PRD Appendix A demo**, including one negative path | AC-01 (full), AC-04, AC-06 |
| **M7 Coverage, Onboarding, Departure (light)** (≈4 wks) | Temporary Coverage playbook + asset-scoped digest + Return Briefing; Onboarding playbook; Departure playbook (parent case → items) + Emergency flag | Absence 10–24 Dec with auto-expiring temporary assignments and a cited return briefing | AC-08 |
| **M8 Pilot hardening** (≈3–4 wks) | Insights v1, hybrid search, scoped Ask, digests, transparency page, SSO, delegation/fallback approvers, data export, billing (if commercial pilots), accessibility audit, load tests, pentest, runbooks | Pilot workspace with real (customer-approved) connectors | PRD Appendix C checklist complete |

Total Phase 1: roughly 7–9 months at this team size [ASSUME]. **Reprioritisation option:** if a demo or pilot date forces it, M5/M6 (AI) can move ahead of M4's Notion work, but **never ahead of M2**. The case workflow must be correct without AI first.

### Phase 2 — Cross-functional (from PRD §19.3, adjusted)

HRIS trigger (one validated vendor), Internal Move and Account Handover playbooks, Slack/Google Workspace (customer-chosen), department responsibility templates, conflict/duplicate detection, Incident-to-Knowledge, Decision lineage, capsule export with omissions report, standing approvals, MCP/read API, graph tab, outbound webhooks, Notion append write-back.

### Phase 3 — Enterprise (PRD §19.4)

Playbook builder, SCIM, legal hold, multi-region, dedicated tenancy, advanced audit (hash chain), Temporal **only if** the D5 trigger fired.

---

## P. Open decisions

| ID | Decision | Options | My recommendation | Needed by |
|---|---|---|---|---|
| **D1** | Ownership model | (a) Owners on responsibilities *and* assets; (b) **ownership only on responsibilities; asset owner derived** | (b) + hard single-primary invariant + `co_owner` role | M1 |
| **D2** | Evidence pool rule (§M.4) | Approve as written / modify | Approve | M5 (design in M2) |
| **D3** | Notion visibility strategy | (a) admin visibility mappings; (b) per-user OAuth verification; (c) both | (a) in v1, (b) P1 — pending S1 | M4 |
| **D4** | Ship light Departure playbook in v1 | Yes / No (PRD: later) | **Yes**, without HRIS | Phase 0 (customer interviews) |
| **D5** | Workflow durability + queue | DB state machine + Procrastinate / in-house queue / Temporal | DB state machine; queue per S2; Temporal deferred with explicit trigger | M0 |
| **D6** | LLM framework | LangGraph / PydanticAI / custom | No LangGraph; PydanticAI or custom per S3 | M5 (spike in Phase 0) |
| **D7** | Auth provider | WorkOS / Clerk / Auth0 / self-hosted | Managed, chosen per S6; Relay DB owns authorisation | M0 |
| **D8** | Hosting & data region | Vercel + PaaS/AWS; EU vs US | Same-region managed Postgres with pgvector + PITR; region by pilot geography | M0 |
| **D9** | Context Capsule form | Live per-viewer view / frozen export / both | Live (P0), export P2 with omissions report | M6 |
| **D10** | Model & embedding providers, data terms | Claude family as default via port; embeddings provider TBD | Claude (Haiku/Sonnet/Opus 5.5 tiers per evals); embeddings per S5; zero-retention terms mandatory | M5 (legal before pilots) |
| **D11** | Tenancy model | Pooled multi-tenant / single-tenant | Pooled + RLS; dedicated tier later | M0 |
| **D12** | UI label "Risks" vs "Continuity Debt" | — | "Risks" in nav; "Continuity Debt" as metric | M1 (test in interviews) |
| **D13** | Retention defaults (§M.6) | — | Approve defaults; legal review per launch jurisdiction | M4 |
| **D14** | Default visibility of responsibility records to all members | Open by default / scoped by team | Open by default (enables "who owns X"); `restricted` flag | M1 |
| **D15** | Criticality tiers & who can set `critical` | — | 4 tiers; `critical` needs Continuity Manager/Admin | M1 |
| **D16** | Separation of duties default | Off / on for critical / on for all | On for critical only | M2 |
| **D17** | Who may self-initiate a case (Temporary Coverage for own absence; self-transfer) | Policy | Allow self-initiated Coverage; Transfer requires manager | M2 |
| **D18** | Linear/GitHub write actions in v1 | Create only / create + update | Create only (+ close via approved action P1) | M6 |
| **D19** | Billing in Phase 1 | Yes / pilots free | Metering in P0 (budgets); billing at M8 only if pilots are paid | M8 |
| **D20** | Public API / MCP timing | P2 / earlier | P2 (read-only, permission-filtered) | Phase 2 |
| **D21** | Readiness criteria configurability | Template-only / template + per-case custom | Template defaults + per-case additions (no custom types) | M2 |
| **D22** | Retention of evidence excerpts after source deletion | Follow source / keep for case retention | Follow source by default; tenant option to retain minimal excerpt for closed cases (legal review) | M4 |

---

## Closing summary

### 1. What we're building
A system of record for **responsibilities and their owners over time**, plus a **governed workflow for transferring them** when people, projects or systems change. Evidence-backed AI reduces the investigation and drafting work, and every consequential step stays under human approval. Engineering organisations are the entry point because their ownership signals are machine-readable. The domain model stays cross-functional from day one.

### 2. Recommended final architecture
A modular Python monolith (FastAPI, SQLAlchemy 2.x, Pydantic) with `api` / `worker` / `scheduler` processes. PostgreSQL provides domain data, the job queue, FTS, pgvector, RLS and the outbox. A deterministic DB-persisted workflow engine runs the cases. AI is a set of typed, versioned capabilities that only produce proposals, read only from a permission-safe evidence pool, and are executed by a deterministic Action Executor with idempotency and receipts. The frontend is Next.js + shadcn/ui on a generated typed client, with no backend logic in Next. Connectors are narrow and contract-based (GitHub App, Linear, Notion) with a per-connector permission strategy. There is no Redis, Celery, Temporal, LangGraph, graph DB, vector DB or microservices until a named trigger fires.

### 3. Biggest problems in the current specification
1. **No catalogue bootstrap.** The product's core object starts empty. Fix: Ownership Suggestions + CSV import (M1).
2. **The hero story (departure) is out of scope.** Fix: a light Departure playbook in v1 (C2).
3. **Source-ACL mirroring is assumed but not feasible for Notion** via the public API [ASSUME, S1]. Fix: a per-connector strategy and an honest UI (I1).
4. **No mechanism for "manager authority ≠ access to employee content", and AI synthesis can leak.** Fix: the evidence pool with consent (§M.4).
5. **Over-agentified design.** Ten agents, of which about two need an LLM loop. Fix: the capability classification (§I.2).
6. **Inconsistent core taxonomies:** fact/inference labels, roles vs relationships, the 11-state case machine, and dual ownership. Fix: the unified models in §B.2, §F and §K.
7. **Missing operational basics:** multi-responsibility scope items, comments, reminders and escalation, access prerequisites, deactivated-owner detection, and approver delegation.

### 4. Most important architectural decisions
D1 (ownership model), D2 (evidence pool), D3 (Notion visibility), D5 (workflow and queue), D6 (LLM framework), D7 (auth), D8 (hosting and region) and D10 (model provider and data terms). Plus the non-negotiable principle that LLMs never hold write tools.

### 5. Proposed implementation sequence
Phase 0 spikes and interviews → **M0** foundations → **M1** catalogue + risks (useful with no AI and no integrations) → **M2** manual transfer case → **M3** GitHub + suggestions → **M4** Linear/Notion + knowledge verification → **M5** AI runtime + case analysis → **M6** interviews, capsules, approved external actions (full demo) → **M7** coverage, onboarding, departure → **M8** pilot hardening.

*Awaiting review before any development begins.*
