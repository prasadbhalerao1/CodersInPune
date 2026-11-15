# Incident response runbook

For anyone operating a Relay deployment. Keep it short and act in order. When in doubt,
contain first, then investigate.

## 0. Severity

| Level | Examples | Response |
|---|---|---|
| SEV1 | Possible cross-tenant exposure, leaked secret, data loss | Start now, all hands, notify affected workspace owners within 72 h |
| SEV2 | Feature down for everyone (sign-in, cases, jobs), connector writing wrongly | Start within 1 h |
| SEV3 | One connector failing, slow pages, a failed email batch | Next working day |

## 1. Triage (first 15 minutes)

1. **Note the time and start a log.** Record what you see, what you do and when.
2. **Health:** `GET /health/ready` on the API, plus the platform dashboards (Render, Vercel, Neon, or `docker compose ps`).
3. **Logs:**
   - Find the failing request's `X-Request-ID`. It is in the browser's network tab and in every response.
   - Search logs for it. One ID joins the web request, the API request and the jobs it queued.
4. **Jobs:**
   - Is the worker running?
   - Are outbox events piling up? Check `platform.outbox_event` where `processed_at IS NULL`, as the owner role.
   - Stalled jobs are re-queued automatically every 5 minutes.

## 2. Contain

| Situation | Action |
|---|---|
| A connector misbehaves (wrong data, error loop, suspicious activity) | Integrations → Health → **Pause**. Syncs and webhooks for it stop being processed until resumed |
| AI output is wrong or unsafe | Agents → **kill switch** (workspace), or remove `RELAY_LLM_PROVIDERS` and redeploy (all workspaces). Deterministic features keep working |
| External issue writes are wrong | Set `RELAY_GITHUB_ISSUE_WRITES=false` / `RELAY_LINEAR_ISSUE_WRITES=false` and redeploy. Pending actions stay queued and visible |
| A compromised member account | Remove the membership (Settings → Members). Access ends on the next request. Then block the user in WorkOS |
| Leaked secret | Rotate it at the provider, update it in Render/Vercel/`.env.production`, and redeploy. See the table below |
| Bad release | Roll back in the platform dashboard or redeploy the previous image tag. Migrations are expand-only, so the old code runs on the new schema |
| Possible cross-tenant exposure | Take the web app offline (maintenance), keep the database, preserve logs, and treat it as SEV1 |

**Secret rotation:**

| Secret | Effect of rotating |
|---|---|
| `WORKOS_API_KEY`, `RELAY_WORKOS_API_KEY` | None for users |
| `WORKOS_COOKIE_PASSWORD` | Everyone signs in again |
| `RELAY_GITHUB_WEBHOOK_SECRET` | Update the GitHub App at the same time. The reconciliation sweep covers the gap |
| `RELAY_INTEGRATION_ENCRYPTION_KEY` | Stored Linear and Notion tokens become unreadable, so reconnect those integrations |
| Database passwords | Update both URLs, redeploy API, worker and migrate |
| LLM and email keys | None for users |

## 3. Investigate

- **Audit log** (Audit → filter by action, actor or target; export CSV). Every change, approval, export, deletion, permission denial and connector state change is recorded with actor and time. The log is append-only, so it's trustworthy evidence.
- **Connector runs** (Integrations → Health). Each sync has a status, duration and error code.
- **AI runs** (Agents → run). Each run lists its steps, tokens and errors, and the proposals people accepted or rejected.
- **Database:** use the owner role, read-only queries, and always set `app.tenant_id` with `set_config(..., true)` inside a transaction. Never disable RLS on production.

## 4. Recover

- **Restore data** from the newest good backup:
  - Neon: point-in-time restore to a branch.
  - Compose: [deploy/README.md §5](../../deploy/README.md).

  Check the restore against the audit log before switching traffic.
- **Replay work.** Failed jobs stay in the outbox. Handlers are idempotent, so retrying is safe.
- **Email.** Failed deliveries can be retried from Settings → Notifications.

## 5. Communicate and learn

- **SEV1 involving personal data:** notify affected workspace owners with what happened, what data, what you did and what they should do. Do this within 72 hours, or sooner if the law requires it.
- **Post-incident review within 5 working days.** Cover:
  - the timeline;
  - the root cause;
  - what worked;
  - one or two concrete follow-ups, each with an owner, preferably a test that would have caught it.

  Record any architectural change as an ADR in `docs/adr/`.

## Alerts

The **Monitor** workflow (`.github/workflows/monitor.yml`) checks every 10 minutes and
keeps one open GitHub issue labelled `incident` while anything is wrong (GitHub emails
the repository owner). Each alert name maps to a first action:

| Alert | Meaning | First action |
|---|---|---|
| `api_or_database_unavailable` | `/health/ready` not 200 | Render API logs; Neon status; if DB is down, see "Database outage" below |
| `web_unavailable(code)` | Frontend not serving | Vercel deployment status; roll back to the previous deployment |
| `worker_down` | No worker heartbeat for 5 min | Render worker logs; restart the worker; jobs resume from the queue (outbox is durable) |
| `queue_backlog` | A ready job waited > 15 min | Worker running but slow or stuck: check logs for one long job; restart; scale concurrency |
| `jobs_failing` | ≥ 5 failed jobs in 1 h | Logs filtered by the event id (`request_id`); fix the cause; failed outbox events retry |
| `events_failing` | Outbox events erroring | Same as above; `last_error_type` names the exception class |
| `connector_unhealthy` | A connector is revoked or its last sync failed | Integrations health page; reconnect or pause; tell the workspace admin |
| `email_failing` | ≥ 3 failed emails in 24 h | Email provider dashboard (sender verification, quota); admins can retry deliveries |
| `ai_failing` | ≥ 3 failed or timed-out AI runs in 24 h | Provider status / key quota; the deterministic analysis still works; kill switch in Agents |
| `ai_budget_exhausted` | A run hit a token budget | Raise the workspace budget or wait for the month to roll over |
| `ops_unreachable` | `/health/ops` didn't answer | Check `RELAY_OPS_TOKEN` matches in Render and GitHub secrets |
| `database_unavailable` | Ops summary couldn't reach the DB | As `api_or_database_unavailable` |

The **Backup** workflow fails (and GitHub emails the owner) when the nightly dump or its
restore drill fails.

### Database outage
Neon status page → if the branch is unavailable, wait or restore: Neon console → Restore
→ point in time into a **new branch**, check it, then switch `RELAY_DATABASE_URL` to it.
Never restore over the live branch. Nightly encrypted dumps (Backup workflow artifacts,
14 days) are the second line: `gpg -d relay-*.dump.gpg > relay.dump` then `pg_restore`
into a fresh database created with the roles from `deployment.md`.

### Failed migration
Migrations are transactional: a failure leaves the previous schema. Keep the previous app
version running; fix forward with a new migration. Never edit an applied migration.

### Credential compromise
Rotate in this order: the leaked secret at its provider → Render/Vercel env → redeploy.
Database: `ALTER ROLE relay_app PASSWORD …` as the Neon admin. WorkOS/GitHub App/Linear/
Notion: regenerate the client secret or private key. `RELAY_INTEGRATION_ENCRYPTION_KEY`:
re-encrypt is not supported; disconnect and reconnect integrations after rotation.

### Data leakage
Treat as Sev 1. Pause affected connectors, narrow source audiences to managers, use the
AI kill switch, export the audit log for the window, then follow §5 notification duties
(legal advice required).
