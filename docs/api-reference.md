# Relay: API Reference, Technical Architecture, and External Services

This document is the complete technical reference for Relay's backend API, data
architecture, AI pipeline, external service integrations, and key library choices.

---

## 1. Architecture Overview

### Component Map

```
Browser (Next.js / React 19 — Vercel Edge)
  |  WorkOS AuthKit session cookie (httpOnly, Secure, SameSite=Lax)
  |  Server Actions call relayFetch() with Bearer token
  v
FastAPI 0.162 (Python 3.14 — Render Web Service)
  |  auth middleware: WorkOS JWT → membership → authorize()
  |  one SQLAlchemy async UoW per request; tenant set via SET LOCAL
  v
PostgreSQL 18 (Neon — AWS ap-southeast-1)
  |  Forced Row Level Security on all 84 tenant tables
  |  relay_app role: no superuser, no BYPASSRLS, no DELETE on audit
  |  relay_owner role: migrations only, never used by the app
  ^
  | transactional outbox (platform.outbox_event)
  |
Procrastinate 3.10 worker (Render Worker Service)
  |
  +-- GitHub App REST API v3 (read-only ingestion)
  |     github.com/apps/{slug}  — HMAC webhooks, JWT installation auth
  |
  +-- Linear GraphQL API (read-only ingestion)
  |     api.linear.app/graphql  — OAuth 2.0, encrypted token at rest
  |
  +-- Notion REST API (read-only ingestion)
  |     api.notion.com/v1       — OAuth, encrypted token at rest
  |
  +-- Google Gemini API  (AI — PydanticAI gateway, key rotation)
  |     generativelanguage.googleapis.com
  |
  +-- WorkOS API (email verification, invitations)
  |     api.workos.com
  |
  +-- Resend or SMTP (transactional email, optional)
```

### Modular Monolith Structure

Relay is a single deployable API and worker. Business logic is partitioned into 15 domain
packages under `backend/src/relay/`:

| Package | Responsibility |
|---|---|
| `identity` | WorkOS JWT verification, session, workspace membership, RBAC |
| `directory` | People, teams, departments, identity conflicts, profiles |
| `catalog` | Responsibilities, assignments, assets, ownership history, stewardship |
| `continuity` | Cases, tasks, readiness criteria, steps, decisions, capsules (lifecycle) |
| `risks` | 8 deterministic continuity risk rules, Continuity Debt score |
| `integrations` | Connector lifecycle, GitHub App, Linear OAuth, Notion OAuth |
| `intelligence` | Evidence pool, AI pipeline, deterministic analysis, capsules (AI) |
| `notifications` | In-app inbox, email preferences, delivery tracking |
| `automation` | Scheduled rules, follow-ups, governance policy |
| `insights` | Cross-workspace analytics and trend data |
| `search` | PostgreSQL full-text search across the workspace |
| `governance` | Policy tiers, workspace export, retention, ownership transfer |
| `audit` | Append-only audit log (written in same transaction as changes) |
| `imports` | Bulk import of people and responsibilities from CSV |
| `platform` | Workspace lifecycle, deletion, purge, health |

---

## 2. Authentication and Authorisation

### Authentication Flow

1. User authenticates via **WorkOS AuthKit** (hosted managed login).
2. WorkOS issues a short-lived RS256 JWT access token.
3. Frontend sends the token as `Authorization: Bearer <token>` on every API call.
4. `identity/auth.py` verifies the token against WorkOS's JWKS endpoint
   (`/sso/jwks/{client_id}`). JWKS keys are cached for 10 minutes (configurable).
5. The verified JWT `sub` is matched to a workspace `membership` record in the database.
6. The membership record provides the caller's role and workspace ID.

### Authorisation Model

Every request path has a role requirement enforced in the service layer via `authorize()`.
Roles in ascending privilege order:

| Role | Capabilities |
|---|---|
| `member` | Read own work, acknowledge capsules, answer interview questions |
| `manager` | Create cases, approve proposals, review evidence, manage responsibilities |
| `admin` | Integration management, exports, retention, policy configuration |
| `owner` | Workspace deletion, ownership transfer, all admin capabilities |

Row Level Security is enforced at the PostgreSQL level on all 84 tenant tables. The app
role (`relay_app`) has no `BYPASSRLS` privilege. Every query runs through RLS policies
that filter by `app.current_tenant_id`, which is set per-transaction via `SET LOCAL`.

### Key Configuration Variables

```
RELAY_WORKOS_CLIENT_ID       WorkOS application client ID
RELAY_WORKOS_API_KEY         Server-side key for email verification and invitations
RELAY_WORKOS_API_BASE_URL    Default: https://api.workos.com
```

---

## 3. API Endpoints

All endpoints are prefixed `/workspaces/{workspace_id}/` unless otherwise noted.
Pagination uses keyset cursors via the `X-Next-Cursor` response header; the JSON body
shape is unchanged (plain arrays). Pass `?after=<cursor>&limit=N` to page.

