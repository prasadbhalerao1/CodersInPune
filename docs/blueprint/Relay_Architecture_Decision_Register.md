# Relay — Architecture Decision Register

| Field | Value |
|---|---|
| Version | 0.1 — for founder review |
| Date | 8 Nov 2026 |
| Companion to | `Relay_Architecture_and_Product_Blueprint.md` (the "Blueprint"), `Relay_Implementation_Plan.md` |
| Working model | Founder-led, AI-assisted. Founder is the final decision-maker. |
| Status | Nothing in this register is approved. "Recommend lock" means *ready for founder sign-off*, not approved. |

## How to read this register

**Evidence tags**
- **[VERIFIED 2026-11-08]**: I checked this against the primary source linked in §R on 8 Nov 2026.
- **[KNOWN]**: documented, stable behaviour (e.g. PostgreSQL semantics) that I'm confident of but did *not* re-fetch today. A link is given; re-check it when implementing.
- **[UNVERIFIED]**: I could not confirm it. It needs a spike or vendor confirmation.
- **[REC]**: my recommendation. **[FOUNDER]**: needs your approval.

**Decision status values**
- **Recommend lock**: low uncertainty; sign it off now.
- **Lock after spike**: the direction is clear, but a ≤1-day experiment must confirm it.
- **Founder approval**: a product, commercial or legal call.
- **Defer**: not needed until a later milestone.

**Reversibility scale**
- **One-way**: schema, tenancy or security model; very expensive to change.
- **Costly**: weeks of rework.
- **Cheap**: config or adapter swap.

### Summary table

| ID | Decision | Recommendation | Status | Reversibility | Needed by |
|---|---|---|---|---|---|
| D1 | Ownership model | Assignments only on Responsibilities; valid-time + change log (revised) | Recommend lock | One-way | M1 |
| D2 | Evidence pool & privacy | Audience-scoped pool; synthesis over shared audience only (revised) | **Founder approval** (one policy toggle) | One-way | Schema M3, behaviour M8 |
| D3 | Notion visibility | Admin visibility mappings; per-user OAuth **dropped** (evidence) | Recommend lock | Costly | M7 |
| D4 | Departure playbook in v1 | Yes, manual, no HRIS | **Founder approval** | Cheap | M4 |
| D5 | Workflow engine & queue | Postgres state machine + outbox + Procrastinate | Lock after spike (S2) | Costly | M0 |
| D6 | LLM framework | PydanticAI behind own port; no LangGraph | Lock after spike (S3) | Cheap | M8 |
| D7 | Auth provider | WorkOS AuthKit (authN only) | **Founder approval** (vendor) | Costly | M0 |
| D8 | Hosting & data region | Single-region PaaS + managed PG 17/18 with pgvector | **Founder approval** (region) | Costly | M0 |
| D9 | Context Capsule form | Live per-viewer view; export later | Recommend lock | Cheap | M9 |
| D10 | Model & embeddings providers | Anthropic (Claude) via port; embeddings deferred (Voyage candidate) | **Founder approval** (contract) | Cheap | M8 |
| D11 | Tenancy model | Pooled multi-tenant + RLS + composite FKs | Recommend lock | One-way | M0 |
| D12 | "Risks" vs "Continuity Debt" label | "Risks" in nav | **Founder approval** (brand) | Cheap | M2 |
| D13 | Retention defaults | Defaults in §D13; legal review before pilots | **Founder approval** | Costly | M7 |
| D14 | Default visibility of responsibility records | Visible to all members; `restricted` flag | **Founder approval** | Costly | M1 |
| D15 | Criticality tiers | 4 fixed tiers, editable labels/definitions | Recommend lock | Costly | M1 |
| D16 | Separation of duties default | Off; on for `critical` | Recommend lock | Cheap | M3 |
| D17 | Self-initiated cases | Coverage yes; Transfer/Departure manager-only | Recommend lock | Cheap | M3 |
| D18 | External write scope v1 | Create-only (Linear issue, GitHub issue) | Recommend lock | Cheap | M6 |
| D19 | Billing timing | Defer; metering of AI spend from M8 | Defer | Cheap | M10 |
| D20 | Public API / MCP | Defer to post-pilot | Defer | Cheap | — |
| D21 | Readiness configurability | Template defaults + per-case additions of fixed types | Recommend lock | Costly | M3 |
| D22 | Evidence after source deletion | Excerpts hidden; statements kept with "evidence withdrawn" | **Founder approval** (+legal) | Costly | M7 |
| D23 *(new)* | Postgres driver | psycopg 3 for SQLAlchemy and the queue | Lock after spike (S4) | Cheap | M0 |
| D24 *(new)* | Primary key strategy | UUIDv7 | Recommend lock | One-way | M0 |
| D25 *(new)* | Time-history mechanism | Valid-time columns + append-only change tables (not full bitemporal) | Recommend lock | One-way | M1 |
| D26 *(new)* | Cross-tenant background work | Scheduler fans out per tenant; no BYPASSRLS in app paths | Recommend lock | Costly | M0 |

---

## Part 1 — Decisions D1–D26

Decisions that shape the schema, permissions, tenancy, workflow or data architecture are analysed in the most depth (D1, D2, D5, D11, D23–D26).

### D1 — Ownership model

1. **Problem.** Who is accountable for what, over time, with one source of truth. The PRD gives owners to both Responsibilities and Assets (Blueprint C7), which creates two ownership systems that will drift apart.
2. **Options.**
   - (a) Owners on both Responsibilities and Assets.
   - (b) Assignments only on Responsibilities; asset owner derived from the responsibility that stewards it.
   - (c) A polymorphic assignment target (responsibility | asset).
3. **Recommendation.** **(b)**, with two refinements to the Blueprint (see Q-A in Part 3):
   - **Refinement 1.** The Blueprint proposed full bitemporal rows (`recorded_at`, `superseded_at`). Challenging that: full bitemporality makes every planned end-date a supersede operation, complicates every query, and is hard for a solo builder to get right. **Revised:** valid-time (`valid_period tstzrange`) on the assignment row, with transaction-time answered by an **append-only `ownership_assignment_change` table** written in the same transaction (D25). "What did Relay believe on date X" is then answerable from the change log, which is rarely needed and needs no special query path.
   - **Refinement 2.** A single primary is a DB-enforced invariant. "Co-primary" needs are met by `co_owner`.
4. **Technical reasoning.** One assignment table means one exclusion constraint, one history, one "as-of" query and one set of rules. (c) doubles every rule and lets the two targets disagree.
5. **Product implications.**
   - Engineers ask "who owns repo X?". This is answered via the stewarding responsibility. Asset pages must show it prominently.
   - **Risk: catalogue bloat** (300 repos → 300 trivial responsibilities). Mitigations: one responsibility may steward many assets; Ownership Suggestions group repos by CODEOWNERS team.
6. **Security & ops.** Ownership is *not* an access grant. Backstage makes the same distinction [KNOWN]. Ownership never feeds L5 source visibility.
7. **Cost & complexity.** Lowest of the options.
8. **Reversible?** One-way (core schema).
9. **Milestone.** M1.
10. **Evidence needed.** None technical. Validate catalogue bloat in the first design-partner conversation [FOUNDER].
11. **Status.** Recommend lock.

### D2 — Evidence pool and privacy

1. **Problem.** Stop an outgoing employee's private or restricted content from reaching a manager or receiver, *including indirectly through AI synthesis*, while still letting the case work.
2. **Options.**
   - (a) No pool: rely on per-item ACL filtering at render time. *Fails*: AI text derived from restricted items leaks content.
   - (b) Blueprint rule: admit only evidence visible to *all* core participants, or explicitly shared.
   - (c) **Audience-scoped pool**: each pool entry has an audience, and synthesis runs only over entries whose audience covers the whole case audience.
