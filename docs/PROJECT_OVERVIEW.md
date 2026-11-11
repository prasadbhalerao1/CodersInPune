# Relay: Project Overview

Relay makes accountability transferable, and proves the transfer happened.

When a key person leaves, goes on leave or changes role, the work they own is scattered across
people, tickets, repositories and documents. Relay keeps a live map of who owns what, finds
continuity gaps before they hurt, and runs each handover as an evidence-backed, approved and
audited case. AI drafts findings and proposals; people decide.

## 1. What Relay does

| Area | Capability |
|---|---|
| Organisation map | People, teams, departments, responsibilities, assets, primary/backup/co-owners with full ownership history |
| Continuity intelligence | Risks (no backup, single point of failure, stale knowledge, unowned work), Continuity Debt score, explainable rules |
| Evidence | GitHub (repos, CODEOWNERS, PRs, issues, teams), Linear (projects, issues), Notion (pages imported as knowledge) |
| Cases | Departure, leave, role change and coverage cases with scope, tasks, readiness criteria, approvals and execution |
| AI analysis | Findings, conflicts, missing evidence and questions, each citing evidence; proposals for tasks and readiness |
| Knowledge interview | Targeted questions for the outgoing owner, answers reviewed and turned into knowledge |
| Context capsule | Role-specific handover for the incoming owner, versioned, approved, then acknowledged |
| Operations | My Work, Inbox, email, automations, insights, global search, audit log, workspace export and deletion |

## 2. Architecture

```
Browser
  │  WorkOS AuthKit session (httpOnly cookie)
  ▼
Next.js 16 (Vercel)            server components + server actions, no business logic
  │  Bearer access token
  ▼
FastAPI (Python 3.14)          auth → membership → authorize() → service → audit
  │  one transaction per request, tenant set per transaction
  ▼
PostgreSQL 18 (Neon)           forced row-level security on every tenant table
  ▲  transactional outbox
  │
Procrastinate worker           syncs, AI steps, email, reminders, retention
  │
  ├─ GitHub App / Linear / Notion APIs (read-only ingestion)
  ├─ Gemini (via PydanticAI gateway, key rotation, fallbacks)
  └─ Email (Resend or SMTP)
```

Modular monolith: one deployable API and one worker, one database, 15 domain modules
(`identity`, `directory`, `catalog`, `continuity`, `risks`, `integrations`, `intelligence`,
`notifications`, `automation`, `insights`, `search`, `governance`, `audit`, `imports`,
`platform`). No Redis, broker or vector store: PostgreSQL carries the queue, rate limits,
search and isolation.

## 3. Data flow

**A request.** WorkOS token verified against JWKS, membership resolved from the database (never
from client input), permission checked inside the service, data read through a unit of work that
sets `app.tenant_id` for that transaction only. PostgreSQL RLS then filters every row. Writes and
their audit event commit together.

**A background job.** A service writes a domain event to `platform.outbox_event` in the same
transaction and defers a Procrastinate job on the same connection. The worker runs the handler
under that tenant as the restricted role. Handlers are idempotent; failures retry with backoff;
logs carry the event id as the correlation id.

**An integration sync.**
- **GitHub:** Installed via GitHub App (read-only). Ingests repository metadata, CODEOWNERS files, Backstage catalog descriptors, teams, pull requests, and issues (metadata only; never file source code, commit diffs, or discussion bodies). Inbound webhooks are authenticated via HMAC-SHA256, deduplicated in PostgreSQL, and dispatched through the outbox. A 6-hourly reconciliation job recovers missed events.
- **Linear:** Connected via OAuth 2.0 with tokens encrypted at rest. Ingests teams, projects, active cycles, and high/urgent priority issues. Features automated identity reconciliation, matching Linear contributors across a rolling 90-day window to Relay directory profiles, and emits discrepancy signals when declared responsibility owners differ from active issue assignees.
- **Notion:** Connected via OAuth with tokens encrypted at rest. Operates under a strict fail-closed model: Relay discovers page hierarchies, but only imports content explicitly mapped by an administrator to a specific responsibility. Each mapped page becomes a knowledge item tracking external URLs, edit timestamps, and cryptographic text revision hashes.
- **Audience boundaries:** Private GitHub repositories and Linear projects default to managers-only visibility. Widening access is an audited administrative decision. Unsharing, archiving, or disconnecting a connector withdraws active evidence and marks claims unsupported; source records are automatically purged 30 days after disconnection.

**An AI analysis.**
1. Context builder collects only evidence the requesting user may see, each item with source,
   revision, timestamp and audience, wrapped in an untrusted-content envelope.
2. Deterministic rules run first (no model needed): missing owners, missing knowledge, stale
   items, conflicting runbooks, overdue tasks.
3. Four model steps (Discovery, Impact, Knowledge Steward, Handover Planner), each persisted as a
   checkpoint.
4. Validator drops uncited claims, rejects invented references, requires two sources for a
   conflict and gives each output the narrowest audience of its evidence.
