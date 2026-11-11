# Relay

Relay keeps work moving when people and responsibilities change. It finds what someone
owns, rebuilds the context from GitHub, Linear and Notion with cited evidence, and moves
ownership through reviewed, audited handovers. AI only proposes; people decide.

## Demo

- **Judges: start here →** [step-by-step walkthrough](#for-judges)
- **Walkthrough Video**: [`artifacts/product-walkthrough/Relay_Product_Walkthrough.mp4`](artifacts/product-walkthrough/Relay_Product_Walkthrough.mp4) (1080p master recording)
- **Live Deployment**: [https://relay-continuity-nine.vercel.app](https://relay-continuity-nine.vercel.app)
- **Project Dossier (PDF)**: [`artifacts/Relay_Project_Overview_Round2.pdf`](artifacts/Relay_Project_Overview_Round2.pdf) (Round 2 publication build)

## For judges

**Live product:** <https://relay-continuity-nine.vercel.app> · **No setup needed.** Every step
below starts from that link and only uses buttons you can see. Allow about ten minutes.

> The API runs on a free server that sleeps when idle: the first page after a quiet period
> can take up to a minute. After that it is fast.

### 1. Get in (1 minute)

1. Open <https://relay-continuity-nine.vercel.app> and click **Go to your workspaces**.
2. Sign in with any email address. WorkOS emails you a one-time code; Relay never sees a
   password.
3. On **Workspaces**, click **Create sample workspace**. In a few seconds you are inside
   *Northwind Labs (demo)*: eight fictional people, seven responsibilities, a year of
   GitHub, Linear and Notion history, and an engineer, Arjun, who is leaving. All of it is
   synthetic.

**Look for:** the Overview leads with *A handover is waiting for you*, a continuity-health
ring, and the gaps that would hurt if someone left tomorrow.

### 2. Understand the past: Project Memory Replay (3 minutes)

1. In the sidebar, click **Responsibilities**, then **Production deployments**.
2. Click **Memory replay** (top right).
3. Press **Replay history** and watch the project evolve event by event; use the category
   chips to filter (try **Incident**).
4. Click **Explain this history**. The AI groups events into chapters on the time axis.
5. Click **Inspect** on any event, then ask *"Why does every payments-api deploy need a
   canary?"* under **Ask about this history**.

**Look for:** every event is a **Fact** with its source; chapters are labelled
**Inferred** and cite the events they rest on; the answer cites the outage and the decision.

### 3. Simulate the future: What If? (2 minutes)

1. Click **People & Teams**, then **Arjun Rao**, then **What if Arjun is unavailable?**
2. Set **is unavailable for** to *2 weeks* and click **Run simulation**.
3. Open **Why it is affected** under *Production deployments*.
4. Scroll to **Who could cover?** and click **Simulate with Dev**.

**Look for:** deployments are left with nobody, readiness is 55/100, one task falls due
while he is away; Dev (the planned recipient) closes the gap and readiness rises. A banner
confirms nothing in the workspace was changed.

### 4. Execute a safer handover: Handover Copilot (3 minutes)

1. Go back to **Overview** and click **Open handover**.
2. Read the brief: *What you now own*, *Knowledge gaps and open questions*, *Risks and
   conflicts*, *Recommended first steps*. Expand any **sources** link to see the evidence.
3. In **Ask about this handover**, ask *"How should I deploy payments-api?"*, then ask
   something the evidence cannot answer, such as *"What is the AWS root password recovery
   process?"*
4. Click **Open memory replay** under *Where this work came from*, then come back and click
   **Acknowledge receipt**.

**Look for:** the answer cites its sources and points out the conflicting old runbook; the
second question gets *Not in the evidence* instead of an invented answer.

### 5. Optional

- **Your own data:** create an empty workspace and open **Integrations** to connect GitHub,
  Linear or Notion (read-only).
- **The code:** [docs/round3/improvements-delivered.md](docs/round3/improvements-delivered.md)
  maps every Round 3 commitment to its code and tests;
  [docs/demo-script.md](docs/demo-script.md) is the full scripted demo.
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
workspaces and click **Create sample workspace**. Everything in it is synthetic.

- **AI features** (Handover Copilot answers, Memory Replay narratives, case analysis) need a
  model key. A free [Gemini API key](https://aistudio.google.com/apikey) works; give it to
  the setup script or set `RELAY_LLM_PROVIDERS=gemini` and `RELAY_GEMINI_KEY_1` in
  `backend/.env`. Without one, Relay says AI is not configured and everything else works:
  the simulator, timelines and rule-based analysis are deterministic.
- **GitHub, Linear and Notion** are optional and need your own app credentials (below).
- The setup script is safe to re-run: it keeps values you already set.

## Documentation

| Doc | What's in it |
|---|---|
| [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) | Architecture, data flow, integrations, AI pipeline, quality evidence |
| [docs/api-reference.md](docs/api-reference.md) | Full API endpoint listing, AI capabilities, external service config, library reference |
| [docs/round3/improvements-delivered.md](docs/round3/improvements-delivered.md) | Round 3: the three improvements as delivered, with the tests that prove each commitment |
| [docs/improvements.md](docs/improvements.md) | Round 3 improvements (AI Handover Copilot, "What If?" Simulator, Project Memory Replay) with acceptance criteria, plus Round 2 delivery status |
| [docs/architecture.md](docs/architecture.md) | System boundary, modules, data flows, inventory |
| [docs/ai.md](docs/ai.md) | AI-use disclosure: evidence pipeline, validation, injection handling, providers |
| [docs/trust.md](docs/trust.md) | Privacy, security, accessibility, responsible design, limitations |
| [docs/demo-script.md](docs/demo-script.md) | Scripted demo on the seeded organisation |
| [deployment.md](deployment.md) | Deploying to Vercel + Render + Neon, or one Docker host |
| [docs/sso.md](docs/sso.md), [docs/runbooks/incident-response.md](docs/runbooks/incident-response.md) | SSO setup, incident response |
| `docs/blueprint/`, `docs/adr/` | Decision Register, implementation plan, ADRs |
| `docs/release-audit/` | Full release audit: traceability, security review, production readiness |

Conventions for contributors: `CLAUDE.md`.

## Deploying

See [deployment.md](deployment.md) for the managed path (Vercel, Render and Neon, with a
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