### 3.1 Directory API (`/people`, `/teams`, `/departments`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/people` | manager | List people. Filters: `q`, `department_id`, `include_archived`. Paginated. |
| `POST` | `/people` | admin | Create a person profile. |
| `PATCH` | `/people/{person_id}` | admin | Update name, email, department, title. |
| `GET` | `/people/{person_id}/profile` | manager | Full profile: responsibilities, teams, cases, evidence coverage. |
| `GET` | `/teams` | manager | List teams. Filters: `q`, `department_id`, `include_archived`. |
| `POST` | `/teams` | admin | Create a team. |
| `PATCH` | `/teams/{team_id}` | admin | Update team. |
| `PUT` | `/teams/{team_id}/members/{person_id}` | admin | Add member to team. |
| `DELETE` | `/teams/{team_id}/members/{person_id}` | admin | Remove member from team. |
| `GET` | `/teams/{team_id}/profile` | manager | Team profile with responsibilities and risk summary. |
| `GET` | `/departments` | manager | List departments. |
| `POST` | `/departments` | admin | Create department. |
| `PATCH` | `/departments/{department_id}` | admin | Update department. |
| `GET` | `/departments/{department_id}/profile` | admin | Department profile. |
| `GET` | `/identity-conflicts` | admin | Persons matched ambiguously across integrations. |

### 3.2 Catalog API (`/responsibilities`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/responsibilities` | member | List responsibilities. Filters: `q`, `criticality`, `status`, `category`, `department_id`, `type_id`, `has_backup`, `review`, `needs_verification`. Paginated. |
| `POST` | `/responsibilities` | manager | Create responsibility. |
| `GET` | `/responsibilities/{id}` | member | Detail view. `?as_of=<datetime>` returns the historical snapshot. |
| `PATCH` | `/responsibilities/{id}` | manager | Update fields (title, criticality, review interval, etc.). |
| `POST` | `/responsibilities/{id}/archive` | manager | Archive (soft delete). |
| `POST` | `/responsibilities/{id}/restore` | manager | Restore archived responsibility. |
| `POST` | `/responsibilities/{id}/assignments` | manager | Add an owner (role: `primary`, `backup`, `co_owner`). |
| `POST` | `/responsibilities/{id}/assignments/{aid}/end` | manager | End an assignment with a reason. |
| `POST` | `/responsibilities/{id}/primary` | manager | Replace the primary owner atomically. |
| `POST` | `/responsibilities/{id}/assignments/{aid}/correct` | admin | Correct a historical assignment record. |
| `GET` | `/responsibilities/{id}/history` | manager | Full ownership history. |
| `GET` | `/responsibilities/{id}/context` | manager | Evidence, cases, assets, and owners cross-referenced. |
| `GET` | `/responsibilities/{id}/stewardship` | manager | Dependencies, access grants, review status. |
| `POST` | `/responsibilities/{id}/dependencies` | manager | Add a dependency on another responsibility. |
| `DELETE` | `/responsibilities/{id}/dependencies/{did}` | manager | Remove dependency. |
| `POST` | `/responsibilities/{id}/access` | admin | Grant restricted access to a person. |
| `DELETE` | `/responsibilities/{id}/access/{user_id}` | admin | Revoke restricted access. |
| `POST` | `/responsibilities/{id}/review` | manager | Mark as reviewed. `?verified=true` upgrades to verified. |
| `GET` | `/responsibilities/types` | manager | List custom responsibility types. |
| `POST` | `/responsibilities/types` | admin | Create a responsibility type. |

### 3.3 Continuity (Cases) API (`/cases`)