3. **Recommendation.** **(c)**. Challenging (b): by design receivers *don't* inherit source access (PRD §17.6), so under (b) almost nothing is admitted without manual sharing, and the AI becomes useless. (c) formalises *who can see each piece* and makes the sharing act explicit. Full design in Part 3, Q-B.
4. **Technical reasoning.**
   - The pool is a table (`evidence_pool_entry`: case, evidence, audience = `case_all | coordinators | named principals`, `basis` = `source_visible_to_audience | shared_by_holder | relay_native`, `admitted_by`, `admitted_at`, `withdrawn_at`).
   - The Context Builder accepts only `audience = case_all` entries for case-level synthesis. Coordinator-only synthesis (e.g. impact on restricted repos) runs as a separate run whose output inherits the `coordinators` audience.
   - Outputs inherit the *narrowest* audience of their inputs. This is enforced in code and checked by the validator.
5. **Product implications.**
   - One consent/sharing step appears in Departure and Transfer.
   - The outgoing owner can share, withhold, or mark items as private.
   - Coordinators may also share org content they can see (subject to the policy toggle below). Receivers then get statements plus access-request tasks for the full source.
6. **Security & ops.** Every admission, withdrawal and revocation is audited. Source revocation withdraws entries (§D22). A non-negotiable test suite: no run output may cite or derive from an entry outside its audience.
7. **Cost & complexity.** Moderate: one table, one admission service, one Context Builder rule. Cheaper than retrofitting after leaks.
8. **Reversible?** One-way. It shapes evidence, statements, runs and capsule rendering.
9. **Milestone.** Schema in M3 (case participants, audiences); behaviour in M7/M8.
10. **Evidence needed.** Legal view on coordinator-initiated sharing of restricted excerpts.
11. **Status.** **Founder approval** for one policy: *"Can a coordinator share an excerpt of a source the receiver can't access into the case?"*
    - Recommend: **ON** for `internal` classification, with audit.
    - **OFF** for `confidential`/`restricted`, which require the source owner's consent.

### D3 — Notion visibility strategy

1. **Problem.** Relay must not show Notion-derived content to users who can't see it in Notion.
2. **Options.**
   - (a) Admin visibility mappings (page subtree/teamspace → Relay teams).
   - (b) Per-user OAuth verification.
   - (c) Mirror Notion ACLs.
3. **Recommendation.** **(a) only. Drop (b) and (c)** (this changes the Blueprint, which kept (b) as P1).
4. **Technical reasoning.**
   - Notion's capabilities reference documents access as page sharing to a *connection*. It documents no endpoint that lists which users can access a page [VERIFIED 2026-11-08].
   - The webhook event catalogue (23 types) has **no permission or sharing event**. The `accessible_by` field lists only the bots/users *owning the connection* that can access the entity, and only for public connections [VERIFIED 2026-11-08].
   - So (c) is not possible. (b) does not work either: a user's own OAuth connection sees only the pages shared with *that connection*, which says nothing about their real workspace access [inference from the same docs; UNVERIFIED by experiment].
5. **Product implications.** The admin must map Notion areas to audiences. Unmapped pages default to *connecting admin + explicit case sharing*. The connector UI states this plainly.
6. **Security & ops.**
   - Over-mapping (marking a private area "everyone") is the main risk. Show page counts and sample titles before confirming a mapping. Audit mapping changes.
   - Revocation: unsharing a page from the integration shows up only on the next fetch (object not found) [inference]. Nightly reconciliation is therefore mandatory.
7. **Cost & complexity.** Low.
8. **Reversible?** Costly (data visibility semantics).
9. **Milestone.** M7.
10. **Evidence needed.** S1 hands-on test: confirm `object_not_found` behaviour after unsharing, and the latency until it's detectable.
11. **Status.** Recommend lock.

### D4 — Ship a light Departure playbook in v1

1. **Problem.** The hero story (a leaver) is otherwise out of scope.
2. **Options.**
   - (a) Defer, as in the PRD.
   - (b) Manual Departure playbook (a parent case spawning Transfer items) without HRIS.
   - (c) HRIS-triggered offboarding.
3. **Recommendation.** **(b)**. It reuses the Transfer engine; the marginal work is the parent case and the consent step (needed by D2 anyway).
4. **Technical.** The parent case owns scope items. No new state machine.
5. **Product.** It aligns the demo with the shipped product. Positioning risk: buyers compare it with ServiceNow offboarding (Blueprint §D). Mitigate by framing it as "responsibility handover", not HR offboarding.
6. **Security.** The consent step must be robust. Deactivation in the IdP is outside Relay.
7. **Cost.** Band S on top of Transfer.
8. **Reversible?** Cheap.
9. **Milestone.** M4.
10. **Evidence.** None technical. This is a positioning choice.
11. **Status.** **Founder approval.**

### D5 — Workflow engine and job queue

1. **Problem.** Cases run for days or weeks: waits on humans, reminders, approvals, retries, temporary assignment expiry. All of it must survive crashes and deploys.
2. **Options.**
   - Engine: (a) Postgres state machine; (b) Temporal; (c) DBOS-style durable library.
   - Queue: (i) custom `SKIP LOCKED`; (ii) Procrastinate; (iii) PgQueuer; (iv) Redis-based (Celery/RQ/Dramatiq).
3. **Recommendation.** **Engine (a). Queue (ii) Procrastinate**, with **our own transactional outbox** as the consistency layer. Detail in Q-D.
4. **Technical reasoning.**
   - Case "long-running-ness" is *data waiting for humans*, not a process waiting. A row with `stage`, `due_at` and step records is the natural model.
   - Temporary-assignment expiry needs **no job at all**, because the valid-time range ends.
   - Procrastinate: MIT; v3.10.0 released 2026-09-23; active (last push 2026-11-02); retries, periodic tasks, task locks, priorities and stalled-job retry documented [VERIFIED 2026-11-08].
   - Its docs do **not** mention enqueueing inside the application's own transaction [VERIFIED absence]. Hence the outbox: domain write + `outbox_event` in one transaction, then a relay defers jobs. That gives at-least-once delivery with idempotent handlers, and the queue's transaction semantics stop mattering.
   - PgQueuer: MIT, v1.6.0 (2026-10-11), similar star count [VERIFIED 2026-11-08]. Features not reviewed (fetch failed) [UNVERIFIED].
   - Custom `SKIP LOCKED`: ~300 lines, but retries, periodic jobs, stalled detection and admin tooling would all be ours to build and debug.
4b. **Challenge to my own recommendation.**
   - Procrastinate couples us to its schema and to psycopg (D23).
   - If S2 shows friction with our SQLAlchemy session or tests, the custom queue is a credible fallback, because the outbox already isolates the domain from the queue.
5. **Product.** None visible; reliability shows up as "nothing gets lost".
6. **Security & ops.** One datastore to back up. Every job sets the tenant context (D26). Visibility: jobs table + run viewer.
7. **Cost.** Lowest operational cost. No Redis bill, no Temporal cluster or Temporal Cloud.
8. **Reversible?** Costly for the engine (all workflows), cheap for the queue (behind outbox + thin adapter).
9. **Milestone.** M0.
10. **Evidence.** S2 (half-day): psycopg connector + SQLAlchemy coexistence, stalled-job recovery after `kill -9`, periodic task with a single leader, per-tenant concurrency via locks.
11. **Status.** Lock after spike.

