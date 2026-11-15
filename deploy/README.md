# Deploying Relay

A single-host Docker Compose deployment: Postgres, a one-shot migration job, the API, the
background worker and the web app. Any host with Docker Engine 24+ and Compose v2 works
(a small VM with 2 vCPU / 4 GB RAM is enough for a small organisation).

```
browser ──TLS──> reverse proxy ──> web :3000 ──> api :8000 ──> db :5432
                                                 worker ──────────┘
```

Only `web` is published. The API is reached server-to-server from the web container; the
browser never calls it directly.

## 1. Prerequisites

- A domain and a TLS-terminating reverse proxy in front of `web` (Caddy, nginx, a cloud
  load balancer). Relay requires HTTPS outside local development.
- A **WorkOS production environment**: client ID, API key, and the redirect URI
  `https://<domain>/callback` registered under Redirects.
- Optional integrations, configured in their own consoles:

| Integration | Where | Callback / setting |
|---|---|---|
| GitHub App | github.com/settings/apps | Setup/callback URL `https://<domain>/integrations/github/callback`; webhook URL `https://<domain>/integrations/github/webhook` (the web app forwards it to the API) with `RELAY_GITHUB_WEBHOOK_SECRET`; repository permissions Metadata, Contents, Pull requests, Issues (read); organisation permission Members (read); events: installation, repository, pull request, issues, team, membership |
| Linear | linear.app/settings/api/applications | Callback `https://<domain>/integrations/linear/callback`, scope `read` |
| Notion | notion.so/my-integrations (public integration) | Redirect `https://<domain>/integrations/notion/callback`, read content capability |
| Resend | resend.com | Verify the sending domain; use a key with send access |

## 2. First deployment

```sh
cp deploy/.env.production.example deploy/.env.production   # git-ignored
# fill in every required value; see the comments in the file
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.production up -d --build
docker compose -f deploy/docker-compose.prod.yml ps
```

What happens:

1. `db` starts; on an empty volume `db-init/01-roles.sh` creates `relay_owner`,
   `relay_app` and the `relay` database.
2. `migrate` runs `alembic upgrade head` as `relay_owner` and exits.
3. `api` and `worker` start as `relay_app` (no superuser, no BYPASSRLS). Startup fails fast
   with a readable message if configuration is incomplete or inconsistent.
4. `web` starts once the API reports ready.

Then sign in at `https://<domain>`, create the first workspace, and invite people.

## 3. Upgrades

```sh
git pull
RELAY_VERSION=$(git rev-parse --short HEAD) \
  docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.production up -d --build
```

Migrations run before the new API and worker start. They are written expand/contract, so
the previous version keeps working while they apply. Take a backup first (below).

Shutdown is graceful: the API drains in-flight requests (20 s); the worker stops taking new
jobs and gives running ones `RELAY_WORKER_SHUTDOWN_SECONDS` (default 30) before they are
cancelled. Cancelled or failed jobs stay in the outbox and are retried, and every handler is
idempotent, so a restart never loses or duplicates work.

## 4. Health checks

| Endpoint | Meaning |
|---|---|
| `GET /health/live` (api, internal) | The process is up |
| `GET /health/ready` (api, internal) | The database answers; used by the compose healthcheck |
| `GET /` (web) | The web server answers; used by its healthcheck |

`docker compose ps` shows the health of each service; `docker compose logs -f api worker`
shows logs (identifiers only; tokens and content are never logged).

## 5. Backups and restore

The database is the only state. The `backup` service writes a nightly dump
(`RELAY_BACKUP_HOUR`, UTC, default 02) into the `relay-backups` volume and keeps 14 days.
Copy that volume off the host. Prove the dumps restore with the drill, monthly:

```sh
sh deploy/restore-drill.sh   # restores the newest dump into a scratch database and checks it
```

Take an extra dump before every upgrade:

```sh
docker compose -f deploy/docker-compose.prod.yml exec -T db \
  pg_dump -U postgres -d relay --format=custom > relay-$(date +%F).dump
```

Store dumps off the host (object storage with versioning). Test a restore regularly:

```sh
docker compose -f deploy/docker-compose.prod.yml stop api worker web
docker compose -f deploy/docker-compose.prod.yml exec -T db \
  pg_restore -U postgres -d relay --clean --if-exists --no-owner --role=relay_owner < relay-YYYY-MM-DD.dump
docker compose -f deploy/docker-compose.prod.yml up -d
```

Also keep a secure copy of `RELAY_INTEGRATION_ENCRYPTION_KEY`: without it, stored Linear
and Notion tokens can't be decrypted and those integrations must be reconnected.

### Deleted workspaces

An owner can schedule deletion in Settings → Data & privacy; it can be cancelled for 30
days. Purge due workspaces daily (host cron) as the owner role:

```sh
docker compose -f deploy/docker-compose.prod.yml --env-file deploy/.env.production   run --rm migrate relay-purge-workspaces
```

## 6. Using a managed Postgres instead

Create the two roles once as an administrator (the SQL in `db-init/01-roles.sh`), remove
the `db` service, and set `RELAY_DATABASE_URL` / `RELAY_MIGRATION_DATABASE_URL` in the
`environment:` blocks of `migrate`, `api` and `worker`. Postgres 18 is required (`uuidv7()`).

## 7. Development vs production

| | Development | Production |
|---|---|---|
| Config | `backend/.env`, `frontend/.env.local` | `deploy/.env.production` |
| Database | `docker-compose.yml` (dev passwords) | Bundled container or managed, secret passwords |
| `RELAY_ENVIRONMENT` | `local` | `production` (strict validation) |
| Processes | `uv run relay-api`, `uv run relay-worker`, `pnpm dev` | Compose services with restart policies |

## Known limitations

- GitHub webhooks arrive at the web app, which forwards the raw body and signature headers
  to the API; the API verifies the signature. The 6-hourly reconciliation covers any missed
  delivery.
- One worker process is enough for a small organisation; scale with
  `RELAY_WORKER_CONCURRENCY` before adding replicas.
- No built-in metrics/alerting: watch container health and logs, or add your platform's.