**Case state machine:**
`draft` → `proposed` → `under_review` → `approved` → `active` → `completed`
Any state → `rejected` or `cancelled`

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/my-work` | member | Tasks, blockers, criteria, and cases assigned to the caller. |
| `GET` | `/cases` | member | List cases. Filters: `type`, `status`, `person_id`, `responsibility_id`, `emergency`. Paginated (descending by urgency/updated_at/id). |
| `POST` | `/cases` | manager | Create a departure/leave/role-change/coverage case. |
| `GET` | `/cases/{id}` | member | Full case detail with scope, tasks, criteria, and decisions. |
| `PATCH` | `/cases/{id}` | manager | Update case metadata. |
| `GET` | `/cases/{id}/history` | manager | Timeline of all state transitions. |
| `POST` | `/cases/{id}/submit` | manager | Submit for review (draft → proposed). |
| `POST` | `/cases/{id}/decisions` | manager | Record approval or rejection decision (proposed → approved/rejected). Predecessor cannot approve their own case. |
| `POST` | `/cases/{id}/execute` | manager | Activate execution (approved → active). |
| `POST` | `/cases/{id}/complete` | manager | Mark completed. Blocked until required criteria are met. |
| `POST` | `/cases/{id}/cancel` | manager | Cancel at any state. |
| `POST` | `/cases/{id}/extend` | manager | Extend a coverage case with a new end date. |
| `POST` | `/cases/{id}/activate` | manager | Move directly to active (shortcut for coverage cases). |
| `POST` | `/cases/{id}/fill-from-backups` | manager | Auto-add backup owners as scope items. |
| `POST` | `/cases/{id}/scope` | manager | Add a scope item (responsibility → new owner). |
| `PATCH` | `/cases/{id}/scope/{item_id}` | manager | Update scope item (recipient, exception note). |
| `DELETE` | `/cases/{id}/scope/{item_id}` | manager | Remove scope item. |
| `POST` | `/cases/{id}/tasks` | manager | Add a handover task. |
| `PATCH` | `/cases/{id}/tasks/{tid}` | manager | Update task (title, assignee, due date, status). |
| `GET` | `/cases/{id}/tasks/{tid}` | member | Task detail with messages and steps. |
| `POST` | `/cases/{id}/tasks/{tid}/change` | member | Change task status (todo/in_progress/done/blocked). |
| `POST` | `/cases/{id}/tasks/{tid}/messages` | member | Post a task message (triggers notification). |
| `POST` | `/cases/{id}/tasks/bulk` | manager | Accept or reject multiple AI-proposed tasks at once. |
| `POST` | `/cases/{id}/criteria` | manager | Add a readiness criterion. |
| `PATCH` | `/cases/{id}/criteria/{cid}` | manager | Update criterion. |
| `PATCH` | `/cases/{id}/criteria/{cid}/steps/{index}` | member | Record a step within a criterion (rehearsal check). |
| `GET` | `/cases/{id}/impact` | manager | Impact analysis: affected responsibilities and open work. |
| `GET` | `/cases/{id}/privacy` | manager | Per-item privacy decisions for the case scope. |
| `PUT` | `/cases/{id}/privacy` | manager | Configure case-level privacy settings. |
| `POST` | `/cover-requests` | member | Self-request cover (creates a coverage case with self as subject). |
| `GET` | `/saved-views` | member | List personal saved filters. |
| `POST` | `/saved-views` | member | Save a filter combination as a named view. |
| `DELETE` | `/saved-views/{view_id}` | member | Delete a saved view. |
| `GET` | `/review-inbox` | manager | Privacy review items pending a decision. |
| `POST` | `/review-items/{item_id}/decision` | manager | Approve or redact a privacy review item. |
| `GET` | `/external-targets` | manager | List configured write targets (GitHub, Linear). |
| `GET` | `/cases/{id}/tasks/{tid}/external` | manager | External actions (linked GitHub issues, Linear issues) for a task. |
| `POST` | `/cases/{id}/tasks/{tid}/external` | manager | Approve creation of an external issue for a task. |
| `POST` | `/external-actions/{aid}/retry` | manager | Retry a failed external action. |
| `POST` | `/external-actions/{aid}/check` | manager | Poll current status of an external action. |

### 3.4 Risks API (`/risks`, `/overview`)

The 8 deterministic risk rules run against PostgreSQL data with no AI call required.

| Rule | Trigger |
|---|---|
| `no_primary` | Responsibility has no active primary owner |
| `no_backup` | Critical/high responsibility has no backup owner |
| `no_knowledge` | Responsibility has zero knowledge items |
| `stale_knowledge` | One or more knowledge items overdue for review |
| `open_work_no_cover` | Open work items with no assigned cover |
| `single_person_dependency` | Only one person owns a critical asset |
| `no_recipient` | Active case scope item has no designated recipient |
| `conflict` | Two knowledge items for same responsibility have conflicting content |

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/risks` | manager | Compute active risks. `?status=active|accepted|all`. |
| `GET` | `/risks/resolved` | manager | Risks resolved by recent case activity. |
| `POST` | `/risks/decision` | manager | Accept a risk with a reason and optional expiry. |
| `POST` | `/risks/assign` | manager | Assign a risk to a person for action. |
| `POST` | `/risks/case` | manager | Open a case directly from a risk. |
| `GET` | `/overview` | member | Continuity Debt score, risk counts by severity, case status summary. p95 342 ms at 1,000 responsibilities. |

### 3.5 Intelligence (AI) API (`/ai`, `/cases/{id}/analysis`)

Rate limit: 20 AI runs per 10 minutes per workspace (token-bucket in PostgreSQL).

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/cases/{id}/analysis` | manager | Start a full AI analysis run (202 Accepted). Returns `RunView` with run ID and status. |
| `GET` | `/cases/{id}/analysis` | manager | Current analysis state: claims, proposals, run history. |
| `POST` | `/ai/runs/{run_id}/cancel` | manager | Cancel a running analysis. |
| `PATCH` | `/ai/claims/{claim_id}` | manager | Accept or dismiss an AI claim (204 No Content). |
| `POST` | `/ai/proposals/{proposal_id}/accept` | manager | Accept a proposal (optionally with edits); creates the task/criterion/knowledge item. |
| `POST` | `/ai/proposals/{proposal_id}/reject` | manager | Reject a proposal with a reason (204 No Content). |
| `GET` | `/ai` | admin | AI admin overview: enabled capabilities, run budget, cost to date. |
| `PATCH` | `/ai` | admin | Update AI settings (token budget, capabilities enabled). |
| `PATCH` | `/ai/capabilities/{name}` | admin | Enable or disable an individual capability. |
| `GET` | `/ai/runs` | admin | List all runs for the workspace. |
| `GET` | `/ai/runs/{run_id}` | admin | Run detail: steps, tokens, cost, tool calls, duration. |
| `POST` | `/cases/{id}/interview` | manager | Generate a knowledge interview (202 Accepted). |
| `GET` | `/cases/{id}/interview` | manager | Current interview: questions, answers, review status. |
| `PATCH` | `/ai/questions/{question_id}` | member | Record an answer to an interview question. |
| `POST` | `/ai/questions/{question_id}/review` | manager | Mark a question as reviewed. |
| `POST` | `/ai/questions/{question_id}/to-knowledge` | manager | Convert an answered question into a knowledge item. |
| `GET` | `/cases/{id}/capsules` | member | List context capsules for a case. |
| `POST` | `/cases/{id}/capsules` | manager | Generate a capsule for a recipient (202-ish; immediate if fast). |
| `GET` | `/ai/capsules/{id}` | member | View a capsule. `?version=N` returns a historic version. |
| `PATCH` | `/ai/capsules/{id}` | manager | Edit capsule content before approval. |
| `POST` | `/ai/capsules/{id}/approve` | manager | Approve a capsule version (required before recipient can acknowledge). |
| `POST` | `/ai/capsules/{id}/acknowledge` | member | Recipient acknowledges the approved capsule version. |
| `GET` | `/ai/capsules/{id}/versions` | manager | Full version history for a capsule. |

### 3.6 Integration APIs

#### Integrations Health (`/integrations`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/integrations/health` | admin | All connector statuses: last sync, error counts, paused state. |
| `POST` | `/integrations/{provider}/{ref}/pause` | admin | Pause a connector (no new syncs). |
| `POST` | `/integrations/{provider}/{ref}/resume` | admin | Resume a paused connector. |

