# Relay architecture

Relay keeps work moving when people and responsibilities change. It holds the record of
who owns what. It rebuilds the context of that work from the tools a team already uses,
with every finding citing its source. It moves ownership through reviewed, audited
handovers.

Decisions are recorded in [blueprint/Relay_Architecture_Decision_Register.md](blueprint/Relay_Architecture_Decision_Register.md)
(D1–D26) and [adr/](adr/). This page describes the system as built.

## 1. System context

```
             ┌──────────── WorkOS AuthKit (identity only) ────────────┐
             │                                                         │
browser ──HTTPS──> Next.js 16 web ──server-to-server (user's token)──> FastAPI API ──┐
                   (server components,                                (thin routers, │
                    server actions; no                                 services,     │
                    business logic)                                    policy)       │
                        ▲                                                            ▼
GitHub webhooks ────────┘ proxied raw to API                       PostgreSQL 18 (RLS)
                                                                   ▲            ▲
GitHub · Linear · Notion APIs  <── read-only syncs ── Procrastinate worker ─────┘
Gemini / Groq / Ollama        <── AI runs (proposals only)        (outbox jobs, schedules)
Resend / SMTP                 <── email deliveries
```

- **One backend language.** Python holds every rule (guardrail 7). Next.js renders pages and forwards actions with the user's access token.
- **One database.** Tenancy, jobs, the audit log, search and AI artifacts all live in PostgreSQL. There is no Redis, broker, vector database or graph database (guardrail 8). Jobs use Procrastinate on Postgres, fed by a transactional outbox.
- **Deployable as one Compose stack** or as managed services. See [../deployment.md](../deployment.md).

## 2. Request path and the security boundary

1. **Identity.** `Identity` verifies the WorkOS access token against JWKS, issuer, audience, expiry and algorithm. Only the verified `sub` is used.
2. **Membership.** `CurrentWorkspace` resolves an *active* Relay membership for `(user, workspace_id)`. The tenant comes from that membership, never from the request body.
3. **Tenant context.** `unit_of_work(factory, tenant_id, principal)` opens one transaction and sets `app.tenant_id` and `app.principal` with `set_config(..., true)`, so the settings are transaction-local. Session-level `SET` is never used, so a pooled connection can't leak context.
4. **Authorization.** Every service calls `authorize(access, Permission.X)` and uses `visible()` for lists. Both come from the central registry `relay/policy/permissions.py`. Unknown roles and unknown permissions are denied. A denial names the roles that would be allowed.
5. **Database enforcement.**
   - Every tenant table has `tenant_id NOT NULL`, composite `(tenant_id, x_id)` foreign keys, and forced row-level security with a fail-closed policy.
   - The app connects as `relay_app`, which is not a superuser, has no `BYPASSRLS` and owns nothing.
   - Restricted responsibilities carry a second, *restrictive* policy, so a bug in a service still can't show them.
   - `tests/security/test_schema_conventions.py` enforces all of this on every table.
6. **Audit and events.** The change, its audit event and its outbox event commit together.
   - The audit log is append-only: there is no UPDATE or DELETE grant, and a trigger refuses both.
   - Audit metadata holds identifiers and enums only.

## 3. Modules (`backend/src/relay/`)

| Module | Responsibility |
|---|---|
| `platform` | Tenant boundary, workspace create/read, scheduled deletion and owner-role purge |
| `identity` | Token verification, users, memberships, invitations, workspace access |
| `policy` | Permission registry, roles, `authorize`/`visible` |
| `directory` | People, teams, departments, reporting lines |
| `catalog` | Responsibilities, ownership (primary, backup, co-owner) with append-only history, assets, knowledge (versions, stewards, disputes, validity, classification) |
| `continuity` | Cases (transfer, coverage, departure, onboarding, project handover) with an explicit state machine, approvals with separation of duties, tasks, blockers, readiness, external task actions, briefings |
| `risks` | Deterministic risk rules (no owner, no backup, overdue review, single point of failure…) with a lifecycle, assignees and linked cases |
| `intelligence` | Evidence pool, AI capabilities, claim validation, proposals, interviews, handover capsules, run engine |
| `integrations` | GitHub App, Linear and Notion connectors behind one contract (health, pause/resume, recorded runs) |
| `search` | Permission-aware full-text search across the record and connected work, plus "who to ask" |
| `insights` | Trend metrics with definitions, denominators and snapshots |
| `notifications` | In-app inbox, email deliveries with idempotency keys, preferences |
| `automation` | Scheduled checks (reviews, deadlines, coverage), workspace policy, retention |
| `governance` | Export (JSON, audit CSV), retention, ownership transfer, connector runs |
| `audit`, `jobs` | Append-only audit log; transactional outbox and Procrastinate worker |
| `shared` | DB session and context, errors, rate limiting, observability (correlation IDs, JSON logs, `/api/v1`) |

Modules talk to each other through service functions, never by reaching into another
module's tables from a router.

## 4. Key data flows

