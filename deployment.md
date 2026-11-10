# Deploying Relay

This guide covers two ways to run Relay in production, the decisions behind them, and the
exact steps. Research was done in November 2026; prices and free-tier limits change, so
check the linked pages before committing money.

| Path | Best for | Pieces |
|---|---|---|
| **A. Managed (recommended)** | Demo, pilot, small teams; no servers to run | Vercel (web) · Render (API + worker) · Neon (Postgres 18) |
| **B. Single host** | Full control, one bill, data on your VM | Docker Compose on any VM ([deploy/README.md](deploy/README.md)) |

## 1. What has to run

```
browser ──HTTPS──> web (Next.js 16) ──server-to-server──> api (FastAPI) ──> Postgres 18
                        │                                    worker ──────────┘
GitHub webhooks ──> web /integrations/github/webhook ──proxy──> api
```

| Component | Process | Notes |
|---|---|---|
| Web | `pnpm build && pnpm start` | Server components and server actions call the API with the user's WorkOS token. The browser never calls the API directly. |
| API | `relay-api` (backend Docker image) | Stateless. `GET /health/live` (process up) and `GET /health/ready` (database answers). Also served under `/api/v1`. |
| Worker | `relay-worker` (same image) | Procrastinate worker for the transactional outbox, syncs, AI runs and periodic tasks. It must always run, or no jobs are processed. |
| Migrations | `alembic upgrade head` (same image) | Runs as the **owner** role, once per release, before the new code starts. |
| Database | PostgreSQL **18** | Needed for native `uuidv7()`. The only extension used is `btree_gist`. There is no pgvector, Redis or broker. |

Two database roles are mandatory: a non-superuser **owner** for migrations, and `relay_app`
for the API and worker, with no superuser, no `BYPASSRLS` and owning nothing. Row-level
security is forced on every tenant table. If the app connected as a role that bypasses RLS,
tenant isolation would silently stop working.

## 2. Platform research and choices

### Web → Vercel