#### GitHub Integration (`/integrations/github`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/integrations/github` | admin | Overview: installations, repositories, sync status. |
| `POST` | `/integrations/github/connect` | admin | Start GitHub App installation flow; returns redirect URL. |
| `POST` | `/integrations/github/complete` | — | OAuth callback (no session; identity from token). Rate-limited. |
| `POST` | `/integrations/github/installations/{ref}/sync` | admin | Trigger manual reconciliation sync. Rate-limited. |
| `POST` | `/integrations/github/installations/{ref}/disconnect` | admin | Disconnect and stamp `disconnected_at`; source records purged after 30 days. |
| `PATCH` | `/integrations/github/repositories/{id}` | admin | Select or deselect a repository for evidence ingestion. |
| `GET` | `/integrations/github/suggestions` | manager | Ownership suggestions derived from CODEOWNERS and PR activity. `?status=open|deferred|dismissed|approved|withdrawn`. |
| `POST` | `/integrations/github/suggestions/{id}/decision` | manager | Approve or dismiss a suggestion. |
| `POST` | `/integrations/github/suggestions/bulk` | manager | Bulk approve/dismiss suggestions. |
| `GET` | `/integrations/github/identities` | admin | GitHub contributor identities and their mapping status. |
| `POST` | `/integrations/github/identities/{id}/decision` | admin | Link, dismiss, or flag a contributor identity. |
| `GET` | `/integrations/github/teams` | admin | GitHub org teams and their Relay team links. |
| `POST` | `/integrations/github/teams/{id}/link` | admin | Link a GitHub team to a Relay team. |
| `GET` | `/integrations/github/signals` | manager | Ownership discrepancy signals (declared owner vs. actual contributor). |
| `POST` | `/integrations/github/webhook` | — | HMAC-authenticated inbound webhook (no user session). Returns `{"queued": N}`. |

#### Linear Integration (`/integrations/linear`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/integrations/linear` | admin | Overview: connections, projects, sync status, identity matches. |
| `POST` | `/integrations/linear/connect` | admin | Start Linear OAuth 2.0 flow. |
| `POST` | `/integrations/linear/complete` | — | OAuth callback. Rate-limited. |
| `POST` | `/integrations/linear/connections/{ref}/sync` | admin | Trigger a manual sync (202 No Content). |
| `POST` | `/integrations/linear/connections/{ref}/disconnect` | admin | Disconnect and stamp `disconnected_at`; source records purged after 30 days. |
| `POST` | `/integrations/linear/projects/{id}/link` | admin | Link a Linear project to a Relay responsibility. |
| `GET` | `/integrations/linear/identities` | admin | Linear contributor identities. `?review=true` for unmatched only. |
| `POST` | `/integrations/linear/identities/{id}/decision` | admin | Link, dismiss, or flag a Linear identity. |
| `GET` | `/integrations/linear/signals` | manager | Discrepancy signals: declared vs. actual active contributors over the 90-day window. |

#### Notion Integration (`/integrations/notion`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/integrations/notion` | admin | Overview: connections, sources, page hierarchy, sync status. |
| `POST` | `/integrations/notion/connect` | admin | Start Notion OAuth flow. |
| `POST` | `/integrations/notion/complete` | — | OAuth callback. Rate-limited. |
| `POST` | `/integrations/notion/connections/{ref}/sync` | admin | Manual sync (202). |
| `POST` | `/integrations/notion/connections/{ref}/disconnect` | admin | Disconnect and stamp `disconnected_at`; source records purged after 30 days. |
| `GET` | `/integrations/notion/sources/{id}/preview` | admin | Preview the content of a Notion page before mapping it. |
| `PUT` | `/integrations/notion/sources/{id}/mapping` | admin | Map a discovered page to a responsibility (fail-closed ingestion model). |

### 3.7 Additional APIs

#### Search (`/search`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/search` | member | Full-text search using PostgreSQL `tsvector`. Results include responsibilities, people, cases, and knowledge items ranked by ts_rank. |

