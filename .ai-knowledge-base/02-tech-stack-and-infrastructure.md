# 02 - Tech Stack & Infrastructure

## 1. Complete Technology Inventory

### 1.1 Backend Runtime & Libraries (Python 3.14+)
| Library / Tool | Version | Purpose / Architectural Scope |
|---|---|---|
| **Python** | `>=3.14` | Core backend runtime. Enforces modern type hinting and asyncio features. |
| **FastAPI** | `>=0.162.2` | High-performance asynchronous HTTP API framework. Handles routing, OpenAPI doc generation, dependency injection. |
| **Uvicorn** | `>=0.54.0` | ASGI web server. On Windows, runs under a Selector event loop to support Psycopg 3 async. |
| **SQLAlchemy** | `>=2.1.8` | Async ORM and Core SQL expression builder (`sqlalchemy[asyncio]`). No raw SQL in business logic. |
| **Psycopg 3** | `>=3.3.8` | PostgreSQL database adapter with native async support and binary extensions. |
| **Alembic** | `>=1.20.1` | Database migration framework. All 41 migrations are hand-crafted. |
| **Procrastinate** | `==3.10.0` | PostgreSQL-native job queue. Runs background ingestion, AI tasks, and periodic maintenance. |
| **PydanticAI** | `==2.66.0` | `pydantic-ai-slim[google,groq,openai]`. Provides typed, schema-validated LLM invocation. |
| **PyJWT[crypto]**| `>=2.15.1` | RS256 token decoding and JWKS validation for WorkOS AuthKit JWTs. |
| **HTTPX** | `>=0.28.1` | Asynchronous HTTP client for outbound integration calls (GitHub, Linear, Notion, WorkOS, LLMs). |
| **Pydantic** | `>=2.x` | Data validation, settings management (`pydantic-settings`), and strict DTO schemas. |
| **Ruff** | `>=0.17.4` | Linter and code formatter. Target version `py314`. |
| **Mypy** | `>=2.4.1` | Strict static type checker. |
| **Pytest** | `>=9.2.0` | Unit, integration, security, and AI evaluation test runner. |

### 1.2 Frontend Runtime & Libraries (Node.js 22+ / Next.js 16)
| Library / Tool | Version | Purpose / Architectural Scope |
|---|---|---|
| **Next.js** | `16.4.5` | React framework using App Router, React Server Components (RSC), and Server Actions. Zero business logic in frontend. |
| **React** | `19.3.0` | Frontend UI library. |
| **@workos-inc/authkit-nextjs** | `^4.6.3` | Authentication proxy middleware (`proxy.ts`), server-side session extraction (`withAuth`), and token management. |
| **@base-ui/react** | `^1.9.0` | Headless, accessible UI primitives powering the design system. |
| **Tailwind CSS** | `^4.0` | Utility-first CSS styling engine using `@tailwindcss/turbopack`. |
| **shadcn/ui** | `^4.23.0` | Accessible component library built on Base UI and Tailwind. |
| **Lucide React** | `^1.70.0` | Vector icons for UI navigation and status indicators. |
| **Playwright** | `1.57.0` | End-to-end browser testing for public routes and authenticated smoke flows. |
| **pnpm** | `10.33.0` | Strict package manager. |

---

## 2. Infrastructure & Deployment Topology

Relay is deployed across two production topologies:

### 2.1 Managed Cloud Topology (Vercel + Render + Neon)
* **Frontend Hosting**: Vercel (Next.js App Router).
* **Backend API & Embedded Worker**: Render Web Service (`render.yaml`).
  - Standard plan runs `relay-api` with an embedded background worker (`RELAY_EMBEDDED_WORKER=true`) to avoid multi-dyno overhead in lower tiers.
  - Production can split `relay-api` and `relay-worker` into separate instances.
* **Database**: Neon Managed PostgreSQL 18 with point-in-time recovery (PITR).
* **Identity Provider**: WorkOS AuthKit (Email OTP / SSO, passwordless).

### 2.2 Self-Hosted Docker Compose Topology (`deploy/docker-compose.yml`)
For single-host deployments:
* Container `postgres`: PostgreSQL 18 with `pgvector` and initial role bootstrap scripts (`infra/db/init/01-roles.sql`).
* Container `api`: Python 3.14 container running `relay-api` on port `8000`.
* Container `worker`: Python 3.14 container running `relay-worker`.
* Container `web`: Node.js 22 container running `pnpm start` on port `3000`.

---

## 3. Environment Variables Reference

