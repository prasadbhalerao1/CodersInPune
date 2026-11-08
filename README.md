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
5. Set `RELAY_WORKOS_CLIENT_ID=<client_id>` in `backend/.env`.
6. Confirm the token parameters the API enforces:
   - `curl https://api.workos.com/user_management/<client_id>/.well-known/openid-configuration`
     → `issuer` must equal the value above.
   - `curl https://api.workos.com/sso/jwks/<client_id>` → keys should have `"alg": "RS256"`.
     If not, set `RELAY_JWT_ALGORITHMS` accordingly.

Manual end-to-end check (not covered by automated tests, which use locally generated keys):
sign in at `http://localhost:3000` → create a workspace → open it → sign out → confirm
`/workspaces` redirects to sign-in.

## Checks

```bash
cd backend  && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest
cd frontend && pnpm format:check && pnpm lint && pnpm typecheck && pnpm build
```

Backend tests need the compose database running. They rebuild the `relay_test` schema from
migrations (downgrade to base, then upgrade to head) and run as the restricted `relay_app` role.

To reset the local database completely: `docker compose down -v`.