#### Notifications (`/notifications`, `/email`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/notifications` | member | In-app inbox. `?unread_only=true`. |
| `POST` | `/notifications/read` | member | Mark notifications as read (body: `{ids: [uuid]}` or `{all: true}`). |
| `GET` | `/notifications/preferences` | member | Email preference settings per notification type. |
| `PUT` | `/notifications/preferences` | member | Update email preferences. |
| `GET` | `/email/status` | admin | Email provider health, last delivery, failure counts. |
| `POST` | `/email/deliveries/{id}/retry` | admin | Retry a failed email delivery. |
| `POST` | `/email/test` | admin | Send a test email (rate-limited: 5/10 min). |

#### Automation and Policy (`/automations`, `/policy`, `/follow-ups`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/automations` | admin | List configured automation rules (risk alerts, review reminders, blocker escalations). |
| `PATCH` | `/automations/{template}` | admin | Enable/disable or reconfigure a rule. |
| `POST` | `/automations/{template}/run` | admin | Run a rule immediately. |
| `POST` | `/automations/{template}/retry` | admin | Retry the last run. |
| `GET` | `/follow-ups` | member | Pending follow-up actions for the caller (or all, for managers). |
| `POST` | `/follow-ups/{id}/complete` | member | Mark a follow-up as complete. |
| `GET` | `/policy` | admin | Workspace continuity policy (review intervals, escalation rules). |
| `PATCH` | `/policy` | admin | Update policy. |
| `GET` | `/policy/tiers` | admin | Criticality tier configuration (critical/high/medium/low intervals). |
| `PUT` | `/policy/tiers/{criticality}` | admin | Update a tier's configuration. |

#### Governance and Export

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/export` | owner | Full workspace export as JSON (all responsibilities, cases, audit). |
| `GET` | `/audit/export.csv` | owner | Audit log export as CSV. |
| `POST` | `/retention/apply` | owner | Trigger data retention rules (source purge, stale record cleanup). |
| `POST` | `/ownership/transfer` | owner | Transfer workspace ownership to another member. |

#### Insights (`/insights`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/insights` | manager | Trend data: Continuity Debt over time, case throughput, evidence coverage rate. |
| `GET` | `/insights/coverage` | manager | Evidence coverage breakdown by department and criticality. |