### 3.1 Backend Configuration (`backend/.env`)
| Variable | Description / Purpose | Default / Requirement |
|---|---|---|
| `RELAY_DATABASE_URL` | PostgreSQL connection string (`postgresql+psycopg://relay_app:...@.../relay`). Must connect as `relay_app`. | **Required** |
| `RELAY_ENVIRONMENT` | Environment name: `development`, `staging`, `production`. When `production`, OpenAPI docs and `/docs` are disabled. | `development` |
| `RELAY_OWNER_DATABASE_URL`| Connection string for `relay_owner` used strictly by Alembic migrations and database setup. | Optional (local dev defaults) |
| `RELAY_WORKOS_CLIENT_ID` | WorkOS AuthKit client ID for JWKS URL construction and invitation dispatch. | **Required** |
| `RELAY_WORKOS_API_KEY` | WorkOS API key for server-side invitation emails and user account queries. | **Required** |
| `RELAY_JWT_ISSUER` | Expected JWT issuer: `https://api.workos.com/user_management/<client_id>`. | **Required** |
| `RELAY_JWT_ALGORITHMS` | Algorithms allowed for WorkOS token verification. | `RS256` |
| `RELAY_INTEGRATION_KEY` | 32-byte secret for encrypting third-party OAuth access and refresh tokens at rest in PostgreSQL. | **Required** |
| `RELAY_LLM_PROVIDERS` | Comma-separated prioritized list of LLM providers: `gemini,groq,ollama`. | `gemini` |
| `RELAY_GEMINI_KEY_1..4` | Up to 4 Google Gemini API keys rotated automatically on quota/rate-limit errors. | Optional (deterministic fallback if absent) |
| `RELAY_GROQ_KEY` | API key for Groq fallback model (`llama-3.3-70b-versatile`). | Optional |
| `RELAY_OLLAMA_URL` | Local Ollama endpoint for offline model inference. | Optional |
| `RELAY_EMBEDDED_WORKER` | If `true`, spawns background job consumer inside the API process (useful for single-container hosting). | `false` |
| `RELAY_WORKER_CONCURRENCY`| Number of concurrent Procrastinate tasks per worker process. | `4` |
| `RELAY_MONTHLY_TOKEN_BUDGET`| Hard token spend cap per workspace per month. | `200000` |
| `RELAY_EMAIL_PROVIDER` | `resend`, `smtp`, or `memory`. | `memory` (dev) |
| `RELAY_RESEND_KEY` | Resend API key for transactional emails. | Optional |

### 3.2 Frontend Configuration (`frontend/.env.local`)
| Variable | Description / Purpose | Default / Requirement |
|---|---|---|
| `WORKOS_CLIENT_ID` | WorkOS Client ID for AuthKit session handling. | **Required** |
| `WORKOS_API_KEY` | WorkOS API Key. | **Required** |
| `WORKOS_COOKIE_PASSWORD`| 32-byte encrypted cookie password generated via `openssl rand -base64 32`. | **Required** |
| `NEXT_PUBLIC_WORKOS_REDIRECT_URI` | Auth callback URI: `http://localhost:3000/callback` or production domain. | **Required** |
| `RELAY_API_URL` | Base URL of the FastAPI backend (e.g. `http://127.0.0.1:8000` or Render URL). | **Required** |

---

## 4. Build, Local Dev & CI/CD Pipelines

### 4.1 Local Developer Tooling
* `python scripts/setup.py`: Orchestrates end-to-end setup. Prompts for WorkOS keys and optional Gemini key, verifies Docker/uv/node/pnpm, writes `.env` files, starts PostgreSQL container, installs uv and pnpm dependencies, runs Alembic migrations.
* `python scripts/dev.py`: Spawns backend (`uv run relay-api`) and frontend (`pnpm dev`) simultaneously with unified signal handling.

### 4.2 GitHub Actions Workflows (`.github/workflows/` and `workflows/`)
* **`ci.yml`**: Runs on all PRs and pushes to `main`.
  1. `licences`: Enforces that no AGPL, GPL, SSPL, BSL, or SUL licenses are imported.
  2. `backend-lint`: Runs `ruff check .`, `ruff format --check .`, and `mypy` strict.
  3. `backend-test`: Spins up real PostgreSQL 18 container with `pgvector`, runs Alembic migrations from scratch, executes 250+ security, schema convention, tenant isolation, and AI evaluation tests as `relay_app`.
  4. `frontend-check`: Runs ESLint, TypeScript typecheck (`next typegen && tsc --noEmit`), Prettier check, and Next.js production build.
  5. `e2e`: Runs Playwright test suite against production build.
* **`migrate.yml`**: Runs `alembic upgrade head` securely as `relay_owner` against Neon production upon deployment.
* **`backup.yml`**: Nightly scheduled backup that dumps the database, tests a restore into a throwaway PostgreSQL 18 instance, and validates schema version and RLS policies.
* **`monitor.yml`**: Runs every 10 minutes; pings `/health/live`, `/health/ready`, and `/health/ops` and creates a GitHub incident issue if degraded.
