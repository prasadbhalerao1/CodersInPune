# Relay: test report (Round 3)

Results from the runs on 16 Nov 2026. Every number below is from an actual run.

| Suite | Command | Result |
|---|---|---|
| Backend: API, services, security, AI validation (real PostgreSQL as the restricted `relay_app` role) | `cd backend && uv run pytest` | **369 passed**, 2 skipped (opt-in live-model and load tests), 8 min 21 s |
| Backend static checks | `uv run ruff format --check . && uv run ruff check . && uv run mypy` | Clean (mypy strict, 236 files) |
| Frontend static checks and build | `pnpm format:check && pnpm lint && pnpm typecheck && pnpm build` | Clean |
| Accessibility (WCAG 2.2 AA, axe-core) | `pnpm exec playwright test --project=a11y` | `/` and `/docs`: no serious or critical issues |
| Production smoke | All 100 `GET` API routes called signed-out | Clean statuses (401/403/404); no 5xx |
| CI | GitHub Actions `ci.yml` on every push | Passing |
| Dependency and secret scans | `pnpm audit --prod`, `pip-audit`, secret scan | Clean |

## What the backend suite proves

| Area | Tests |
|---|---|
| Tenant isolation and schema rules (RLS on every table, composite keys) | `security/test_tenant_isolation.py`, `test_schema_conventions.py` |
| Authentication and route protection | `test_tokens.py`, `security/test_route_auth.py`, `security/test_workspace_access.py` |
| Full case lifecycle: status model, approvals, separation of duties, readiness, decline, **acceptance**, **completion gate**, reopen, split, follow-through | `security/test_cases.py`, `security/test_case_lifecycle.py`, `test_case_state_properties.py` |
| **Idempotent creates** (same key once; different payload rejected) | `security/test_idempotency.py` |
| Simulator writes nothing | `test_simulation.py` |
| AI: citations validated, injection inert, restricted evidence never reaches a member, abstention | `intelligence/test_analysis.py`, `test_copilot.py`, `test_ask.py`, `test_handover.py` |
| Memory Replay, meetings, Autopilot, rehearsal, **evidence strength** | `intelligence/test_memory_replay.py`, `test_meetings.py`, `test_autopilot.py`, `test_rehearsal.py`, `test_brief_strength.py` |
| Integrations: GitHub evidence and webhooks, Linear, Notion, Slack, **incremental sync window** | `security/test_github_evidence.py`, `test_linear.py`, `test_notion.py`, `test_slack.py`, `test_sync_checkpoint.py` |
| Roles: read-only roles refused on writes; public roles table matches the registry | `test_new_features_access.py`, `test_role_docs.py` |
| Sample and judges' workspaces | `test_sample_workspace.py`, `test_judges_seed.py` |
| Rate limits, pagination, imports, email, jobs | `security/test_rate_limits.py`, `test_pagination.py`, `test_imports.py`, `test_email.py`, `test_stalled_jobs.py` |

## Browser journeys

| Spec | Covers | How it runs |
|---|---|---|
| `e2e/public.spec.ts` | Landing, docs, protected-route redirects | CI, no account |
| `e2e/a11y.spec.ts` | WCAG 2.2 AA on `/` and `/docs` | CI, no account |
| `e2e/smoke.spec.ts`, `e2e/round3.spec.ts` | Sign in, sample workspace, the three improvements end to end | Signed in through the one-click sample Owner account: 18 of 18 pass (smoke and round3) |
| `e2e/beyond.spec.ts` | Autopilot, meetings, Ask Relay, decision log, expertise, plan, rehearsal | Signed in the same way; all pass (26 of 26 across the signed-in suites) |

More detail, including the failure cases exercised for each journey:
[`Documentation/5-testing-and-quality/testing-notes.md`](testing-notes.md).
