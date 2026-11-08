# Relay

Organisational continuity platform. Planning docs: `docs/blueprint/`. Conventions: `CLAUDE.md`.

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

# 3. Frontend (separate terminal)
cd frontend
pnpm install
pnpm dev                           # http://localhost:3000
```

## Checks

```bash
cd backend  && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest
cd frontend && pnpm format:check && pnpm lint && pnpm typecheck && pnpm build
```

Backend tests need the compose database running. They rebuild the `relay_test` schema from
migrations (downgrade to base, then upgrade to head) and run as the restricted `relay_app` role.

To reset the local database completely: `docker compose down -v`.
