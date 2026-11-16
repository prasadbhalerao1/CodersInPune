# Security evidence

Relay holds sensitive organisational knowledge, so security is designed in and checked by
tests. This page maps the OWASP Application Security Verification Standard (ASVS 4.0,
Level 2) to the code and tests that cover it, and records the latest scans.

## Scans (16 Nov 2026)

| Check | Command | Result |
|---|---|---|
| Frontend dependencies (production) | `pnpm audit --prod` | No known vulnerabilities |
| Backend dependencies | `uv export --no-dev` + `pip-audit` | No known vulnerabilities |
| Secrets in tracked files | Pattern scan for cloud keys, webhook URLs, private keys, database URLs | None (only a documented placeholder); `.env` is never tracked |
| Tenant isolation and schema rules | `uv run pytest tests/security` | 198 passed |

## ASVS Level 2 mapping

| ASVS chapter | How Relay meets it | Where | Proof |
|---|---|---|---|
| V1 Architecture | One API owns all business logic; the web app holds no rules; deny-by-default permission registry; ADRs for every deviation | `relay/policy/permissions.py`, `Documentation/3-architecture/decisions/` | `tests/security/test_route_auth.py` |
| V2 Authentication | WorkOS AuthKit (email codes, passwords or SSO); WorkOS holds credentials and Relay never stores them. The one password in the code is the published shared password of the judges' sample accounts, which can only open the sample workspace. Access tokens are verified against WorkOS JWKS on every request | `relay/identity/tokens.py` | `tests/test_tokens.py` |
| V3 Session management | Sealed, http-only session cookies managed by AuthKit; sign-out revokes; API is stateless bearer | `frontend/src/proxy.ts` | `e2e/public.spec.ts` (protected routes redirect) |
| V4 Access control | Membership-derived tenant (never client input); `authorize()`/`visible()` inside every service; forced row-level security on every tenant table; read-only roles cannot write | `relay/identity/workspace_access.py`, migrations | `tests/security/test_tenant_isolation.py`, `test_schema_conventions.py`, `test_new_features_access.py` |
| V5 Validation and encoding | Strict Pydantic inputs reject unknown fields and cap lengths; SQLAlchemy expressions only (no raw SQL in app code); LIKE patterns escaped; React escapes output | `relay/shared/api_types.py`, `relay/shared/text.py` | input tests across modules |
| V6 Stored cryptography | Integration tokens and the Slack webhook are encrypted with a dedicated Fernet key and never returned by the API | `relay/shared/secrets.py`, `integrations/slack/service.py` | `test_slack.py` (URL never returned) |
| V7 Errors and logging | Problem-details errors with no internals; append-only audit log written in the same transaction; audit metadata holds identifiers only | `relay/shared/errors.py`, `relay/audit/` | `tests/security/test_permissions_audit_jobs.py` |
| V8 Data protection | Managers-only evidence is filtered before any AI call; data export and 30-day deletion; connector data purged after disconnect | `intelligence/evidence.py`, `platform/deletion.py` | `test_ask.py`, `test_copilot.py` (restricted evidence never reaches a member) |
| V9 Communications | HTTPS only in production (Render, Vercel); production config refuses non-https URLs | `relay/config.py` | config validation |
| V10 Malicious code | Prompt-injection text in sources is treated as data; models hold read-only tools only | `intelligence/capabilities.py` | `test_analysis.py` (injection inert) |
| V11 Business logic | Separation of duties on approvals; a case completes only when tasks are done, readiness is met and the incoming owner has accepted; idempotent creates via `Idempotency-Key` (cases, tasks, responsibilities, meetings; a reused key with a different request is rejected) plus idempotent sample creation, proposal acceptance and meeting items; rate limits on AI and Slack endpoints | `continuity/workflow.py`, `relay/shared/idempotency.py`, `relay/shared/rate_limit.py` | `test_cases.py`, `test_case_lifecycle.py`, `test_idempotency.py`, `test_sample_workspace.py` |
| V12 Files and resources | Imports validated and size-capped; no user-uploaded executables | `relay/imports/` | import tests |
| V13 API | Every route authenticated except health, sample-free public pages and signed webhooks; OpenAPI generated from code | `relay/app.py`, `Documentation/4-api/openapi.json` | `test_route_auth.py` |
| V14 Configuration | Secrets only from environment; app connects as a role with no superuser, no BYPASSRLS, owning nothing; migrations run as owner from a separate workflow | `infra/db/init/`, `.github/workflows/migrate.yml` | `test_schema_conventions.py` |

## Operational practice

- Production secrets are rotated after judging, including the Slack webhook.
- Migrations run only from the protected `Migrate` workflow; the running app can't alter the schema.
- Responsible disclosure: open a private security advisory on the repository.