5. Proposals wait for a human. Accepting one goes through the normal services and audit.

## 4. Key technical decisions

| Decision | Choice | Why |
|---|---|---|
| Tenancy | Shared schema, `tenant_id` on every row, forced RLS, composite foreign keys | Isolation enforced by the database, not just code; tested as the real app role |
| Roles | `relay_app` (no superuser, no BYPASSRLS, owns nothing) and `relay_owner` (migrations) | A compromised API cannot change schema or delete audit history |
| Queue | Procrastinate on PostgreSQL with a transactional outbox | Exactly the jobs that committed; no extra infrastructure |
| AI runtime | PydanticAI behind our own `LLMPort`; Relay owns run state | Typed outputs, provider swap, no framework lock-in |
| AI authority | Models have read-only tools and produce proposals only | No model can change ownership, tasks or data |
| Source permissions | Each linked source has an audience; private repos and Linear projects start managers-only | Relay cannot read each person's GitHub or Linear access, so it never assumes it |
| Rate limits | Counters in PostgreSQL behind a SECURITY DEFINER function | Correct across any number of API replicas |
| Search | PostgreSQL full text | Fast enough at target scale; semantic search deferred until evals justify it |
| Migrations | Hand-written, expand/contract, drift-tested against models | RLS, grants and constraints are explicit and reviewed |
| Pagination | Keyset cursors in `X-Next-Cursor` | Stable under writes; JSON shape unchanged |

## 5. AI models and evaluation

| Item | Detail |
|---|---|
| Primary model | Google Gemini `gemini-3.5-flash-lite` through the Gemini API |
| Key rotation | Up to 4 keys; on quota errors the gateway moves to the next key, then the next provider |
| Fallbacks | Groq and Ollama (local) configurable; deterministic analysis always works without a model |
| Controls | Per-run token limit, monthly workspace budget, timeout, cancel, global kill switch, per-capability toggles |
| Recording | Provider, model, key index, tokens, cost, duration, tool calls and error codes per step; prompts never logged |

**Evaluation set** (`backend/tests/intelligence/eval_dataset.py`): 31 labelled synthetic cases in
12 categories: supported claims, unsupported claims, incorrect citations, conflicting runbooks,
stale knowledge, missing evidence, prompt injection, restricted sources, duplicate proposals,
conflicting ownership, partial connectors and human review. It runs in CI with scripted model
outputs (no paid calls); `RELAY_EVAL_LIVE=1` runs the same cases against the configured model.

| Metric (scripted run) | Result |
|---|---|
| Unsupported claims stored | 0 of 6 (all blocked) |
| Citation precision | 0.93 (the 2 misses are real-but-wrong citations, surfaced for human review) |
| Conflict detection | 100%, 0 false positives |
| Stale knowledge detection | 100% |
| Missing-evidence detection | 100% |
| Partial connector flagged | 2 of 2 |
| Duplicate proposals shown | 0 |
| Proposal usefulness | 0.84 |
| Restricted proposals blocked from posting | 3 of 3 |
| Prompt injection effect | None (no ownership or task change) |
| Permission leaks | 0 |

Earlier live runs on Gemini: four full analyses, 8 to 9k tokens each, 10 to 17 seconds of model
time, conflicting runbooks flagged, cited task proposals produced, key rotation observed.

## 6. APIs

REST under `/api/v1` (also served at `/`), JSON, `{code, message}` errors, strict input models
(unknown fields rejected), 202 + reference for long work, cursor pagination on large lists.

| Group | Examples |
|---|---|
| Workspaces and members | `POST /workspaces`, invitations, roles, export, scheduled deletion |
| Directory | `/people`, `/teams`, `/departments` |
| Catalog | `/responsibilities`, assignments, history, `/assets`, knowledge, context |
| Continuity | `/cases`, scope, tasks, readiness, approvals, execute, briefing |
| Risks and insights | `/risks`, `/overview`, `/insights` |
| AI | `/cases/{id}/analysis`, `/ai/proposals/{id}/accept`, interview, capsules, `/ai/runs` |
| Integrations | `/integrations/github`, `/linear`, `/notion`, webhooks, health |
| Notifications | `/inbox`, email preferences, delivery status |
| Operations | `/health/live`, `/health/ready`, `/health/ops` (token-protected aggregate counts) |

Every route is enumerated by a test that checks anonymous and forged-token requests are rejected.

## 7. Libraries, services and templates

**Backend:** FastAPI, Pydantic 2, SQLAlchemy 2 (async), psycopg 3, Alembic, Procrastinate,
PydanticAI (Google, Groq, OpenAI-compatible providers), httpx, PyJWT, cryptography, uv, Ruff,
mypy, pytest.

**Frontend:** Next.js 16 (App Router, server actions), React 19, TypeScript, Tailwind CSS,
shadcn/ui components, WorkOS AuthKit for Next.js, Playwright, pnpm.

**External services:**