### D6 — LLM execution framework

1. **Problem.** Typed structured outputs and tool definitions without a second workflow state machine.
2. **Options.**
   - (a) PydanticAI.
   - (b) Thin custom layer over the Anthropic SDK.
   - (c) LangGraph.
3. **Recommendation.** **(a) behind our own `LLMPort`**. Use only its agent loop, output types, tools and OTel instrumentation, *not* pydantic-graph or its durable-execution integrations. **(c) rejected.**
4. **Technical.**
   - PydanticAI: MIT; v2.66.0 (2026-11-04); typed `output_type` with validation-retry; tools from typed functions with argument validation; `RunContext` dependency injection; Anthropic supported; OTel spans [VERIFIED 2026-11-08].
   - It also offers Temporal/DBOS/Prefect durable execution and pydantic-graph [VERIFIED]. These are exactly the "second state machine" we must not adopt.
   - LangGraph is MIT and widely used [VERIFIED stars/licence], but its value is graph state plus checkpointing plus interrupts, which duplicates D5.
4b. **Challenge.**
   - PydanticAI's version number (v2.66) signals a fast release cadence, so API churn is a real risk. Mitigation: pin exactly, wrap behind `LLMPort`, keep usage to a narrow surface.
   - If the wrapper ends up thinner than the library is worth, (b) is fine. The Anthropic SDK already supports tools and structured output.
5. **Product.** None directly.
6. **Security.** The tool allowlist and actor scoping live in *our* Tool Gateway, not the framework. Our own validator enforces citations.
7. **Cost.** Low. Swapping is cheap behind the port.
8. **Reversible?** Cheap.
9. **Milestone.** M8.
10. **Evidence.** S3: build `synthesize_impact` once with PydanticAI. Judge: output validation retries, streaming, test doubles (fake model), token accounting hooks.
11. **Status.** Lock after spike. "No LangGraph" can be locked now.

### D7 — Authentication provider

1. **Problem.** Secure sign-in, an invitations UX, a later SSO/SCIM path, and FastAPI JWT verification, with Relay owning authorisation.
2. **Options.** WorkOS AuthKit, Clerk, Auth0, self-hosted (Keycloak/Zitadel/Better Auth).
3. **Recommendation.** **WorkOS AuthKit, used for authentication only.** Relay owns workspaces, memberships, roles and invitations. AuthKit verifies identity, and later SSO and Directory Sync.
4. **Technical / pricing** [VERIFIED 2026-11-08, see §R]:

| Provider | Base | B2B orgs | SSO | SCIM |
|---|---|---|---|---|
| WorkOS | AuthKit free to 1M MAU | Not stated on pricing page | $125/connection/mo (1–15) | Same tiers as SSO |
| Clerk | Pro $25/mo (50k MRU incl.) | Free: 100 orgs, **20 members/org cap**; Enhanced $100/mo | 1 incl., extra $75/mo | 1 incl. on Pro (billing starts 1 Jan 2027) |
| Auth0 | Free 25k MAU, **5 orgs** | B2B Essentials $150/mo (500 MAU) | 3 incl. (Essentials) | Included |

   - Clerk's free org tier caps members at 20, which a real B2B workspace will hit. Auth0's free tier caps at 5 orgs.
   - Because Relay owns memberships, we don't need the IdP's org features at all. That makes WorkOS's free AuthKit tier the cheapest path. SSO costs only arrive with an enterprise customer, who pays for it.
4b. **Challenge.**
   - Clerk has the best Next.js developer experience, which matters to a solo builder.
   - But Relay's backend is Python, and the IdP's orgs would be a duplicate source of membership truth (a D11 risk).
   - Lock-in is low either way if we store `idp_subject` + verified email and own everything else.
5. **Product.** Users sign in with email/Google/Microsoft. Enterprise SSO is a paid upgrade.
6. **Security.**
   - Verify JWT signature (JWKS), issuer, audience and expiry in FastAPI.
   - Short token lifetime plus a membership status check per request (deactivation takes effect immediately in Relay even if the IdP session lives on).
   - Never auto-join a workspace by email domain without an admin setting.
7. **Cost.** $0 until SSO is sold.
8. **Reversible?** Costly but bounded: user re-linking via verified email.
9. **Milestone.** M0.
10. **Evidence.** S6 (half-day): AuthKit + Next.js session + FastAPI JWKS verification + invitation-acceptance flow by verified email. **Confirm the AuthKit org/RBAC features don't conflict with keeping orgs in Relay** [UNVERIFIED].
11. **Status.** **Founder approval** (vendor relationship).

### D8 — Hosting and data region

1. **Problem.** Where Relay runs and where customer data lives.
2. **Options.**
   - Platforms: Vercel + Render/Railway/Fly + managed Postgres; AWS (ECS + RDS); a single PaaS for everything.
   - Region: India, EU, US.
3. **Recommendation.**
   - One PaaS for api+worker, plus managed Postgres **in the same region**, with: pgvector ≥ 0.8 (iterative scans, D-S5), PITR, `btree_gist`, `pg_trgm`, PG 17 or 18. Frontend on Vercel or the same PaaS.
   - **Region: choose by where your first design partners are.** If unknown, pick one region now and keep `tenant.region` in the schema.
4. **Technical.** The provider must support `btree_gist` and the required pgvector version [UNVERIFIED per provider; check before choosing]. Avoid serverless Postgres with connection behaviour that breaks `LISTEN` or session settings unless a direct connection is available.
5. **Product.** Data residency questions come up in Indian enterprise (DPDP Act 2023) and EU (GDPR) procurement [KNOWN; not legal advice].
6. **Security & ops.** Managed backups, encryption at rest, private networking between app and DB where the PaaS supports it.
7. **Cost.** Roughly $50–150/month at MVP scale [UNVERIFIED estimate].
8. **Reversible?** Costly (data migration), but straightforward while small.
9. **Milestone.** M0.
10. **Evidence.** Check the provider's extension list and pgvector version.
11. **Status.** **Founder approval:** region, and the platform after the extension check.

### D9 — Context Capsule form

1. **Problem.** Give receivers a package of context without breaking permissions.
2. **Options.** (a) Live per-viewer rendering; (b) frozen export; (c) both.
3. **Recommendation.** (a) now. (b) later as an admin-gated, audited export with an omissions report.
4. **Technical.** The capsule is a *view* over statements and pool entries filtered by audience (D2). There is no copy to keep in sync.
5. **Product.** Receivers see current, permission-correct content.
6. **Security.** No uncontrolled copies.
7. **Cost.** Low.
8. **Reversible?** Cheap.
9. **Milestone.** M9.
10. **Evidence.** None.
11. **Status.** Recommend lock.

### D10 — Model and embeddings providers, data terms