#### Imports (`/imports`)

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/imports/people` | admin | Bulk import people from CSV. Returns import result with error rows. |
| `POST` | `/imports/responsibilities` | admin | Bulk import responsibilities from CSV. |

#### Platform and Health

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | — | Public health check: returns `{"ok": true}` when API and DB are reachable. |
| `GET` | `/health/ops` | ops token | Extended health: worker status, job queue depth, failing jobs. |

---

## 4. AI Pipeline

### Model and Provider Configuration

Relay uses **PydanticAI 2.66** as the structured output layer over raw model APIs.
The `Gateway` class in `intelligence/llm.py` implements the `LLMPort` protocol with:

- Provider chain: configured via `RELAY_LLM_PROVIDERS` (comma-separated: `gemini`,
  `groq`, `ollama`, `fake`).
- Gemini key rotation: up to 4 keys (`RELAY_GEMINI_KEY_1` through `_4`). When a key
  hits its quota, it cools down for 60 seconds and the next key is used. Auth failures
  cool down for 1 hour.
- Fallback: when every key on the primary provider is cooling down, the next provider in
  the chain is tried.
- Token budget enforcement: `UsageLimits(total_tokens_limit=N)` passed to every run.
  Exceeded budget raises `token_budget_exceeded`, not a provider error.
- Cost tracking: per-run USD cost computed from known price tables and stored in the
  `ai_run` record.

**Configured model (production):** `gemini-2.5-flash-lite`
**Price (per million tokens):** input \$0.10, output \$0.40

**Alternative models supported:**

| Model | Provider | Input $/M | Output $/M |
|---|---|---|---|
| `gemini-2.5-flash-lite` | Gemini (default) | \$0.10 | \$0.40 |
| `gemini-2.5-flash` | Gemini | \$0.30 | \$2.50 |
| `gemini-2.5-pro` | Gemini | \$1.25 | \$10.00 |
| `llama-3.3-70b-versatile` | Groq | \$0.59 | \$0.79 |
| Any Ollama model | Local Ollama | Configured manually | Configured manually |

Unknown models cost \$0 (reported, not enforced). Custom prices can be set via
`RELAY_LLM_PRICE_INPUT` and `RELAY_LLM_PRICE_OUTPUT` (Decimal per million tokens).

### AI Capabilities

The pipeline has 9 named capabilities (prompts in `intelligence/capabilities.py`).
Each gets the same evidence pool and two read-only tools. No write tools exist.

| Capability | Purpose | Output Type |
|---|---|---|
| `discovery` | Reconstruct current state: in-progress items, decisions, questions, open work | `AnalysisOutput` (claims + proposals) |
| `impact_analyst` | Find dependencies and conflicts between sources | `AnalysisOutput` |
| `knowledge_steward` | Identify missing or stale knowledge; propose knowledge drafts | `AnalysisOutput` |
| `handover_planner` | Propose concrete tasks, readiness criteria, and exceptions | `AnalysisOutput` |
| `continuity_monitor` | Identify single points of failure and silent gaps | `AnalysisOutput` |
| `readiness_verifier` | Verify whether evidence proves each readiness criterion is met | `AnalysisOutput` |
| `coordination` | Draft coordination messages to named people | `AnalysisOutput` |
| `knowledge_interviewer` | Generate targeted questions for the outgoing owner | `InterviewOutput` |
| `handover_generator` | Write the per-recipient context capsule with sections and cited points | `CapsuleOutput` |

**Read-only tools available to all capabilities:**
- `search_evidence(query: str)`: keyword search over the evidence pool (max 15 hits).
- `get_evidence(ref: str)`: retrieve full text of one evidence item by its ref (e.g. `E3`).

### Evidence Pool and Citation Pruning

Before any AI call, `intelligence/evidence.py` assembles a `Pool` of items from:
- Responsibilities in the case scope
- Knowledge items for each responsibility
- GitHub PRs, issues, commits, CODEOWNERS entries
- Linear issues and project data
- Notion pages mapped to responsibilities
- Prior claims and decisions in this case

Each item is assigned a short ref (`E1`, `E2`, ...) and rendered as an
`<evidence ref="E1">...</evidence>` tag in the prompt. The model must cite refs in every
claim or proposal it produces.

**Citation pruning (mathematical):** any proposal whose `evidence` list is empty is
silently discarded before being stored. Claims without refs are stored with
`confidence=low` and flagged for manager review.

### Safety Envelope

Every capability prompt begins with a `SAFETY` block that explicitly:
- Tells the model evidence is untrusted data, not instructions to follow.
- Prohibits inventing people, systems, dates, or refs.
- Requires citing only refs present in the pool.
- States the model cannot change anything.

Models operate with temperature 0 (via PydanticAI's structured output mode).
There are no write tools in the tool registry.

---

## 5. Background Job System

Relay uses **Procrastinate 3.10** as a transactional job queue backed by PostgreSQL.
Jobs are written to the `procrastinate_jobs` table in the same transaction as the domain
event that triggers them. If the transaction rolls back, the job never executes.

### Job Types (Serialisation Groups)

| Group | Serial Key | Purpose |
|---|---|---|
| `github-sync` | `"{tenant}:github-sync"` | GitHub reconciliation runs (one at a time per workspace) |
| `linear-sync` | `"{tenant}:linear-sync"` | Linear sync (one at a time per workspace) |
| `notion-sync` | `"{tenant}:notion-sync"` | Notion sync (one at a time per workspace) |
| `ai` | `"{tenant}:ai"` | AI analysis and capsule generation (serialised per workspace) |
| Notifications, reminders | None | Parallelisable; no lock needed |

### Correlation

Every job runs with a `REQUEST_ID` environment variable set to the hex of the event ID
that triggered it. Workers emit `"queued {event_type} event {event_id}"` log lines for
tracing.

### Scheduled Jobs (Cron)

| Job | Schedule | Purpose |
|---|---|---|
| `github_reconcile` | Every 6 hours | Recover missed GitHub webhook events |
| `review_reminder` | Daily | Email review-overdue responsibility owners |
| `blocker_escalation` | Hourly | Escalate overdue blockers to case leads |
| `purge_disconnected` | Daily | Purge source records 30 days after connector disconnect |
| `relay-purge-workspaces` | Via GitHub Actions | Permanently delete workspaces past the 30-day grace period |

---

## 6. External Services

### WorkOS AuthKit

**Purpose:** Managed authentication (login, MFA, SSO, invitation emails).
**How used:**
- Hosted login page, users never enter credentials on Relay's domain.
- RS256 JWT access tokens verified against WorkOS JWKS endpoint.
- Server-side API key used only for email verification and invitation acceptance.
- WorkOS never receives data about responsibilities, cases, or evidence.

**Configuration:**
```
RELAY_WORKOS_CLIENT_ID       Client ID for the AuthKit application
RELAY_WORKOS_API_KEY         Server-side key (email verification only)
```

**SDK:** `@workos-inc/authkit-nextjs ^4.6.3` (frontend), `pyjwt[crypto] >=2.15.1` (backend verification).

---

### GitHub App

**Purpose:** Read-only ingestion of repository metadata, ownership signals, and issue links.
**Integration type:** GitHub App (organisation installation).
**Permissions requested:**
- `contents: read` — repository file access for CODEOWNERS, Backstage descriptors.
- `metadata: read` — repository metadata, teams.
- `pull_requests: read` — PR authorship and review activity.
- `issues: read` — issue metadata for task linking.
- `issues: write` (optional, `RELAY_GITHUB_ISSUE_WRITES=true`) — create Relay task issues.
- Webhooks: `push`, `pull_request`, `issues`, `installation`.

**What is not ingested:** commit diffs, file source code, discussion bodies, secrets.

**Authentication:** GitHub App JWT (RS256 private key) for installation tokens; HMAC-SHA256
for inbound webhook verification.

**Rate limits:** GitHub REST API v3, 5,000 requests/hour per installation token. The 6-hour
reconciliation sweep is designed to stay within this budget for typical installations.

**Configuration:**
```
RELAY_GITHUB_APP_ID           Numeric App ID
RELAY_GITHUB_APP_SLUG         App slug for the installation URL
RELAY_GITHUB_CLIENT_ID        OAuth client ID
RELAY_GITHUB_CLIENT_SECRET    OAuth client secret
RELAY_GITHUB_PRIVATE_KEY      PEM-encoded RSA private key (App authentication)
RELAY_GITHUB_WEBHOOK_SECRET   HMAC secret for webhook signature verification
RELAY_GITHUB_ISSUE_WRITES     false (default); true enables task issue creation
```

---

### Linear (OAuth 2.0)

**Purpose:** Read-only ingestion of project, issue, and contributor data.
**Integration type:** Linear OAuth 2.0.
**Scopes requested:** `read` (default). `issues:create` required for write mode
(`RELAY_LINEAR_OAUTH_SCOPE=...` and reconnect).
**Contributor window:** 90-day rolling window for active assignees and commenters.

**Tokens at rest:** Linear OAuth tokens are encrypted using AES-GCM via a Fernet-compatible
key (`RELAY_INTEGRATION_ENCRYPTION_KEY`). Tokens are never logged.

**Discrepancy signals:** when the declared Relay primary owner of a responsibility differs
from the most active assignee or commenter over the 90-day window, a discrepancy signal
is emitted for manager review.

**Configuration:**
```
RELAY_LINEAR_CLIENT_ID         OAuth application client ID
RELAY_LINEAR_CLIENT_SECRET     OAuth application client secret
RELAY_LINEAR_OAUTH_SCOPE       Default: "read"
RELAY_INTEGRATION_ENCRYPTION_KEY  Fernet key for token encryption
```

---

### Notion (OAuth)

**Purpose:** Fail-closed read-only ingestion of runbooks and documentation pages.
**Integration type:** Notion public integration OAuth.
**Ingestion model:** Notion pages are **not** bulk-ingested. Relay discovers the workspace
page hierarchy, but only imports pages that an administrator has explicitly mapped to a
specific Relay responsibility. Unmapped pages are never read.

**Revision tracking:** each mapped page is tracked via its `last_edited_time` and a
SHA-256 hash of the extracted text content. When the hash changes, the evidence item
is flagged as "Changed since cited" on any active capsule that cites it.

**Tokens at rest:** encrypted using the same `RELAY_INTEGRATION_ENCRYPTION_KEY` as Linear.

**Configuration:**
```
RELAY_NOTION_CLIENT_ID         OAuth integration client ID
RELAY_NOTION_CLIENT_SECRET     OAuth integration client secret
RELAY_INTEGRATION_ENCRYPTION_KEY
```

---

### Google Gemini API

**Purpose:** Structured AI output for the 9 analysis capabilities.
**Access:** Direct REST via `pydantic-ai-slim[google]`; no Vertex AI or Google Cloud
project required (free tier or paid API key).
**Key rotation:** up to 4 keys to stay within per-key free-tier rate limits.
**Data:** evidence excerpts (not raw source code or full Notion pages) are sent in prompts.
Production deployments should use a paid API key with Google's enterprise zero-training
agreement for customer data privacy guarantees.

**Configuration:**
```
RELAY_GEMINI_KEY_1   through   RELAY_GEMINI_KEY_4
RELAY_GEMINI_MODEL             Default: gemini-2.5-flash-lite
RELAY_LLM_PROVIDERS            Default: gemini
RELAY_LLM_TIMEOUT_SECONDS      Default: 30
```

---

### Resend or SMTP

**Purpose:** Transactional email (invitation, task notification, blocker escalation, reminders).
**Default:** email is off when neither Resend nor SMTP is configured. In-app notifications
are unaffected.
**Resend:** REST API via `httpx`. Recommended for production on Render (Render free tier
blocks outbound SMTP).
**SMTP:** alternative; supports `starttls`, `ssl`, or `none` (local/test only).

**Configuration:**
```
RELAY_RESEND_API_KEY     Resend API key
RELAY_EMAIL_FROM         Sender address, e.g. "Relay <notifications@mail.example.com>"
RELAY_EMAIL_REPLY_TO     Optional reply-to address
RELAY_SMTP_HOST          SMTP host (takes precedence over Resend if set)
RELAY_SMTP_PORT          Default: 587
RELAY_SMTP_SECURITY      starttls | ssl | none
RELAY_SMTP_USERNAME
RELAY_SMTP_PASSWORD
```

---

### Neon PostgreSQL

**Purpose:** Primary datastore, job queue, rate limiter, audit log, and full-text search.
**Version:** PostgreSQL 18.6 (Neon serverless, AWS ap-southeast-1).
**Configuration:**
```
RELAY_DATABASE_URL         postgresql+psycopg:// URL for the app role
RELAY_MIGRATION_DATABASE_URL  postgresql+psycopg:// URL for the owner role (migrations only)
```

**Notable design decisions:**
- Forced RLS on all 84 tenant tables. App role cannot bypass RLS.
- Tenant ID set via `SET LOCAL app.current_tenant_id = '...'` per transaction.
- Procrastinate uses a `procrastinate_jobs` table (not a separate queue service).
- Rate limits use an atomic `SECURITY DEFINER` token-bucket function.
- Full-text search uses `tsvector` columns with GIN indexes (no Elasticsearch or vector DB).
- Audit log has an append-only grant and a trigger preventing UPDATE or DELETE.

---

## 7. Backend Libraries

| Library | Version | Purpose |
|---|---|---|
| `fastapi` | >=0.162.2 | Async HTTP API framework; dependency injection for auth and jobs |
| `uvicorn[standard]` | >=0.54.0 | ASGI server (Gunicorn + UvicornWorker in production) |
| `sqlalchemy[asyncio]` | >=2.1.8 | Async ORM with native PostgreSQL type support |
| `psycopg[binary]` | >=3.3.8 | Native async PostgreSQL driver (psycopg3) |
| `alembic` | >=1.20.1 | Database migrations (hand-written, 0001–0039) |
| `procrastinate` | ==3.10.0 | Transactional job queue backed by PostgreSQL |
| `pydantic-ai-slim[google,groq,openai]` | ==2.66.0 | Structured LLM output; provider abstraction; tool calling |
| `pydantic-settings` | >=2.16.2 | Environment-based configuration with validation |
| `pyjwt[crypto]` | >=2.15.1 | WorkOS JWT verification (RS256) |
| `httpx` | >=0.28.1 | Async HTTP client for GitHub, Linear, Notion, Resend, WorkOS APIs |
| `pyyaml` | >=6 | Automation rule configuration parsing |

---

## 8. Frontend Libraries

| Library | Version | Purpose |
|---|---|---|
| `next` | 16.4.5 | App Router, Server Components, Server Actions |
| `react` / `react-dom` | 19.3.0 | UI rendering |
| `@workos-inc/authkit-nextjs` | ^4.6.3 | WorkOS session management and auth middleware |
| `@workos-inc/node` | ^12.2.0 | Server-side WorkOS API calls |
| `@base-ui/react` | ^1.9.0 | Accessible, unstyled UI primitives |
| `tailwindcss` | ^4 | Utility-first CSS |
| `lucide-react` | ^1.70.0 | Icon set |
| `class-variance-authority` | ^0.7.1 | Typed component variant management |
| `shadcn` | ^4.23.0 | Component scaffolding on top of base-ui and tailwind |
| `@playwright/test` | 1.57.0 | End-to-end browser tests |

---

## 9. Frontend API Client

The frontend never calls the backend directly from the browser. All data fetching runs
in Server Components and Server Actions via `relayFetch()` in `lib/relay-api.ts`.

```typescript
// relayFetch: authenticated call from server context
relayFetch(path: string, options?: RequestInit): Promise<Response>