| Service | Use |
|---|---|
| WorkOS AuthKit | Sign-in, sessions, SSO-ready |
| Neon | Managed PostgreSQL 18, point-in-time restore |
| Render | API with in-process worker (pilot), separate worker for production |
| Vercel | Next.js hosting |
| GitHub App | Repository, team, PR and issue metadata; webhooks; approved issue creation |
| Linear (OAuth) | Projects and issues; approved issue creation |
| Notion (OAuth) | Mapped pages imported as knowledge |
| Google Gemini API | Analysis, interview, planning and capsule drafting |
| Resend or SMTP | Email delivery with idempotency keys |
| GitHub Actions | CI, SBOM and licence scans, migrations, monitor, nightly backup with restore drill |

**Templates:** email templates in `backend/src/relay/notifications/email_templates.py`; UI built
on shadcn/ui primitives with a neutral palette where colour is used only for meaning.

**Datasets:** no external or customer datasets. Demo workspace and evaluation cases are
synthetic and generated in code (`backend/src/relay/demo/`, the eval dataset above).

## 8. Security and privacy

| Control | How |
|---|---|
| Tenant isolation | Forced RLS on all 84 tenant tables, verified on the production database |
| Least privilege | App role cannot alter schema, read rate-limit counters or delete audit events |
| Source permissions | Audience per source; widening is an admin decision written to the audit log |
| Audit | Append-only table (grant + trigger), written in the same transaction as the change |
| Secrets | Environment only; integration tokens encrypted with a dedicated key; never logged |
| AI safety | Read-only tools, untrusted-content envelope, citation validation, audience inheritance |
| Abuse | Shared rate limits, payload caps, per-tenant job serialisation, AI budgets |
| Data lifecycle | Workspace export; deletion with 30-day grace, purged by the owner role; source data purged 30 days after disconnect |
| Web | CSP, HSTS, frame denial, httpOnly session cookies; API docs disabled in production |

## 9. Operations

* **Monitoring:** GitHub Actions checks web, API, database and `/health/ops` every 10 minutes
  and opens one `incident` issue (emailed to the owner) until it recovers. Alerts: worker down,
  queue backlog, failing jobs or events, unhealthy connector, failing email, failing AI, AI
  budget exhausted.
* **Backups:** Neon point-in-time restore plus a nightly encrypted dump that is restored into a
  throwaway PostgreSQL 18 and checked (schema version, forced RLS, safe role flags).
* **Runbook:** `docs/runbooks/incident-response.md` maps every alert to a first action and
  covers database outage, failed migration, credential compromise and data leakage.

## 10. Quality evidence

| Check | Result |
|---|---|
| Backend tests (real PostgreSQL as the app role, migrations rebuilt each run) | 250+ passing |
| Static checks | Ruff and mypy clean (192 files); Prettier, ESLint and TypeScript clean |
| Browser tests | 18 Playwright tests on the production build with a real WorkOS account |
| Performance | p95 ≤ 383 ms on all reads at 1,000 responsibilities |
| AI evaluation | 31 cases, thresholds above enforced in CI |
| Production database | Roles verified, migrations 0001 to 0039 applied, isolation verified |

## 11. Committed Improvements for Round 3

Relay commits to three systemic, depth-oriented improvements for Round 3, solving hard engineering problems across core product capabilities:

1. **Continuous Verification and Live Source Drift Detection:**
   Transition Relay from periodic polling to an event-driven continuous verification system across GitHub, Linear, and Notion. Extends webhook intake and cryptographic revision hashing to automatically compare live source states against cited evidence. When code, tickets, or documentation change in connected systems, Relay dynamically flags affected knowledge and handovers with a "Changed since review" state, recalculates Continuity Debt, and surfaces targeted update proposals before stale context causes operational disruptions.

2. **Zero-Trust Permission Hardening and Multi-Source Access Lineage:**
   Implement strict access lineage across all multi-source evidence, AI summaries, and context capsules. Every derived finding, proposal, and interview response inherits the cryptographic intersection of permissions from its originating sources. When an integration is disconnected, a repository turns private, or access is revoked, dependent views and derived context are instantly withdrawn from non-manager views, guaranteeing zero unauthorized data exposure across cross-functional teams.

3. **Verifiable Operational Rehearsal and Evidence-Backed Readiness Verification:**
   Bridge the critical gap between passive documentation handover and demonstrable operational competence. Operationalize supervised rehearsal workflows directly linked to cited runbooks and tasks. The incoming owner executes structured operational drills (such as mock deployment dry-runs, access verification checks, and rollback procedures) under supervision, recording execution notes and test evidence. Completing these mandatory drills acts as an automated, audited gate before final ownership transfer can commit.

## 12. Repository map

```
backend/src/relay/      domain modules, one package each
backend/migrations/     hand-written migrations 0001 to 0039
backend/tests/          security, integration, AI evaluation, performance
frontend/src/           Next.js app, components, typed API client
deploy/                 Compose stack, role scripts, restore drill
docs/                   blueprint, ADRs, runbooks, release audit
.github/workflows/      CI, migrate, monitor, backup, purge
```