1. **Problem.** Which LLM and embedding providers process customer content, and on what terms.
2. **Options.** Anthropic (Claude), OpenAI, others via `LLMPort`. Embeddings: Voyage AI (Anthropic's documented partner), OpenAI, a self-hosted open model.
3. **Recommendation.** **Anthropic** as the default LLM via the port, with capability-level model tiers decided by evals. **Embeddings deferred**: FTS only until post-pilot (S5). When needed, Voyage AI is the first candidate, evaluated against one alternative.
4. **Technical.**
   - Anthropic does not offer its own embedding model and points to Voyage AI. Voyage 4 models default to 1024 dimensions, within pgvector's 2,000-dimension HNSW limit for `vector` [VERIFIED 2026-11-08].
   - `voyage-4-nano` is open-weight (Apache 2.0) for self-hosting [VERIFIED].
5. **Product.** Customer-facing statement: "your data is not used to train models" is supportable for Anthropic (below).
6. **Security & legal** [VERIFIED 2026-11-08]:
   - Commercial Terms (effective 17 Jun 2025): *"Anthropic may not train models on Customer Content from Services."*
   - The DPA *"is incorporated into these Terms by reference."*
   - API inputs/outputs are deleted *"within 30 days"*. Usage-policy-flagged content is kept up to 2 years. Zero data retention is available by separate agreement.
   - Subprocessor list: not checked [UNVERIFIED]. Fetch it before pilots.
7. **Cost.** Usage-based. Budgets per tenant (Blueprint §I.10).
8. **Reversible?** Cheap (port).
9. **Milestone.** M8. Legal confirmation before the first pilot with real data.
10. **Evidence.** Decide whether pilots need ZDR (enterprise prospects may require it). Check Voyage's data terms when embeddings are adopted.
11. **Status.** **Founder approval** (provider contract; ZDR request yes/no).

### D11 — Tenancy model

1. **Problem.** Isolate customers cheaply and reliably.
2. **Options.** (a) Pooled tables + `tenant_id` + RLS; (b) schema-per-tenant; (c) database-per-tenant.
3. **Recommendation.** **(a)**, with four layers: service-level tenant scoping, RLS (fail-closed), composite `(tenant_id, id)` FKs, and generated isolation tests. Detail and traps in Q-F and S4.
4. **Technical.** (b) and (c) multiply migrations and connections, which is untenable solo. With (a), a dedicated-DB tier can be added later because `tenant_id` is everywhere.
5. **Product.** Cheapest onboarding; instant workspace creation.
6. **Security.** The risk is a single bug exposing cross-tenant data. Hence defence in depth and blocking tests.
7. **Cost.** Lowest.
8. **Reversible?** One-way in practice.
9. **Milestone.** M0.
10. **Evidence.** S4 trap checks.
11. **Status.** Recommend lock.

### D12 — Nav label: "Risks" vs "Continuity Debt"

- Problem: clarity for first-time users vs a distinctive brand term.
- Options: Risks / Continuity Debt / Gaps.
- Recommendation: "Risks" in navigation; "Continuity Debt" as the name of the backlog metric in Insights.
- Implications: purely UX/brand.
- Reversible: cheap.
- Milestone: M2.
- Evidence: 3–5 user reactions.
- **Status: Founder approval.**

### D13 — Retention defaults

1. **Problem.** How long each data class lives.
2. **Options.** Per-class defaults (Blueprint §M.6), configurable per tenant within bounds.
3. **Recommendation.**
   - Source snapshots/chunks: while connected and in scope; removed ≤24 h after source deletion or revocation is detected; ≤30 days after disconnect.
   - Agent run metadata: 1 year. Raw prompt capture: off by default, ≤14 days when on.
   - Audit: 2 years default (configurable 1–7).
   - Closed cases: 2 years.
4. **Technical.** Retention jobs per class. Embeddings deleted with chunks.
5. **Product.** It affects what a re-opened case can show.
6. **Security/legal.** Needs counsel review for the launch jurisdiction [UNVERIFIED legal].
7. **Cost.** Low.
8. **Reversible?** Costly (data already deleted can't come back).
9. **Milestone.** M7.
10. **Evidence.** Legal review.
11. **Status.** **Founder approval** + legal.

### D14 — Default visibility of responsibility records

1. **Problem.** "Who owns X?" only works if records are broadly visible. Some responsibilities are sensitive (e.g. "Payroll approver", "Security incident lead").
2. **Options.** (a) Visible to all members by default, with a `restricted` flag; (b) team-scoped by default.
3. **Recommendation.** (a). The record (name, owners, team) is visible. *Evidence and knowledge* stay governed by L5/D2.
4. **Technical.** One boolean in the `visible()` predicate.
5. **Product.** Enables directory-style discovery, a core value.
6. **Security.** A restricted responsibility hides its existence from non-scoped users (search, counts, Risks).
7. **Cost.** Trivial.
8. **Reversible?** Costly once customers rely on discovery.
9. **Milestone.** M1.
10. **Evidence.** None.
11. **Status.** **Founder approval** (privacy posture).

### D15 — Criticality tiers

- Recommendation: 4 fixed tier *keys* (`critical/high/standard/low`) with tenant-editable labels and definitions. Team Managers set ≤ high; `critical` needs Continuity Manager/Admin.
- Reasoning: fixed keys keep policies, rules and reports stable. Custom tiers would break the rule engine.
- Reversible: costly (rules depend on keys). Milestone: M1.
- **Status: Recommend lock.**

### D16 — Separation of duties default

- Recommendation: off by default; on for `critical` closure (approver ≠ initiator). Exceptions recorded.
- Reasoning: small organisations would otherwise be blocked.
- Reversible: cheap (policy). Milestone: M3.
- **Status: Recommend lock.**

### D17 — Self-initiated cases

- Recommendation: a member may open Coverage for their own absence (manager approval required to activate). Transfer/Departure only by Team Manager+ (a member may *request* one).
- Reversible: cheap. Milestone: M3.
- **Status: Recommend lock.**

### D18 — External write scope in v1

1. **Recommendation.** Create-only: Linear `issueCreate`, GitHub issue create. No updates or closes in v1. Status is *pulled* back.
2. **Reasoning.** It minimises blast radius and conflict handling.
3. **Implementation.**
   - Linear app-actor tokens make mutations come from the app, and `createAsUser` can attribute to the requester [VERIFIED 2026-11-08].
   - GitHub App installation tokens: 5,000/h base, scaling to 12,500/h. Content-creation secondary limit is 80/min and 500/h [VERIFIED].
4. **Reversible?** Cheap. **Milestone:** M6.
5. **Status.** Recommend lock.

### D19 — Billing timing

- Recommendation: defer Stripe until paid pilots. Per-tenant AI cost metering ships with M8 because budgets need it anyway.
- Reversible: cheap. **Status: Defer.**

### D20 — Public API / MCP

- Recommendation: defer to post-pilot. It must reuse `visible()` and the D2 audiences, so there's no design impact now beyond keeping the service layer the only data path.
- **Status: Defer.**

### D21 — Readiness configurability

- Recommendation: playbook templates define default criteria. Coordinators may add per-case criteria of the six fixed types. No custom types.
- Reasoning: the closure logic and reports depend on the fixed types.
- Reversible: costly. Milestone: M3.
- **Status: Recommend lock.**

### D22 — Evidence after source deletion or revocation

1. **Problem.** A cited source disappears or becomes inaccessible mid-case or after closure.
2. **Options.**
   - (a) Follow the source: hide excerpts, keep statements flagged "evidence withdrawn".
   - (b) Retain minimal excerpts for closed cases.
   - (c) Delete statements too.
3. **Recommendation.**
   - (a) by default.
   - Human-*verified* statements stay valid as `human_stated` (the human vouched for them).
   - AI-inferred statements whose only evidence was withdrawn are marked "unsupported" and excluded from new synthesis.
   - (b) is a tenant option only after legal review.
4. **Reversible?** Costly. **Milestone:** M7.
5. **Status.** **Founder approval** + legal.

### D23 (new) — Postgres driver

1. **Problem.** SQLAlchemy async needs a driver. Procrastinate uses psycopg. Two drivers means two pooling/prepared-statement behaviours.
2. **Options.** asyncpg, psycopg 3 (async).
3. **Recommendation.** psycopg 3 for both.
4. **Technical.** Trap: with a transaction-mode pooler, psycopg 3 prepares statements after repeated use unless `prepare_threshold=None`. asyncpg has the equivalent statement-cache issue [KNOWN — SQLAlchemy/psycopg docs; re-check during S4].
5. **Reversible?** Cheap. **Milestone:** M0.
6. **Status.** Lock after spike S4.

### D24 (new) — Primary keys

- Recommendation: UUIDv7. Time-ordered for index locality, safe to expose, no enumeration.
- PostgreSQL 18 provides a native `uuidv7()` [KNOWN; verify on the chosen managed version]. Otherwise generate in the application.
- Reversible: one-way. **Status: Recommend lock.**

### D25 (new) — Time-history mechanism

1. **Problem.** The Blueprint mixed bitemporal rows (ownership) with ad-hoc history elsewhere.
2. **Recommendation.**
   - Valid-time ranges (`tstzrange`, half-open `[)`) on facts that are true *in the organisation* for a period: assignments, memberships, grants, case participants, dependencies.
   - Every mutation of those tables writes an **append-only change row** (who, when, before/after, reason, correlation_id) in the same transaction, via the service layer (not DB triggers, so the actor context is explicit).
   - Status histories (case stage, finding state) are also append-only tables.
3. **Reasoning.** It answers "as-of" questions by simple range queries and answers "who changed what" from the change log. It avoids full bitemporal complexity.
4. **Reversible?** One-way. **Milestone:** M1.
5. **Status.** Recommend lock.

### D26 (new) — Cross-tenant background work

1. **Problem.** Periodic jobs (rules evaluation, reminders, freshness checks) touch all tenants, but RLS confines a connection to one tenant.
2. **Options.** (a) An app role with `BYPASSRLS` for workers; (b) the scheduler lists active tenants (one narrow query) and enqueues **one job per tenant**, each running under that tenant's RLS context.
3. **Recommendation.** (b).
   - Run the tenant-listing query through a minimal `SECURITY DEFINER` function owned by a separate role, returning only tenant IDs.
   - No application path ever holds `BYPASSRLS`.
4. **Reasoning.** It keeps RLS meaningful for all business logic. Per-tenant jobs also give fairness and isolation of failures.
5. **Reversible?** Costly. **Milestone:** M0.
6. **Status.** Recommend lock.

---

## Part 2 — Spike findings S1–S7

### S1 — Connector permissions

| Question | GitHub | Linear | Notion |
|---|---|---|---|
| Recommended auth | **GitHub App** (installation tokens; optional user tokens) | **OAuth app with `actor=app`** (workspace install) | **Public integration (OAuth)** |
| Per-user access determinable? | **Yes.** `GET /repos/{o}/{r}/collaborators/{user}/permission` returns the highest role "after considering all sources of grants, including: repo, teams, organization, and enterprise". `GET /repos/{o}/{r}/collaborators` includes team-derived members [VERIFIED 2026-11-08] | **Partially, team-level.** Issues belong to teams; private teams exist. App visibility of private teams is **not documented** on the actor page [UNVERIFIED] | **No.** No documented ACL endpoint; `accessible_by` only covers connection owners [VERIFIED 2026-11-08] |
| Required permission/scope | Listing collaborators needs write/maintain/admin on the repo (and `read:org`+`repo` for OAuth/classic tokens). The GitHub App permission name is not stated on that page [VERIFIED / UNVERIFIED respectively] | Scope names (`read`, `write`, `issues:create`, `admin`…) appear only in third-party guides [UNVERIFIED] | Capabilities: read/update/insert content, comments, user info with/without email [VERIFIED] |
| Revocation signals | Org/team/member/installation-repo webhooks exist [KNOWN; re-verify event names]; plus periodic ACL refresh | `OAuthApp revoked` webhook and `Users` data-change webhooks exist; **team membership changes are not documented** as webhook events → poll [VERIFIED 2026-11-08] | **No permission/sharing events** (23 event types listed) → detect on fetch failure + nightly reconcile [VERIFIED 2026-11-08] |
| Webhooks | Repo/org/issue/PR/membership events; HMAC signature [KNOWN] | Issues, comments, projects, project updates, documents, cycles, users, etc.; `Linear-Signature` HMAC-SHA256 over raw body; timestamp check ±1 min; retries 3× (1 min, 1 h, 6 h); may be auto-disabled [VERIFIED] | Page/database/data_source/comment events; `X-Notion-Signature` HMAC-SHA256; **metadata only, no content**; "at-most-once" aim with up to 8 retries over ~24 h; **events may arrive out of order** [VERIFIED] |
| Rate limits | Installation: 5,000/h base, +50/h per repo and per user beyond 20, max 12,500/h; 15,000/h on Enterprise Cloud. Secondary: 100 concurrent; 900 REST points/min; 80 content-creating requests/min, 500/h [VERIFIED] | OAuth app: 5,000 requests/h and 2,000,000 complexity points/h; max 10,000 points per query; default page size 50; `Retry-After` on 429 [VERIFIED] | 180 req/min per connection (600/min on Business/Enterprise workspaces); data source queries ~3 req/s; per-workspace shared budget; `Retry-After` (≤60 s per connection); payload ≤1000 blocks / 500 KB [VERIFIED] |
| Pagination | Link headers / GraphQL cursors [KNOWN] | Cursor (`first`/`after`), default 50 [VERIFIED] | Cursor; max page size not stated on the limits page [UNVERIFIED] |

**Conclusions.**
1. GitHub supports true per-user visibility. Compute `source_visibility` from repo collaborator lists (including team-derived) and refresh on webhooks plus nightly.
2. Linear: team-level visibility. Hands-on check needed for whether an `actor=app` install sees private teams, and how team membership changes surface (poll `teams { members }`).
3. Notion: mirroring is impossible with documented APIs. D3 = admin mappings. Notion webhooks are a *hint to re-fetch*, not a source of truth (metadata-only, at-most-once, unordered). Nightly reconciliation is mandatory.
4. Notion's free/standard-plan limit (180/min) makes initial full sync of large workspaces slow. Design sync as resumable, checkpointed and budgeted per tenant.

**Remaining hands-on tests (≤1 day total):**
- (a) Linear app install: private team visibility.
- (b) GitHub App permission set needed for collaborator listing.
- (c) Notion: behaviour after unsharing a page (error code, detection latency).

### S2 — Background jobs

| Criterion | Custom `SKIP LOCKED` | Procrastinate | PgQueuer |
|---|---|---|---|
| Licence / maturity | ours | MIT; v3.10.0 (2026-09-23); ~1.4k★; active [VERIFIED] | MIT; v1.6.0 (2026-10-11); ~1.5k★; active [VERIFIED] |
| Retries | build | yes (retry strategies) [VERIFIED] | [UNVERIFIED — docs fetch failed] |
| Periodic jobs | build | yes [VERIFIED] | [UNVERIFIED] |
| Concurrency control | build | task locks, queueing locks, priorities [VERIFIED] | [UNVERIFIED] |
| Crash recovery | build (lease + timeout) | "retry stalled jobs" how-to [VERIFIED exists; mechanism UNVERIFIED] | [UNVERIFIED] |
| Enqueue in app transaction | yes (same session) | **not documented** [VERIFIED absence] | [UNVERIFIED] |
| Deployment | none extra | worker process; its own tables | worker process; its own tables |

**Recommendation.** Procrastinate + our own outbox (D5). Idempotency is ours regardless: handler keys = `event_id` / `(workflow_step, input_hash)`.

**Spike S2 must prove:** worker `kill -9` → job retried; periodic job runs once with 2 workers; a per-tenant lock prevents parallel syncs for one tenant; tests can run jobs synchronously.

### S3 — AI execution framework

| Criterion | PydanticAI | Thin custom over Anthropic SDK | LangGraph |
|---|---|---|---|
| Structured output + validation retry | built-in [VERIFIED] | build (~100 lines) | via integrations |
| Typed tools + arg validation | built-in [VERIFIED] | build | yes |
| Dependency injection for actor/tenant context | `RunContext` [VERIFIED] | build | state object |
| Provider portability | many providers [VERIFIED] | single provider unless built | many |
| Workflow/state | optional (avoid) | none | **core** (graph + checkpoints) — duplicates D5 |
| Observability | OTel spans [VERIFIED] | build | LangSmith/OTel |
| Licence | MIT [VERIFIED] | — | MIT [VERIFIED] |

**Recommendation.** PydanticAI pinned, behind `LLMPort`, with its durable/graph features off. LangGraph gives no concrete benefit here: its main strengths (checkpointing, interrupts) are things we already own in Postgres.

**Spike S3:** one capability end-to-end, a fake-model unit test, and token accounting captured.

### S4 — SQLAlchemy & PostgreSQL traps (check before M0 code)

Each trap below is [KNOWN] PostgreSQL/SQLAlchemy behaviour unless marked otherwise. Links are in §R. Re-confirm during the S4 spike.

**RLS & tenancy**
1. **The table owner bypasses RLS** unless `ALTER TABLE … FORCE ROW LEVEL SECURITY`. Superusers and `BYPASSRLS` roles always bypass it. → The app connects as a non-owner role, and migrations run as the owner.
2. **`SET LOCAL` only lasts for the current transaction.** A plain `SET` on a pooled connection *leaks the tenant to the next request*. → Use `set_config('app.tenant_id', :t, true)` in a SQLAlchemy `after_begin` session event, so it runs in every transaction, including after commits in long jobs.
3. **Policies use `current_setting('app.tenant_id', true)`.** A missing value returns NULL, so the policy matches nothing (fail-closed). Never default to an "all tenants" value.
4. **Uniqueness leaks across tenants.** Any `UNIQUE` without `tenant_id` lets one tenant probe another's values via constraint errors. → Every unique key includes `tenant_id`.
5. **Composite FKs** `(tenant_id, parent_id) → parent(tenant_id, id)` need a unique constraint on the parent's `(tenant_id, id)`.
6. **Index order.** Put `tenant_id` first in composite indexes. RLS adds the predicate to every query.

**Pooling & connections**

7. **Prepared statements break under transaction pooling.** → Disable them (D23).
8. **`LISTEN` needs a dedicated session-mode connection.** Transaction poolers drop it. → One direct connection per API instance for SSE fan-out.

**Async session usage**

9. **`AsyncSession` isn't concurrency-safe.** One session per request or job. No `asyncio.gather` over one session.
10. **Lazy loading raises under async.** → Default `lazy="raise"` and load relations explicitly.
11. **Set `expire_on_commit=False`.** Otherwise post-commit attribute access triggers I/O.

**Alembic**

12. **Autogenerate does not reliably handle RLS policies, `EXCLUDE` constraints, extensions, functions or grants.** → Write those migration steps by hand (`op.execute`), and keep grants in migrations. Add a CI check that a fresh DB plus all migrations equals the models (autogenerate produces no diff for supported objects).
13. **Expand/contract migrations.** Never drop or rename in the same release as the code change.

**Temporal data**

14. **`EXCLUDE USING gist (tenant_id WITH =, responsibility_id WITH =, valid_period WITH &&) WHERE (role='primary' AND status='active')`** needs `btree_gist`. Use half-open `[)` ranges so contiguous handovers don't collide. Use an unbounded upper end for open assignments.
15. **Business "effective date" vs instant.** Store `tstzrange` instants computed from the case time zone at local midnight. Rely on the `[)` semantics.

**Outbox & queue**

16. **Outbox.** The relay reads unprocessed rows with `FOR UPDATE SKIP LOCKED`, defers jobs, then marks them dispatched. This is at-least-once delivery. Handlers dedupe via a `processed_event(handler, event_id)` unique row inserted in the handler's transaction. Ordering is not global: handlers must tolerate reordering (use entity version checks).

**pgvector**

17. **Filtering happens *after* the HNSW scan.** With `ef_search=40` and a 10%-selective filter, about 4 rows come back on average. → Use iterative index scans (pgvector ≥0.8.0) [VERIFIED 2026-11-08]. `vector` HNSW supports at most 2,000 dimensions; `halfvec` 4,000 [VERIFIED]. Latest tag is v0.8.7 [VERIFIED]. Tenant filter selectivity is high in pooled tenancy, so iterative scans are required.

### S5 — Search & embeddings

1. **v1 (through pilot): Postgres FTS + `pg_trgm` is sufficient** for what users search early on: titles, identifiers ("payment-service", "PAY-123"), people, short knowledge records. It shares the same permission predicate and transaction, so search results can't leak.
2. **Hybrid (vector + FTS with reciprocal-rank fusion) becomes necessary when** any of these hold:
   - (a) Scoped Ask / natural-language questions ship.
   - (b) Knowledge bodies are long and paraphrase-heavy (runbooks, ADRs).
   - (c) The eval shows recall@10 below target on a labelled query set of ≥50 queries.
3. **pgvector in the same Postgres** handles hybrid at expected pilot scale: per-tenant corpora in the tens of thousands of chunks. Iterative scans address filtered recall [VERIFIED feature].
4. **A separate vector DB is not justified.** It would duplicate permission filtering outside Postgres, which is a leakage risk. Revisit only if a benchmark on real tenant data shows that p95 filtered vector query latency or recall can't meet targets after tuning (`ef_search`, iterative scans, `halfvec`, partitioning). No such evidence exists.
5. **Embedding choice is deferred** (D10).

### S6 — Authentication

See D7 for the full comparison table.

- **Relay owns:** workspaces, memberships, roles, grants and invitations.
- **The IdP provides:** identity (subject + verified email), MFA, social login, and later SAML/OIDC SSO and SCIM.

**Flow:**
1. A Relay invitation is created.
2. The email links to the AuthKit sign-in.
3. On first login, the verified email matches the invitation and a membership is created.
4. FastAPI verifies the JWT on every request and loads the membership.

**Lock-in:** low (`idp_subject` + email mapping).

**Pricing:** $0 until SSO. SSO is $125 per connection per month on WorkOS, to be passed into enterprise pricing.

**Unverified:** AuthKit session handling with a separate Python API (token audience configuration); whether AuthKit features push us toward using WorkOS Organizations (we don't want to).

### S7 — Legal & licensing

**Dependency and project licences** (from the GitHub API and the licence files themselves, checked 2026-11-08):

| Project | Licence | Commercial-use notes |
|---|---|---|
| FastAPI, SQLAlchemy, Alembic, Next.js, shadcn/ui, TanStack Query/Table, xyflow (React Flow), hey-api/openapi-ts, Procrastinate, PgQueuer, PydanticAI, LangGraph, Temporal server & Python SDK, pgvector-python, DBOS-py, AnythingLLM, codebase-memory-mcp, SourceAnt, knowledge-transfer | MIT | Keep notices |
| Tiptap (repo) | MIT | Pro extensions are separately licensed [KNOWN] → core only |
| import-linter | BSD-2-Clause | Keep notices |
| pgvector (extension) | PostgreSQL Licence (permissive) | Runs inside managed PG; no distribution by us |
| Graphiti, Cognee, OpenFGA, SpiceDB, Backstage, OpenMetadata, Kestra, RAGFlow, Mem0 | Apache-2.0 | Keep NOTICE; patent grant |
| Onyx | MIT outside `ee/` dirs; Onyx Enterprise Licence inside `backend/ee`, `web/src/app/ee`, `web/src/ee` | **Never copy from `ee` dirs** |
| Langfuse | MIT outside `ee/`-style dirs; separate licence inside | Self-host CE only |
| n8n | Sustainable Use License; `.ee.` files under the Enterprise Licence | **Not OSS; no embedding or resale** |
| Outline | BSL 1.1; Additional Use Grant excludes use "for a Document Service"; Change Date 2030-10-23 → Apache-2.0 | **UX reference only** |
| Docmost | AGPL-3.0 | No code reuse without legal review |
| Frappe HR | GPL-3.0 | No code reuse |

**Model provider (Anthropic):** see D10 [VERIFIED].

**Not checked:**
- Anthropic's subprocessor list and ZDR eligibility terms.
- WorkOS/hosting/email providers' DPAs.
- Voyage data terms.

**What Relay itself needs before the first real-data pilot** [REC]:
- Its own DPA template.
- A public subprocessor list (hosting, DB, WorkOS, Anthropic, email, error monitoring).
- A data-flow diagram.
- A licence register / SBOM, generated in CI (CycloneDX for Python and npm), with a deny-list for AGPL/GPL/SSPL/BSL/SUL licences in production dependencies.

India's DPDP Act 2023 and GDPR obligations need counsel [UNVERIFIED; not legal advice].

---

## Part 3 — Foundational questions

### Q-A — Ownership model (resolves D1, D25)

- **Exclusive:** yes. `ownership_assignment` targets only `responsibility`. Assets reach owners through `responsibility_asset(relation='stewards')`.
- **Roles and their interaction:**

| Role | Cardinality at any instant | Meaning | Interaction |
|---|---|---|---|
| `primary` | exactly 0..1 (DB-enforced) | Accountable | 0 raises a finding if the tier requires one |
| `co_owner` | 0..n | Shares accountability for a defined sub-scope (free-text scope note) | Never replaces the primary |
| `backup` | 0..n (policy may require ≥1) | Can cover on demand | Must not be the same person as the primary (CHECK in service; finding if violated) |
| `temporary` | 0..n, always bounded `valid_period` | Acting holder during coverage | **Acting owner** = active temporary if any, else primary. The primary stays accountable (it is not replaced) |

- **Team assignees:** allowed for all roles. For `critical`, a team primary requires `accountable_contact_user_id`.
- **Future effective dates:** a case closure writes the receiver's assignment with `valid_period = [effective_at, ∞)` and caps the outgoing row's period at `effective_at` in the same transaction. Contiguous half-open ranges satisfy the exclusion constraint. Before the date, both are visible: one "current", one "scheduled". No job is needed.
- **Corrections of history:** a reason-required "correct history" action edits periods and writes change rows. Restricted to Admin/Continuity Manager.
- **Ending vs deleting:** never delete. Status is `active | cancelled` (cancelled = created in error). Cancelled rows are excluded from the constraint.

### Q-B — Evidence pool and privacy (resolves D2)

**Pipeline per case:**
1. **Discovery scope is asset-based, not person-based.** Discovery reads only sources linked to the case's responsibilities and assets, within the case date window. It never queries "everything the person authored" (avoiding the ServiceNow pattern of crawling a person's documents).
2. **Each candidate gets an audience.** The audience is computed from L5 (GitHub per-user visibility, Linear team membership, Notion mapping):
   - **visible to the whole case audience** (coordinator + receivers + approvers) → admitted as `case_all`.
   - **visible to the coordinator but not the receivers** → admitted as `coordinators`. The coordinator may *share* it to `case_all` (policy toggle, D2), which is audited.
   - **visible only to the outgoing owner** (or another single holder) → not admitted. It appears in that holder's inbox as "share into case?" with options *share / withhold / private*.
   - **visible to no participant** → not admitted. It is listed as "inaccessible source, ask an admin" (it appears only as a count and the source type, never a title, unless the title itself is visible).
3. **AI context assembly.** Case-level synthesis reads only `case_all` entries. Coordinator-only runs may read `coordinators` entries, and their outputs are tagged `coordinators`. The output audience is the narrowest audience among its inputs, checked by the validator.
4. **Statements** inherit their audience. Capsules and briefings render per viewer: entries outside the viewer's audience are hidden. If a statement is visible but its source isn't, the viewer gets an "access required" item and an access-request task.
5. **Consent lifecycle:**
   - Sharing is per entry, attributed and timestamped.
   - The holder can withdraw sharing until case closure. Withdrawal invalidates dependent proposals and statements that aren't yet human-verified.
   - Consent survives the holder's deactivation.
   - Emergency cases skip the holder's consent step: their non-shared items simply stay out.
6. **Revocation:** a source deletion or permission loss marks pool entries `withdrawn` (D22). Synthesis excludes them, and dependent unverified statements become "unsupported".
7. **Interview answers** are `relay_native` with an author-chosen audience (default `case_all`, with an option of "coordinator only").

**Tests (blocking):**
- Restricted-only content never appears in `case_all` outputs (canary strings planted in fixtures).
- Withdrawn entries are never in the context.
- Per-viewer capsule rendering matches the audience rules.

### Q-C — Domain architecture (entities that must not be duplicated)

```
Responsibility 1─* OwnershipAssignment *─1 (User|Team)
Responsibility *─* Asset            (responsibility_asset: stewards|uses)
Asset *─* SourceRecord              (asset_source: e.g. repo, Linear project, Notion page tree)
SourceRecord 1─* SourceRecordVersion 1─* Evidence (locator + optional excerpt)
KnowledgeItem ─ linked → SourceRecord (mode=linked) | native content (mode=native)
KnowledgeItem *─* Responsibility / Asset
Statement *─* Evidence ; Statement → subject (case item | responsibility | knowledge item)
ContinuityCase 1─* CaseScopeItem *─1 Responsibility
CaseScopeItem 1─* Task, ReadinessCriterion
ContinuityCase 1─* EvidencePoolEntry *─1 Evidence
Finding → subject (responsibility | asset | knowledge | case | connector), evidence[]
```

**Single sources of truth (never duplicate these):**
- **Owners** live only in `ownership_assignment`. Assets have no owner field; the case scope item references assignments.
- **Source content** lives only in `source_record_version`. Knowledge items link to it; evidence points into it. There are no copies in cases.
- **Claims** live only in `statement`. Findings, capsules and briefings reference statements; they don't restate them.
- **Tasks** live only in `task`. External tasks are a task with an `external_ref`, not a second entity.
- **People** live only in `user` + `membership`. External identities link to them; they never become separate "person" records.
- **Approvals** live only in `approval_request`. Consent is an approval kind, not a separate system.

### Q-D — Workflow engine (resolves D5)

**Can Postgres-backed workflows handle this? Yes.** The requirements map onto rows:

| Requirement | Mechanism |
|---|---|
| Long waits on humans | Case/item/task/approval rows with state. Nothing is "running" while waiting |
| Reminders & escalation | `reminder_schedule` rows with `due_at`, a periodic per-tenant job, and dedupe keys `(target, kind, sequence)` |
| Approvals | `approval_request` + content hash. Decisions emit outbox events that advance the workflow |
| Retries | Job-level retries with backoff. Steps are idempotent via `(instance, step, input_hash)` |
| Temporary assignments | Bounded `valid_period`. Expiry is automatic. A reminder N days before asks "extend?" |
| Crash recovery | Job leases + stalled-job retry. Steps are resumable from the last completed step |
| Versioning | Cases pin `playbook_version`. Transition functions are versioned code, and old versions are kept until no open case uses them |

**Conditions that would justify Temporal later** (any two together, sustained):
1. Workflows need **sub-minute timers at scale** (thousands per tenant) that strain the scheduler.
2. Multi-step **external sagas with compensation** across ≥3 systems become common (e.g. coordinated writes to Linear, GitHub and an HRIS with rollback).
3. We spend **more than ~20% of engineering time** on workflow-engine bugs, recovery tooling or versioning issues across two consecutive milestones.
4. A customer requirement for **workflow-history replay or audit** that our step logs can't satisfy.
5. A team grows beyond the founder and needs a standard durable-execution model.

### Q-E — Agentic architecture

The Blueprint §I.2 classification stands:
- **2 bounded LLM agents:** Interview and Scoped Ask.
- **About 9 single-shot LLM skills:** relevance classification, impact synthesis, plan additions, knowledge drafting, revision comparison, conflict check, section summaries, reviewer evidence summaries, responsibility grouping.
- **Everything else is deterministic Python:** the rules engine, discovery queries, impact queries, readiness evaluation, the briefing composer, the action executor and the Irreplaceable query.

**Flow:**
1. A deterministic step assembles **audience-filtered evidence**.
2. The skill returns **typed proposals** with evidence IDs.
3. The validator checks the schema, citations, URL allowlist and audience.
4. Proposals go to the proposal tray, where a human accepts, edits or rejects them.
5. Accepted proposals become domain records (`basis=ai_inferred`) or `action_request`s.
6. Each action needs an approval bound to its content hash.
7. The Action Executor re-authorises and executes with an idempotency key, writes a receipt, and emits events.

**Hard rules:**
- No LLM holds a write tool.
- No LLM changes any case/approval/verification/ownership state.
- No LLM output is ever `verified`.

### Q-F — Multi-tenancy (resolves D11, D26)

**Risks:**
1. A missing tenant filter in a raw SQL report.
2. `SET` without `LOCAL` leaking through the pool.
3. Background jobs running without a tenant context.
4. Cross-tenant references by ID in request bodies.
5. Vector or search queries missing the tenant predicate.
6. SSE fan-out to the wrong tenant.
7. Global unique constraints leaking existence.
8. A `BYPASSRLS` role used by mistake.

**Controls:**
- Tenant comes from the token and membership, never the client.
- `tenant_id` is a required argument on every repository method.
- RLS with `FORCE`, fail-closed `current_setting(…, true)`.
- Composite FKs.
- Per-tenant jobs (D26).
- `tenant_id` in every unique key.
- An SSE channel payload carrying only `(tenant_id, topic, id)`, checked against the subscriber's tenant.

**Testing (release-blocking):**
- **Generated route matrix:** for each route, seed tenants A and B, call as A with B's IDs, and expect 404 (not 403, to avoid confirming existence).
- **RLS canary:** a test connects as the app role *without* setting a tenant and asserts zero rows from every tenant table. Run it automatically over the full table list from the catalog.
- **Job isolation:** a job for tenant A cannot read B's rows.
- **Search and vector isolation** with overlapping external IDs (PRD AC-09).
- **Migration lint:** a CI script fails if any table with a `tenant_id` column lacks an enabled+forced RLS policy, or if any unique index omits `tenant_id`.

---

## Part 4 — Decisions requiring founder approval

| # | Decision | My recommendation | What I need from you |
|---|---|---|---|
| D2 | Coordinator sharing of restricted excerpts | ON for `internal`, OFF for `confidential`/`restricted` | Approve or adjust the policy |
| D4 | Departure playbook in v1 | Yes, manual | Yes/No |
| D7 | Auth vendor | WorkOS AuthKit | Approve vendor |
| D8 | Data region & platform | Region of the first design partners | Tell me the target customer geography |
| D10 | LLM provider and ZDR | Anthropic; request ZDR only if a pilot needs it | Approve; say whether early pilots are enterprise |
| D12 | Nav label | "Risks" | Approve |
| D13 | Retention defaults | As listed | Approve, pending legal |
| D14 | Responsibility records visible to all members | Yes, with a `restricted` flag | Approve |
| D22 | Evidence after deletion | Follow the source | Approve, pending legal |

## Part 5 — Remaining uncertainties

| # | Uncertainty | Resolve by | When |
|---|---|---|---|
| U1 | Linear app install visibility of private teams; exact scope names; team-membership change detection | S1 hands-on | Before M6 |
| U2 | GitHub App permission set for collaborator listing; exact webhook event names for membership changes | S1 hands-on + GitHub App permissions docs | Before M5 |
| U3 | Notion: error and latency after unsharing | S1 hands-on | Before M7 |
| U4 | Procrastinate stalled-job mechanism; coexistence with the SQLAlchemy session; test mode | S2 | Before M0 ends |
| U5 | PgQueuer feature set (docs fetch failed) | Only if S2 rejects Procrastinate | — |
| U6 | Managed Postgres offers PG17/18, `btree_gist`, pgvector ≥0.8 | Provider check | Before D8 |
| U7 | AuthKit with a separate Python API (token audience) | S6 | Before M0 |
| U8 | Anthropic subprocessors and ZDR process; vendor DPAs | S7 follow-up | Before the first real-data pilot |
| U9 | Customer appetite: Departure framing, Coverage frequency, readiness acceptance | Founder conversations (no user research exists yet) | Before M3/M4 scope freeze |
| U10 | Legal: DPDP/GDPR obligations, coordinator sharing, retention | Counsel | Before pilots |

---

## §R — Verified references (checked 8 Nov 2026 unless marked)

**Notion**
- Capabilities: https://developers.notion.com/reference/capabilities
- Webhooks: https://developers.notion.com/reference/webhooks
- Event types & delivery: https://developers.notion.com/reference/webhooks-events-delivery
- Request limits: https://developers.notion.com/reference/request-limits

**Linear**
- Rate limiting: https://linear.app/developers/rate-limiting
- Webhooks: https://linear.app/developers/webhooks
- OAuth actor authorization: https://linear.app/developers/oauth-actor-authorization

**GitHub**
- REST rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- Collaborators: https://docs.github.com/en/rest/collaborators/collaborators

**Libraries**
- Procrastinate: https://procrastinate.readthedocs.io/en/stable/
- PydanticAI: https://pydantic.dev/docs/ai/overview/
- pgvector README: https://github.com/pgvector/pgvector (fetched via GitHub API)

**Licences & release metadata:** GitHub REST API `repos/{owner}/{repo}`, `/license`, `/releases/latest`, `/tags` for each project in S7.

**Auth pricing**
- WorkOS: https://workos.com/pricing
- Clerk: https://clerk.com/pricing
- Auth0: https://auth0.com/pricing

**Anthropic**
- Data retention: https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data
- Commercial Terms: https://www.anthropic.com/legal/commercial-terms
- Embeddings (Voyage): https://platform.claude.com/docs/en/build-with-claude/embeddings

**[KNOWN], not re-fetched today:**
- PostgreSQL RLS: https://www.postgresql.org/docs/current/ddl-rowsecurity.html
- `set_config`: https://www.postgresql.org/docs/current/functions-admin.html
- Range types / exclusion constraints: https://www.postgresql.org/docs/current/rangetypes.html
- SQLAlchemy asyncio: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- psycopg 3 prepared statements: https://www.psycopg.org/psycopg3/docs/advanced/prepare.html
- GitHub webhook events: https://docs.github.com/en/webhooks/webhook-events-and-payloads