// relayPaged: handles X-Next-Cursor pagination
relayPaged<T>(path: string): Promise<T[] & { nextCursor?: string }>
```

The access token is retrieved from the WorkOS AuthKit server session, never from
`localStorage` or `document.cookie`.

The typed API client is generated from the FastAPI OpenAPI schema (available in development
at `http://localhost:8000/docs`; disabled in production via CSP and config).

---

## 10. Datasets

**No external or customer datasets are used.**

| Dataset | Purpose | Location |
|---|---|---|
| Demo workspace seed | Seed data for the "Northwind Labs" demo workspace | `backend/src/relay/demo/seed.py` (synthetic) |
| AI evaluation cases | 31 canonical test scenarios for CI thresholds | `backend/tests/intelligence/` (hand-authored) |
| Risk rule test cases | Seeded random walk tests for all 8 continuity rules | `backend/tests/test_case_state_properties.py` |

All test and demo data is entirely synthetic and contains no real personal information.

---

## 11. Important Technical Decisions

### ADR 0001: LLM Gateway with Provider Fallback

PydanticAI is used exclusively through a custom `LLMPort` interface (`intelligence/llm.py`).
This decouples model provider from business logic: provider, model name, and key index
are the only fields stored; prompts are never logged. Provider and key rotation happen
transparently to all callers. See `docs/adr/0001-llm-gateway.md`.

