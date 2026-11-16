# Relay

Relay keeps work moving when people and responsibilities change. It finds what someone
owns, rebuilds the context from GitHub, Linear and Notion with cited evidence, and moves
ownership through reviewed, audited handovers. AI only proposes; people decide.

## Start here

| | |
|---|---|
| **Live product** | <https://midnight-ciphers.cv> (the home page has one-click sign-in for judges) |
| **Final product document (PDF, 11 pages)** | [Documentation/Relay_Final_Product.pdf](Documentation/Relay_Final_Product.pdf): the three improvements, everything beyond them, architecture, design decisions, testing and roadmap |
| **Complete reference (PDF)** | [Documentation/Relay_Complete_Documentation.pdf](Documentation/Relay_Complete_Documentation.pdf): the specification, every API endpoint and data model, decision records, the product guide and every screen |
| **Product video** | [Documentation/video/Relay_Walkthrough.mp4](Documentation/video/Relay_Walkthrough.mp4) (recorded during Round 3 development; a final cut follows) |
| **Ten-minute walkthrough** | [For judges](#for-judges), below |
| **Judge guide** | [judge-guide.md](Documentation/1-start-here/judge-guide.md): the problem, the lifecycle and an evidence matrix |
| **All documentation** | [Documentation/](Documentation/README.md) |
| **How we got here** | [devDocs/](devDocs/README.md): Round 1 and Round 2 submissions, research, audits and design notes |

> **Relay is a production SaaS, not a mock-up.** It signs real users in (WorkOS), connects to
> real GitHub, Linear, Notion and Slack accounts, and runs on a real Postgres database with
> row-level security. The pre-seeded Northwind sample exists only so judges don't have to
> connect their own tools, and so every edge case (a leaver, a stale runbook, a conflict, a
> blocked handover) is there to see on day one. Everything you do in it works the same way in a
> workspace you create yourself.

## For judges

**Live product:** <https://midnight-ciphers.cv> · **No setup needed.** Every step
below starts from that link and only uses buttons you can see. Allow about ten minutes.

> The API runs on a free server that sleeps when idle: the first page after a quiet period
> can take up to a minute. After that it is fast.

### 1. Get in (1 minute)

1. Open <https://midnight-ciphers.cv> and click **Go to your workspaces**.
2. Sign in with any email address. WorkOS emails you a one-time code; Relay never sees a
   password.
3. On **Workspaces**, click **Create sample workspace**. In a few seconds you are inside
   *Northwind Labs (sample)*: eight fictional people, seven responsibilities, a year of
   GitHub, Linear and Notion history, and an engineer, Arjun, who is leaving.

**Sample accounts (one per role):** the home page shows **Judges: sign in instantly**. Click
**Sign in as Owner** for one-click sign-in, or open the other roles; every email has a copy
button. All eight are real WorkOS accounts and members of the same *Northwind Labs (judges)*
sample. Password for all: `relay-password@987`. The sample is shared by every judge; for a
private clean copy, click **Fresh sample** on the workspace overview.

| Role | Email | Best for |
|---|---|---|
| **Owner** (start here) | `demo-owner@example.com` | Everything, plus *Try Relay as…* to switch roles |
| Continuity manager (Tom Okafor) | `demo-continuity@example.com` | Running the handover: cases, Autopilot, approvals, What If? |
| Member (Priya Nair) | `demo-member@example.com` | Receiving the brief, the exit interview, Ask Relay |
| Auditor (Riya Desai) | `demo-auditor@example.com` | Reading everything incl. the audit log, changing nothing |
| Admin (Maya Chen) | `demo-admin@example.com` | Members, integrations, policies, AI settings |
| Knowledge steward (Ines Duarte) | `demo-steward@example.com` | Verifying knowledge, settling disputes |
| Team manager (Dev Patel) | `demo-teamlead@example.com` | The incoming owner: *Accept ownership* of Arjun's handover; manages only their team's work |
| Guest (Kai Nakamura) | `demo-guest@example.com` | An outside contractor's read-only view |

Prefer your own? Sign in with any email (WorkOS sends a one-time code), click **Create sample
workspace** for a private copy, or create an empty workspace and connect your real GitHub,
Linear, Notion and Slack in **Integrations**. Same product, same code paths.

**Try every role:** the sample has a person in each of the eight roles: Maya (admin), Tom
(continuity manager), Ines (knowledge steward), Dev (team manager), Priya (member), Riya
(auditor), Kai (guest), and you (owner). The banner at the top has **Try Relay as…**, which
switches *your own* role in the sample, so you see exactly what that role can and can't do.
**Switch back to Owner** at any time. Settings → Roles explains why each role exists.

| Can they… | Owner | Admin | Continuity mgr | Knowledge steward | Team mgr | Member | Auditor | Guest |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| See the workspace, people, responsibilities and cases | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Read AI output: briefs, Autopilot results, Ask Relay | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Comment on cases | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Write knowledge: runbooks and decisions | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Verify knowledge and settle disputes | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Manage responsibilities | ✅ | ✅ | ✅ | ❌ | 🟡 own teams | ❌ | ❌ | ❌ |
| Open and run handover cases | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Approve handovers and sign off readiness | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Run AI (Autopilot, analysis) and review its proposals | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Run the What If? simulator | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| See insights: health and continuity debt | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Read the audit log | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Manage members, invites and integrations | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Change policies and automations | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Delete the workspace | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

Enforced in every backend service and by database row-level security, not just hidden in the
UI. The same table is on [/docs#roles](https://midnight-ciphers.cv/docs#roles),
checked against the permission registry by a test.

**Look for:** the Overview leads with *A handover is waiting for you*, a continuity-health
ring, a setup checklist with the next useful tour, and the gaps that would hurt if someone
left tomorrow. New to Relay? Click **Take the tour**, or open **Learn Relay** in the sidebar
for every tutorial. Tours can be skipped, resumed and replayed; guidance can be switched off.

### 2. Understand the past: Project Memory Replay (3 minutes)

1. In the sidebar, click **Responsibilities**, then **Production deployments**.
2. Click **Memory replay** (top right).
3. Press **Replay history** and watch the project evolve event by event; use the category
   chips to filter (try **Incident**), or narrow it with **From / To** dates.
4. Click **Explain this history**. The AI groups events into chapters on the time axis.
5. Click **Inspect** on any event, then ask *"Why does every payments-api deploy need a
   canary?"* under **Ask about this history**.

**Look for:** every event is a **Fact** with its source; chapters are labelled
**Inferred** and cite the events they rest on; the answer cites the outage and the decision.

### 3. Simulate the future: What If? (2 minutes)

1. Click **People & Teams**, then **Arjun Rao**, then **What if Arjun is unavailable?**
2. Set **is unavailable for** to *2 weeks* and click **Run simulation**.
3. Open **Why it is affected** under *Production deployments*.
4. Scroll to **Who could cover?**: each candidate is simulated and compared with nobody
   stepping in; anyone who would carry far more than the team's typical load is flagged
   *Would be overloaded*. Click **Simulate with Dev**.
5. Click **Plan a real handover**: the case form opens with Arjun already selected. Starting
   a real case is a separate, audited step.

**Look for:** deployments are left with nobody, readiness is 55/100, one task falls due
while he is away; Dev (the planned recipient) closes the gap and readiness rises. A banner
confirms nothing in the workspace was changed.

### 4. Execute a safer handover: Handover Copilot (3 minutes)

1. Go back to **Overview** and click **Open handover**.
2. Check the **evidence strength** under the summary (Strong, Partial or Weak, with the
   counts behind it) and **Brief coverage**: which responsibilities have cited evidence and
   which critical ones still need an answer from the current owner. **Who to ask** lists the
   current holders, backups and previous owners from the ownership records. Read the brief: *What you now own*, *Knowledge gaps and open questions*, *Risks and
   conflicts*, *Recommended first steps*. Expand any **sources** link to see the evidence.
3. In **Ask about this handover**, ask *"How should I deploy payments-api?"*, then ask
   something the evidence cannot answer, such as *"What is the AWS root password recovery
   process?"*
   Under the answer, **Worth asking next** suggests follow-ups from the brief's own gaps.
4. Under **Versions**, click **Compare** on an earlier version to see what changed.
5. Click **Open memory replay** under *Where this work came from*, then come back and click
   **Acknowledge receipt**.

**Then close the loop:** the incoming owner clicks **Accept ownership** on the case. A case
can't be completed while tasks are open, a required readiness check is unmet, or an incoming
owner hasn't accepted; the case header lists exactly what it is waiting on.

**Look for:** the answer cites its sources and points out the conflicting old runbook; the
second question gets *Not in the evidence* instead of an invented answer. After you
acknowledge, the brief shows **your next steps**: your open tasks, what you are taking over
(each with its history), the case status and where to ask. If the AI draft is slow or
fails, the page says so and offers a retry; the rule-based brief is always usable.

### 5. Beyond the three (5 minutes)

On the same sample workspace:

- **Handover Autopilot:** open Arjun's case → **Analysis** → **Run Autopilot**. Each tool call
  streams in, and it ends with proposals for you to accept.
- **Meetings:** open *Arjun handover kickoff*. Every decision, action, question and risk links
  to its transcript line. Accepting a decision creates an ADR; accepting an action creates a case task.
- **Ask Relay:** ask "What did we decide about webhooks?". The answer cites records you can open.
- **Decision log**, **Expertise map** (named vs capable backups) and the case's **30/60/90 plan**.
- **Knowledge:** "Code changed since review" flags the old deploy runbook from merged pull requests.
- **Slack:** Integrations → Slack, then **Post to #channel** on a meeting.

### 6. Optional

- **Your own data:** create an empty workspace and open **Integrations** to connect GitHub,
  Linear or Notion (read-only).
- **The code:** [improvements-delivered.md](Documentation/2-round3-improvements/2-what-we-delivered.md)
  maps every Round 3 commitment to its code and tests;
  [demo-script.md](devDocs/7-demo-and-early-builds/demo-script.md) is the full scripted demo.
- **Run it locally:** see [Run it yourself](#run-it-yourself): two commands after a free
  WorkOS sign-up.

## Run it yourself

You need [Docker](https://docs.docker.com/get-docker/), [uv](https://docs.astral.sh/uv/),
Node.js 22+ and pnpm 10 (`corepack enable`). Relay never handles passwords, so sign-in goes
through [WorkOS](https://workos.com), which is free for development:

1. Create a WorkOS account and open the **Staging** environment.
2. Under **Authentication**, enable **AuthKit** (email code sign-in is enough).
3. Under **Redirects**, set the redirect URI to `http://localhost:3000/callback`, the
   initiate-login URI to `http://localhost:3000/sign-in` and the sign-out redirect to
   `http://localhost:3000/`.
4. Under **API keys**, copy the **client ID** and the **API key**.

Then, from the repository root:

```bash
python scripts/setup.py   # asks for the two WorkOS values (and an optional Gemini key),
                          # writes the env files, starts PostgreSQL, installs, migrates
python scripts/dev.py     # runs the API and the web app; Ctrl+C stops both
```

Open <http://localhost:3000>, sign in with any email (WorkOS sends a code), go to your
workspaces and click **Create sample workspace**.

- **AI features** (Handover Copilot answers, Memory Replay narratives, case analysis) need a
  model key. A free [Gemini API key](https://aistudio.google.com/apikey) works; give it to
  the setup script or set `RELAY_LLM_PROVIDERS=gemini` and `RELAY_GEMINI_KEY_1` in
  `backend/.env`. Without one, Relay says AI is not configured and everything else works:
  the simulator, timelines and rule-based analysis are deterministic.
- **GitHub, Linear and Notion** are optional and need your own app credentials (below).
- The setup script is safe to re-run: it keeps values you already set.

## Scope and next steps

**What Relay covers today:** accountability for any kind of work, evidence from GitHub,
Linear and Notion (read-only), rule-based risks, the What If? simulator, AI-assisted
analysis, briefs, interviews, meetings and answers that always cite their sources, audited
handover cases with follow-through, Slack sharing, eight roles, and a full audit trail.

Each next step, with the point at which it becomes worth building:
[scope and next steps](Documentation/7-roadmap/scope-and-next-steps.md).

**Deliberate choices:**
- AI proposes; people decide. No model can change ownership, approve or edit a source.
- Connectors read only. Relay never writes to GitHub, Linear or Notion.
- Ask Relay retrieves with permission-aware search; semantic retrieval is planned behind a
  measured trigger ([ADR 0003](Documentation/3-architecture/decisions/0003-ask-relay-retrieval.md)).
- Customers sign in with their own WorkOS identity (email code, password or SSO). The only
  shared password belongs to the sample role accounts, which reach nothing but the sample
  organisation; any judge can also make a private sample and switch roles with *Try Relay as*.

## Roadmap

1. **Next:** repository- and asset-level Memory Replay; side-by-side brief diffs at sentence
   level. (Nightly encrypted backups with an automatic restore drill, under a read-only backup
   role, already run.)
2. **Soon:** calendar and HR-system signals (planned leave feeding the simulator
   automatically); Slack threads and Jira issues as evidence (Slack posting ships today);
   semantic retrieval for Ask Relay on the pgvector extension already installed; Linear and
   Notion webhooks, and for Notion the sync checkpoint GitHub and Linear already use; saved multi-person What If?
   scenarios; scheduled continuity reviews per team.
3. **Later:** organisation-wide resilience trends; SCIM provisioning; self-hosted model
   support for regulated customers.

## Team and contributions

Team **Midnight Ciphers** (CodersInPune Hackathon, Round 3 finalist).

| Member | Contribution |
|---|---|
| Prasad Bhalerao | Backend and trust: API, tenancy and row-level security, permissions, audit, continuity cases, the What If? simulator, deployment |
| Aayush Deshpande | Integration and intelligence: GitHub, Linear and Notion connectors, the evidence pipeline, Handover Copilot and Memory Replay AI |
| Vipul Nanaware | Product and experience: user journeys, interface and brand, onboarding and tutorials, testing with users, presentation |

AI coding assistants were used throughout; how AI is used inside the product is disclosed
in [Documentation/ai.md](Documentation/3-architecture/ai-design.md).

## Documentation

The repository has two documentation folders:

- **[Documentation/](Documentation/README.md)**: the final product documentation. Start here.
- **[devDocs/](devDocs/README.md)**: how Relay was built: the Round 1 and Round 2 submissions,
  the original blueprint and decisions, research, release audits and design notes.

| Folder | What's in it |
|---|---|
| [Relay_Final_Product.pdf](Documentation/Relay_Final_Product.pdf) | The 11-page final product document |
| [Relay_Complete_Documentation.pdf](Documentation/Relay_Complete_Documentation.pdf) | The complete reference, including the full API reference |
| [1-start-here](Documentation/1-start-here/) | Judge guide, project overview, competitive analysis |
| [2-round3-improvements](Documentation/2-round3-improvements/) | What we committed in Round 2, what we delivered, feature matrix, traceability |
| [3-architecture](Documentation/3-architecture/) | Architecture, AI design, trust and privacy, SSO, decision records |
| [4-api](Documentation/4-api/) | API reference and the OpenAPI schema (255 operations) |
| [5-testing-and-quality](Documentation/5-testing-and-quality/) | Test report, testing notes, security, performance |
| [6-operations](Documentation/6-operations/) | Deployment, environment setup, incident response |
| [7-roadmap](Documentation/7-roadmap/) | Roadmap, scope and next steps |
| [Specification (SRS and PRD v3.0)](devDocs/1-round1-submission/relay_srs_prd.md) | Requirements, updated to match the built product |

Conventions for contributors: `CLAUDE.md`.

## Deploying

See [deployment.md](Documentation/6-operations/deployment.md) for the managed path (Vercel, Render and Neon, with a
Render Blueprint). The single-host Docker Compose stack is covered in
[deploy/README.md](deploy/README.md), with the variable reference in
[deploy/.env.production.example](deploy/.env.production.example).

## Prerequisites

Docker (with Compose), [uv](https://docs.astral.sh/uv/), Node.js 22+ and pnpm 10.

## Local development

```bash
# 1. Database (Postgres 18 + pgvector). The first start creates relay_owner/relay_app
#    roles and the relay + relay_test databases (infra/db/init/01-roles.sql).
docker compose up -d --wait

# 2. Backend API
cd backend
cp .env.example .env
uv sync
uv run alembic upgrade head        # runs as the owner role
uv run relay-api                   # http://127.0.0.1:8000/health/live and /health/ready
uv run relay-worker                # background jobs (separate terminal)

# 3. Frontend (separate terminal)
cd frontend
pnpm install
pnpm dev                           # http://localhost:3000
```

## WorkOS setup (development)

Relay uses WorkOS AuthKit only to establish identity. Workspaces, memberships and roles
live in Relay; signing in grants access to nothing until a membership exists.

1. In the [WorkOS dashboard](https://dashboard.workos.com), use the **Staging** environment
   and enable AuthKit (User Management).
2. Under **Redirects**, set:
   - Redirect URI: `http://localhost:3000/callback`
   - Initiate login URI: `http://localhost:3000/sign-in`
   - Sign-out redirect (default): `http://localhost:3000/`
3. Under **Sessions**, keep the access-token duration short (the API verifies it per request).
4. Copy the client ID and API key into `frontend/.env.local` (from `frontend/.env.example`),
   generate `WORKOS_COOKIE_PASSWORD` (`openssl rand -base64 32`), and set
   `WORKOS_ISSUER=https://api.workos.com/user_management/<client_id>`.
5. Set `RELAY_WORKOS_CLIENT_ID=<client_id>` and `RELAY_WORKOS_API_KEY=<api_key>` in
   `backend/.env`. The API key is used server-side to read verified emails and send
   workspace invitations; without it, invitations return 503.
6. Confirm the token parameters the API enforces:
   - `curl https://api.workos.com/user_management/<client_id>/.well-known/openid-configuration`
     → `issuer` must equal the value above.
   - `curl https://api.workos.com/sso/jwks/<client_id>` → keys should have `"alg": "RS256"`.
     If not, set `RELAY_JWT_ALGORITHMS` accordingly.

Manual end-to-end check (not covered by automated tests, which use locally generated keys):
sign in at `http://localhost:3000` → create a workspace → open it → sign out → confirm
`/workspaces` redirects to sign-in.

## GitHub App setup (optional)

Relay reads repository metadata, `CODEOWNERS`, `catalog-info.yaml` and maintainers. It never
reads source code and stores no GitHub tokens: installation tokens are minted per sync.

1. Create a GitHub App (personal account or organisation → Settings → Developer settings →
   GitHub Apps → New):
   - Callback URL: `http://localhost:3000/integrations/github/callback`
   - Enable **Request user authorization (OAuth) during installation** (Relay verifies the
     installer owns the installation; the `installation_id` alone is not trusted).
   - Webhook (optional): `https://<public web URL>/integrations/github/webhook` with a secret
     in `RELAY_GITHUB_WEBHOOK_SECRET`. Locally, leave it inactive and use "Sync now".
   - Repository permissions: **Contents**, **Metadata**, **Pull requests** and **Issues**:
     read-only. Organisation permission **Members**: read-only.
2. Generate a client secret and a private key.
3. In `backend/.env` set `RELAY_GITHUB_APP_ID`, `RELAY_GITHUB_APP_SLUG` (from the app URL),
   `RELAY_GITHUB_CLIENT_ID`, `RELAY_GITHUB_CLIENT_SECRET` and `RELAY_GITHUB_PRIVATE_KEY`.
4. Restart `relay-api` and `relay-worker`, then open a workspace → Integrations → Connect GitHub.

Sync runs on connect, on "Sync now", on webhooks and every 6 hours. Suggestions are reviewed under
Integrations → Review suggestions; approving never replaces an existing primary owner.

## Checks

```bash
cd backend  && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest
cd frontend && pnpm format:check && pnpm lint && pnpm typecheck && pnpm build
```

Backend tests need the compose database running. They rebuild the `relay_test` schema from
migrations (downgrade to base, then upgrade to head) and run as the restricted `relay_app` role.

End-to-end tests (Playwright) run against a production build (`pnpm build && pnpm start`,
with the API and worker running):

```bash
cd frontend
pnpm exec playwright test --project=public   # CI-safe, no account needed
pnpm e2e:login                                # once: sign in with real Chrome, saves e2e/.auth
pnpm exec playwright test --project=smoke     # real WorkOS account journeys
```

To reset the local database completely: `docker compose down -v`.