**Handover (core loop).**
1. A manager opens a case and scopes the responsibilities.
2. Relay checks for duplicate and overlapping cases.
3. The case generates tasks and readiness criteria.
4. *Analyse case* builds the evidence pool and runs deterministic rules, then any AI capabilities that are enabled.
5. The outputs are claims with citations and proposals. People accept, edit or reject each one.
6. A handover capsule is generated per recipient, approved by a second person, and acknowledged per version.
7. Ownership changes are applied through the case, so history stays append-only and is audited.

**Connector sync.**
1. A webhook or schedule emits an outbox event.
2. The worker runs the sync under the tenant's context as `relay_app`, through `connectors.recorded` (which honours pause and records the run).
3. Data lands as evidence and signals, and suggestions wait for review. Imports never overwrite ownership.
4. Missed webhooks are covered by periodic reconciliation.

**External write (opt-in).** A manager approves the *exact* issue content. The worker
creates it with an idempotency key, does find-before-create on retries, and records a
receipt.

## 5. Reliability

- **Outbox.** Events are written in the domain transaction. Handlers are idempotent and keyed by event. Stalled jobs are re-queued every 5 minutes.
- **Retries.** Retries are bounded. Transient provider errors (rate limits, 5xx) retry. Revocation and authentication errors are shown to people instead of being retried forever.
- **Shutdown.** The API drains in-flight requests. The worker finishes or cancels running jobs, and they stay in the outbox.
- **Request tracing.** Every request gets an `X-Request-ID`, echoed in responses and attached to every log line. Access logs record the route template, never concrete IDs or bodies.
- **Health.** `/health/live` checks the process; `/health/ready` checks the database.

## 6. API

- **Documentation.** Outside production, the API serves its OpenAPI schema at `/openapi.json` and interactive docs at `/docs`. Production exposes neither.
- **Versioning.** Every route is available under `/api/v1/...`. The unversioned paths serve the web app.
- **Conventions.**
  - Request bodies are `StrictInput`, so unknown fields are rejected.
  - Responses are `*View`, `*Summary` or `*Detail`.
  - Errors are `{code, message}`.
  - Timestamps are timezone-aware ISO 8601.
  - Ranges are half-open `[from, to)`.
  - Creating requests take an `Idempotency-Key` where a retry could duplicate work.
- **Rate limits.** Abuse-prone endpoints are rate-limited: workspace creation, invitations and acceptance, OAuth starts, syncs, imports, AI runs, automation runs and email tests or retries.

## 7. Inventory

**Backend** (Python 3.14):

| Package | Version | Use |
|---|---|---|
| FastAPI, Uvicorn, Pydantic | latest pinned in `uv.lock` | HTTP API and DTOs |
| SQLAlchemy 2 async, psycopg 3, Alembic | | ORM and core, driver, hand-written migrations |
| Procrastinate | 3.10.0 | Postgres-backed job queue |
| pydantic-ai-slim (google, groq, openai) | 2.66.0 | Model gateway (see [ai.md](ai.md)) |
| PyJWT[crypto], httpx, PyYAML | | Token verification, provider clients, `catalog-info.yaml` |

**Frontend:**

| Package | Version | Use |
|---|---|---|
| Next.js, React | 16.4.5, 19.3.0 | App Router, server components, server actions |
| WorkOS AuthKit for Next.js | ^4.6 | Sign-in session |
| Tailwind 4, shadcn/ui on Base UI, lucide-react | | UI |
| Playwright | | Public and signed-in end-to-end suites |

**AI models** (all configurable; none required):

| Provider | Default model | Notes |
|---|---|---|
| Google Gemini | `gemini-3.5-flash-lite` | Up to 4 keys rotated on quota errors |
| Groq | `llama-3.3-70b-versatile` | Fallback |
| Ollama | any local tool-capable model | Local and offline |

**Licences.** No GPL, AGPL, SSPL, BSL or SUL production dependencies. CI enforces this in the `licences` job, and every build gets an SBOM and an image vulnerability scan.

**Data model.** 35 hand-written migrations across these schemas: `platform`, `identity`, `directory`, `catalog`, `continuity`, `risks`, `intelligence`, `integrations`, `notifications`, `governance`, `audit` and `procrastinate` (vendored); the outbox lives in `platform`. A drift test keeps the ORM models identical to the migrations.

## 8. Testing

| Suite | What it proves |
|---|---|
| `backend/tests/security/` | Tenant isolation as the real `relay_app` role, RLS fail-closed, schema conventions, permissions, idempotency, webhooks, connectors, governance, deletion |
| `backend/tests/intelligence/` | Citation validation, injection inertness, audience narrowing (canary), kill switch, budgets, timeouts, key rotation, capsules |
| `frontend/e2e/public.spec.ts` | Public pages and unauthenticated redirects (CI) |
| `frontend/e2e/smoke.spec.ts` | Signed-in journeys against a production build |

All backend tests use real PostgreSQL (never SQLite), with migrations applied from scratch
on each run.