- Vercel builds Next.js natively, App Router and server actions included. No adapter is needed.
- **Environment variables.**
  - Server-only values (WorkOS key, cookie password, `RELAY_API_URL`) stay off the client bundle.
  - Only `NEXT_PUBLIC_*` values are inlined into the client.
  - Variables are scoped per environment (Production, Preview, Development).
  - Sources: [Vercel env vars](https://vercel.com/docs/projects/environment-variables), [adding env vars](https://vercel.com/kb/guide/how-to-add-vercel-environment-variables).
- **Preview deployments** must not point at the production API or WorkOS environment. Give Preview its own values, or turn previews off.

### Why not Cloudflare for the web app (yet)

- Next.js on Cloudflare Workers goes through the OpenNext adapter. It supports Next.js 16, but:
  - **Node.js middleware is not supported yet.**
  - The adapter is still pre-1.0.
  - Sources: [Vercel: Next.js on Vercel vs Cloudflare](https://vercel.com/kb/guide/next-js-on-vercel-vs-cloudflare), [OpenNext for Cloudflare](https://opennext.js.org/cloudflare), [Next.js across platforms](https://www.nextjs.org/blog/nextjs-across-platforms).
- Relay's `src/proxy.ts` (Next.js 16's renamed middleware) runs on Node and handles authentication on every request, so this is a blocker.
- The Python API and long-running worker cannot run on Workers either.
- Cloudflare is still a good fit **in front** of Vercel/Render as DNS, WAF and DDoS protection. Revisit OpenNext when Node middleware support lands.

### API and worker → Render

- **Runtime.** Docker web service plus Docker background worker, built from `backend/Dockerfile`.
  - Workers can reach Postgres over the network.
  - Only *inbound* private traffic is restricted on free services.
  - Source: [Render private network](https://render.com/docs/private-network).
- **Free web services spin down after 15 minutes idle.** The next request then waits roughly 30–60 s while the service cold-starts.
  - Sources: [Render pricing explained](https://livemy.app/blog/render-pricing), [Render free-tier notes](https://agentdeals.dev/vendor/render), [cold starts](https://cronic.pages.dev/blog/eliminating-render-free-tier-cold-starts/).
  - Free compute is 750 instance-hours a month. That is enough for **one** service kept awake around the clock (about 744 h), but not two.
- **Background workers have no free plan.** The smallest paid instance is listed from about $7/month.
  - Source: [Render pricing 2026](https://www.activepieces.com/blog/render-pricing-2026-free-tier-workers-total-cost.md).
  - Relay needs the worker: invitations, syncs, AI analysis and notifications all go through it.
- **Health check.** Render uses `healthCheckPath` to gate deploys. A failing check keeps the old version live.
  - Relay sets it to `/health/ready`, which runs a real database round-trip.
  - Source: [Render health checks](https://render.com/docs/health-checks).
- **Blueprint.** [`render.yaml`](render.yaml) declares both services and a shared env group. Secrets are `sync: false`, so Render prompts for them on first sync.
  - Source: [Blueprint YAML reference](https://render.com/docs/blueprint-spec).
- **Keeping the free API warm.** An in-app cron sleeps along with the app, so the ping must come from outside.
  - Source: [Render free service sleeping](https://odown.com/blog/how-to-keep-a-render-free-service-from-sleeping/).
  - Relay ships [`.github/workflows/keep-warm.yml`](.github/workflows/keep-warm.yml), which pings `/health/live` every 10 minutes.
  - It pings `/health/live` rather than `/health/ready` because it only needs to keep the process up and shouldn't add database load.
  - It does nothing until you set the repository variable `RELAY_API_HEALTH_URL`.
  - A Render Cron Job could do the same, but it is a separately billed service, and GitHub Actions is free.
  - On a paid instance, delete the variable; there is no spin-down.

### Database → Neon (or Render Postgres)

- **Neon.**
  - Supports Postgres 14–18; Postgres 18 includes native `uuidv7()`. Sources: [Neon version support](https://neon.com/docs/postgresql/postgres-version-support), [UUIDv7 on Neon](https://neon.com/postgresql/18/uuidv7-support).
  - `btree_gist` is in its [extension list](https://neon.com/docs/extensions/pg-extensions).
  - Branching gives cheap staging copies.
- **RLS caveat (critical).**
  - Roles created in the Neon **console, CLI or API** are members of `neon_superuser`, which has **`BYPASSRLS`**. Source: [Neon on RLS](https://dev.to/neon-postgres/introducing-neon-authorize-simplifying-row-level-security-for-postgres-14fp).
  - Create `relay_app` and `relay_owner` with **SQL** (step 3.1), never in the console, then verify the flags.
- **Use the direct (non-pooled) host.**
  - The worker uses `LISTEN/NOTIFY` and holds a session.
  - The API sets tenant context per transaction.
  - The direct endpoint is the simple, safe choice for both.
- **Region.** Put the database in the same region as Render (for India, Singapore: Neon `aws-ap-southeast-1`, Render `singapore`) and the Vercel function region (`sin1`). Every request makes several API → database round-trips.
- **Render Postgres instead.**
  - It works the same way: use its internal URL from the same region. Source: [Render Postgres connection strings](https://render.com/tutorials/postgres-on-render/connection-strings).
  - Confirm that Postgres 18 is offered.
  - Free Render databases expire after 30 days. Sources disagree on 30 or 90 days, so check: [Render free-tier notes](https://agentdeals.dev/vendor/render), [Render Postgres limits](https://kuberns.com/blogs/render-postgres-pricing-setup-limits/).
  - Use a paid plan for anything you keep.

### Approximate monthly cost

| Setup | Web | API | Worker | DB | Total |
|---|---|---|---|---|---|
| Demo | Vercel Hobby $0 | Render free + keep-warm | Render Starter ~$7 | Neon free | **~$7** |
| Small production | Vercel Pro | Render Starter ~$7 | Render Starter ~$7 | Neon Launch / Render Basic | **~$40–60** |
| Single VM (path B) | — | — | — | — | VM price (2 vCPU / 4 GB) |

Vercel Hobby is for non-commercial use. A paying organisation needs Pro.

## 3. Path A step by step

Most of this can be done from a terminal or by Claude Code with the provider CLIs. The
steps that need a human are account sign-ups, payment details, OAuth consent screens and
pasting secrets into dashboards.

### 3.1 Database (Neon)

1. Create a project on Postgres **18** in the region chosen above. Copy the **direct** connection string for the default owner (`neondb_owner`).
2. Create the two Relay roles and the database with SQL, not the console. Generate two strong passwords; they never go into git.

   ```sql
   CREATE ROLE relay_owner LOGIN PASSWORD '<owner-pw>' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
   CREATE ROLE relay_app   LOGIN PASSWORD '<app-pw>'   NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;
   CREATE DATABASE relay OWNER relay_owner;
   REVOKE ALL ON DATABASE relay FROM PUBLIC;
   GRANT CONNECT ON DATABASE relay TO relay_app;
   -- then, connected to the relay database:
   CREATE EXTENSION IF NOT EXISTS btree_gist;
   ```

   The extension is created by the admin because `relay_owner` may not be allowed to. The migration uses `IF NOT EXISTS`.
3. Verify the flags. Both rows must show `f | f | f`:

   ```sql
   SELECT r.rolname, r.rolsuper, r.rolbypassrls,
          pg_has_role(r.rolname, 'neon_superuser', 'member') AS in_neon_superuser
   FROM pg_roles r WHERE r.rolname IN ('relay_owner', 'relay_app');
   ```

4. Build the two URLs, with `sslmode=require` on both:
   - `RELAY_MIGRATION_DATABASE_URL=postgresql+psycopg://relay_owner:<owner-pw>@<direct-host>/relay?sslmode=require`
   - `RELAY_DATABASE_URL=postgresql+psycopg://relay_app:<app-pw>@<direct-host>/relay?sslmode=require`

### 3.2 Migrations (GitHub Actions)

1. In the GitHub repository, create an environment called `production` with the secret `RELAY_MIGRATION_DATABASE_URL`.
2. Run **Actions → Migrate → Run workflow** ([`migrate.yml`](.github/workflows/migrate.yml)).

The owner credential lives only there. The API and worker never hold it, so a compromised
app process can't change the schema.

Run the workflow before deploying any release that adds a migration. Migrations are
expand/contract, so the running version keeps working while they apply.

On a paid Render API you can instead set `preDeployCommand: alembic upgrade head`, but that
puts the owner URL into the API's environment. The workflow is the stricter option.

### 3.3 API and worker (Render)

1. In Render, go to **New → Blueprint**, select this repository, and Render reads [`render.yaml`](render.yaml).
2. Fill the prompted secrets:

   | Variable | Value |
   |---|---|
   | `RELAY_DATABASE_URL` | the `relay_app` URL from 3.1 |
   | `RELAY_FRONTEND_BASE_URL` | `https://<web domain>`, used in emails, invitations and OAuth return links |
   | `RELAY_WORKOS_CLIENT_ID`, `RELAY_WORKOS_API_KEY` | WorkOS **production** environment |
   | `RELAY_INTEGRATION_ENCRYPTION_KEY` | Fernet key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Back it up; losing it means reconnecting Linear and Notion. |
   | `RELAY_RESEND_API_KEY`, `RELAY_EMAIL_FROM` | Optional. Without them, emails are skipped and in-app notifications still work. |
   | `RELAY_LLM_PROVIDERS`, `RELAY_GEMINI_API_KEYS`, `RELAY_GROQ_API_KEY` | Optional. Without them, the deterministic analysis still runs and AI features show "not configured". Ollama is for local use only. |
   | `RELAY_GITHUB_WEBHOOK_SECRET` (+ the `RELAY_GITHUB_APP_*` values) | Only if you connect GitHub |

3. Deploy. `RELAY_ENVIRONMENT=production` turns on strict configuration validation. A missing or inconsistent value stops startup with a readable message in the logs, rather than half-working.
4. Check that `https://relay-api.onrender.com/health/ready` returns 200. Use your service's actual URL.
5. **Free plan only:** set the repository variable `RELAY_API_HEALTH_URL` to `https://<api>/health/live` to turn on the keep-warm workflow.

### 3.4 Web (Vercel)

1. Import the repository with **Root Directory** `frontend`. Vercel detects Next.js and uses pnpm from the lockfile.
2. Set **Settings → Functions → Region** to the same region as the API (e.g. `sin1`).
3. Set these environment variables for **Production**:

   | Variable | Value |
   |---|---|
   | `RELAY_API_URL` | `https://<api>.onrender.com` (server-only) |
   | `WORKOS_CLIENT_ID`, `WORKOS_API_KEY` | WorkOS production (server-only) |
   | `WORKOS_COOKIE_PASSWORD` | 32+ random chars: `openssl rand -base64 32` |
   | `WORKOS_ISSUER` | `https://api.workos.com/user_management/<client id>` |
   | `NEXT_PUBLIC_WORKOS_REDIRECT_URI` | `https://<web domain>/callback` |

4. Deploy, then add your custom domain. Cloudflare DNS in front is fine; use "DNS only" or Full (strict) TLS.

### 3.5 Identity and integrations

| Service | Setting |
|---|---|
| WorkOS (production env) | Redirect URI `https://<web>/callback`; sign-out redirect `https://<web>/`; enable the sign-in methods you want. For SSO/SAML, see [docs/sso.md](docs/sso.md); SSO is set up per organisation in WorkOS with no Relay code changes. |
| GitHub App | Callback `https://<web>/integrations/github/callback`; webhook `https://<web>/integrations/github/webhook` (the web app proxies the raw body to the API, which checks the signature); read-only repository permissions as listed in [deploy/README.md](deploy/README.md) |
| Linear | Callback `https://<web>/integrations/linear/callback`, scope `read`. Issue creation needs `RELAY_LINEAR_ISSUE_WRITES=true` and `RELAY_LINEAR_OAUTH_SCOPE=read,write`, plus approval of each issue. |
| Notion | Redirect `https://<web>/integrations/notion/callback`, read-content capability |
| Resend | Verify the sending domain (SPF/DKIM) |

### 3.6 First run

1. Open `https://<web>`, sign in, create a workspace, and invite people.
2. Optional: load the synthetic demo organisation. Run it from a machine that has `RELAY_DATABASE_URL` set to production; it uses the app role.

   ```sh
   cd backend && uv run relay-demo-seed --owner <your WorkOS user id>
   ```

## 4. Operating it

- **Logs.** JSON lines (`RELAY_JSON_LOGS=true`), one access line per request with method, route template, status and duration. Every response and log line carries `X-Request-ID`. Bodies, query strings and tokens are never logged.
- **Health.** Render gates deploys on `/health/ready`. Add an external uptime check on the same URL for alerting.
- **Backups.**
  - Neon has point-in-time restore within your plan's history window.
  - Also take a nightly logical dump off-platform, for example a scheduled `pg_dump` with the owner URL to versioned object storage.
  - Test a restore monthly. [`deploy/restore-drill.sh`](deploy/restore-drill.sh) shows the check.
- **Releases.**
  1. Merge to `main`; CI runs lint, types, tests, migrations, SBOM, image scan and the licence check.
  2. Run **Migrate**.
  3. Render and Vercel auto-deploy.
  4. Roll back from each dashboard. Migrations are expand-only per release, so the previous code still runs against the newer schema.
- **Secrets rotation.** WorkOS key, Resend key and LLM keys can be rotated any time by updating them in Render/Vercel and redeploying. Rotating `RELAY_INTEGRATION_ENCRYPTION_KEY` requires reconnecting Linear and Notion.
- **Incidents.** Follow [docs/runbooks/incident-response.md](docs/runbooks/incident-response.md). In short: pause the affected connector (Integrations → Health), turn off AI with the kill switch (Agents), export the audit log, then restore or roll back.

## 5. Path B: single host with Docker Compose

Everything (Postgres, migrations, API, worker, web, nightly backups) runs from
[`deploy/docker-compose.prod.yml`](deploy/docker-compose.prod.yml) behind your own TLS proxy.
Follow [deploy/README.md](deploy/README.md).

- Any VM with Docker works.
- There is no spin-down and no keep-warm.
- You own patching and off-host backups.

## 6. Pre-launch checklist

- [ ] `relay_app` and `relay_owner`: `rolsuper = f`, `rolbypassrls = f`, not in `neon_superuser`.
- [ ] Production and Preview use different WorkOS environments, API URLs and databases.
- [ ] `/health/ready` is 200; Render health check path set.
- [ ] WorkOS redirect URIs match the web domain exactly.
- [ ] `RELAY_INTEGRATION_ENCRYPTION_KEY` and the database passwords are stored in a password manager.
- [ ] A restore has been tested once.
- [ ] Keep-warm is on only while the API is on the free plan.
- [ ] Integrations stay read-only unless issue writes are deliberately enabled.