### ADR 0002: 6-Hour GitHub Reconciliation Interval

The reconciliation sweep interval is 6 hours (not the 15 minutes in the Round 1 plan).
Webhooks deliver events in real time; the sweep is a safety net. A 6-hour interval
stays within GitHub's 5,000 req/hr rate limit for typical multi-repo installations.
See `docs/adr/0002-github-reconciliation-interval.md`.

### No External Broker

Relay uses Procrastinate (PostgreSQL-backed) instead of Redis or RabbitMQ. This
eliminates split-brain risk between job state and database state: a job is enqueued
in the same transaction as the domain event. If the transaction rolls back, the job
does not exist. This also enables single-instance free hosting on Render without
additional services.

### Fail-Closed Notion Ingestion

Notion does not support restrictive per-page OAuth scopes. Rather than bulk-import
all accessible pages, Relay discovers the workspace hierarchy but only imports pages
that an administrator has explicitly mapped to a Relay responsibility. This prevents
accidental ingestion of internal HR, legal, or strategy documents.

### Keyset Pagination

All list endpoints use keyset (cursor-based) pagination rather than LIMIT/OFFSET.
The cursor is a base64-encoded JSON object encoding the last row's sort key columns.
It is returned in the `X-Next-Cursor` response header; the JSON response body is an
unchanged plain array. This keeps the API shape stable while enabling efficient
large-dataset pagination without counting.

### PostgreSQL Rate Limiting

Relay does not use an in-process rate limiter or Redis for rate limiting. Instead,
a `SECURITY DEFINER` function implements a token-bucket algorithm atomically in
PostgreSQL. This ensures rate limits are shared across all API workers and are durable
across restarts, with no additional infrastructure.

### Audit Log Integrity

The audit log table (`audit.event`) has:
- Append-only database grant: `relay_app` has `INSERT` only; no `UPDATE` or `DELETE`.
- A PostgreSQL trigger that rejects any attempt to update or delete existing rows.
- Audit events are written in the same transaction as the change they record.

This guarantees that any committed business operation has a corresponding, immutable
audit record, and that no application code path can silently rewrite history.
