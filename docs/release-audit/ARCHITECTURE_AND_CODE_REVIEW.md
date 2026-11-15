# Architecture and code review

Reviewed: `backend/src/relay` (≈190 modules, 36 migrations), `frontend/src`, `deploy/`,
CI. Findings cite code; "inference" marks judgement without a test.

## 1. Architecture

**Shape.** Modular monolith: FastAPI API + Procrastinate worker over one PostgreSQL 18,
Next.js 16 as a thin server-rendered client. Business rules live only in Python (no logic
in Next.js server actions beyond input shaping). This matches the Decision Register
(D5 queue on Postgres, D6 PydanticAI behind a port, D11 shared-schema tenancy with RLS) and
needs no Redis, broker or vector store. **Appropriate for the target scale.**

**Boundaries.** One package per domain; routers are thin; services hold `authorize()`.
Cross-module calls go through service functions (e.g. `risks.service.open_case_for_risk`
calls `continuity.service.create_case`), not other modules' tables, with one exception
class: read-only joins across schemas for views (e.g. capsules reading catalog). No import
cycles at module import time (`python -c "import relay.app"` clean).

**Agent orchestration.** PydanticAI is used only for typed model calls with read-only
tools; Relay owns run state (`agent_run`, step checkpoints via the outbox), evidence,
approvals and side effects. **LangGraph is not used, correctly**: D6 rejected it because
its checkpointing would duplicate the outbox-driven run engine. Nothing in the current
flows (linear step chains, one human gate per proposal) needs graph orchestration.

**Sources of truth.** Ownership = `catalog.ownership_assignment` (+ append-only change
log); case state = `continuity`; AI output = proposals until accepted. External systems
are evidence only. Clear.

## 2. Data integrity

| Area | Assessment |
|---|---|
| Tenancy | `tenant_id NOT NULL`, `UNIQUE (tenant_id, id)`, composite FKs, forced RLS — enforced by `test_schema_conventions.py` on every table |
| Impossible states | Ownership overlaps blocked by EXCLUDE constraints; one primary at a time; dismissal/acceptance need notes (CHECK); confidential knowledge must be managers-only (CHECK); capsule approval immutable |
| History | Ownership changes and audit append-only (grant + trigger); case status changes append-only (grant) |
| Concurrency | Row locks on cases and risk records under change; optimistic `version` on responsibility updates (PATCH requires it); idempotency keys on workspace creation, external writes, emails |
| Migrations | Hand-written, expand-first, drift-tested against models; round trip (downgrade to base → upgrade) on every test run |
| Deletion | Workspace purge is per-tenant, children first, in one transaction; audit deletion only allowed for tenants past their grace period |
| Pagination | **Fixed in this audit**: four main lists were silently capped at 500; now keyset-paged with `X-Next-Cursor` |

Remaining: a running case can be cancelled via `blocked` (C-05), and some secondary lists
(teams, members, knowledge overview) are capped rather than paged.

## 3. API

- Strict input models (unknown fields rejected), `{code, message}` errors, `/api/v1` alias,
  route-template access logs with request IDs.
- Every route is enumerated by `test_route_auth.py` (anonymous and forged-token rejection).
- Long work returns 202 + a reference (analysis, syncs, external actions).
- Production disables `/docs` and `/openapi.json` (fixed in this audit).

## 4. Frontend

- Server components fetch per request with the user's token; mutations are server actions
  that revalidate and refresh, so the UI never shows success the backend didn't commit
  (actions return the API error otherwise).
- Duplicate submits: `SubmitButton` disables while pending; creating endpoints are
  idempotent server-side where a retry could duplicate work.
- Destructive actions use a native `confirm()`; deletion requires typing the workspace name.
- Loading skeletons per route; error boundary shows an opaque reference.
- Permission-aware navigation hides admin items, but the API is the enforcement point.
- Gaps: no offline handling; native `confirm()` dialogs are not styled; no client-side
  form state persistence across a failed server action beyond the browser's own.

## 5. AI runtime

| Check | Result |
|---|---|
| Provider isolation | `LLMPort` + `Gateway`; provider chain; key rotation; failures mapped to codes without provider text |
| Tool allowlist | Two read-only tools over the run's own evidence pool (`registry.READ_ONLY_TOOLS`); test asserts read-only |
| Writes | Impossible from a model: no tool writes; proposals applied only by a person through normal services |
| Citations | Unknown IDs rejected; uncited dropped or marked insufficient; conflicts need ≥ 2 sources |
| Audience | Intersection of cited evidence; canary test proves managers-only content never reaches a member |
| Injection | Envelope + stripped tags + read-only tools; test proves injected instructions cause no action |
| Budgets | Per-run token limit, per-tenant monthly budget, timeout, cancellation, kill switch |
| AI knowledge | `origin='ai'` stays draft until a reviewer verifies it |
| Recording | Steps, tokens, cost, errors; **tool calls now recorded by name** (fixed) |
| Live behaviour (Gemini, 4 runs) | 8.3–8.8k tokens, 10–17 s model time; the validator rejects uncited claims (reasons now recorded per step); 0 uncited claims stored; conflicting runbooks flagged after the fix; key rotation observed (key 2 used once). Planner produced 0 proposals in the first runs because step briefs dropped evidence refs; **after the fix (3447f9c) it produced 2 cited proposals and skipped 1 duplicate of an existing case task** |

**Usefulness.** The analysis adds synthesis beyond a summary: it connected open tasks to
the leaver, flagged contradictory runbooks and missing escalation knowledge, and asked a
targeted question. Proposal generation now works but is modest (2 per run on the demo);
a labelled evaluation set (FR-AGENT-012) is still needed to measure and tune it.

## 6. Integrations

| Provider | Auth | Sync | Webhooks | Revocation | Verified with real account |
|---|---|---|---|---|---|
| GitHub App | Installation verified against installer; tokens minted per sync | Metadata, CODEOWNERS, PRs/issues since a date | HMAC, dedupe, order-safe, via web proxy | Reported; suggestions withdrawn; data purged 30 d after disconnect | App install/sync used during development; webhooks and writes verified only against the fake (incl. lost-response recovery) |
| Linear | OAuth, single-use hashed state, encrypted tokens, refresh | Incremental by `updatedAt`, self-scheduled reconcile | None (scheduled) | Revoked vs expired distinguished; purge 30 d | Not re-verified in this audit |
| Notion | OAuth, encrypted tokens | Mapped sources only, revision-hashed, unchanged pages skipped | None | Withdrawn pages drop out; purge 30 d (knowledge archived) | Not re-verified |
| WorkOS | AuthKit; API verifies JWT | — | — | Membership removal effective next request | **Yes** (Playwright smoke with a real account) |
| Email (Resend/SMTP) | API key | Idempotent deliveries, retry with same key | — | Removed members not emailed | Simulated only |

Bug fixed this cycle: `connectors.recorded` refreshed the connection before flushing, so
successful syncs were recorded as "queued" (`d5ab090`).

## 7. Performance (measured)

`backend/tests/perf/test_api_latency.py`, in-process against real PostgreSQL as
`relay_app`, dataset 250 people / 1,000 responsibilities / 60 cases, 30 rounds, laptop
(Windows 11, Docker Desktop Postgres 18). Excludes network, TLS and WorkOS.

| Endpoint | p50 | p95 |
|---|---|---|
| GET /responsibilities (500 rows) | 259 ms | 383 ms |
| GET /overview | 263 ms | 342 ms (was 866 ms) |
| GET /risks | 231 ms | 314 ms (was 793 ms) |
| GET /responsibilities/{id} | 26 ms | 30 ms |
| GET /people, /cases | 24–28 ms | 34 ms |
| GET /search | 60 ms | 71 ms |
| POST /people, POST knowledge | 21–33 ms | 23–36 ms |

Fix: risk reconciliation no longer upserts and row-locks every risk record on each read
(`13b8a02`). Estimates beyond this dataset (not measured): risks/overview grow linearly
with responsibilities, so ~5k responsibilities would approach 1–1.5 s and should move to
an incremental (event-driven) risk table.

## 8. Technical debt (prioritised)

1. Risk computation on read (fine to ~2–3k responsibilities; move to incremental beyond).
2. In-process rate limiter (blocks horizontal scaling).
3. Secondary lists capped instead of paged.
4. Missing AI evaluation set.
