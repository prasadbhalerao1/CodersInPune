# Relay: Round 3 execution state

Last updated: 16 Nov 2026. Status values: **Verified** (tested and checked), **Implemented**
(built, covered indirectly), **Blocked** (waiting on something outside the code).

## Final build: what changed and its status

| Work | Status | Evidence |
|---|---|---|
| Incoming owner accepts ownership (per scope item, state-checked, idempotent, cleared on recipient change or decline) | Verified | `security/test_case_lifecycle.py`; migration 0046 applied in production |
| Completion gate: open tasks, readiness and acceptance must be resolved; cover that ends early is exempt from the task check | Verified | `security/test_cases.py`, `test_case_lifecycle.py`, `test_briefing_audit.py` |
| Evidence strength on handover briefs (label from fresh, cited sources and coverage) | Verified | `intelligence/test_brief_strength.py` |
| "Who to ask" from ownership records; Copilot follow-up suggestions | Implemented | Rendered on the brief page; uses existing tested data |
| Memory Replay date-range filter | Implemented | Client-side filter alongside the existing tested filters |
| Idempotent creates (cases, tasks, responsibilities, meetings) with one key per submission intent | Verified | `security/test_idempotency.py`; migration 0047 applied |
| Incremental GitHub and Linear sync with checkpoint, overlap and daily reconcile | Verified | `test_sync_checkpoint.py`; migrations 0048 and 0049 applied |
| Idempotent creates extended to people, assets and knowledge | Verified | `security/test_idempotency.py` |
| What If? pinned scenarios (up to three, compared side by side) | Implemented | Server-rendered from the existing tested simulation; nothing is written |
| Memory Replay filters (including the date range) shareable by URL | Implemented | Client filters mirrored into the URL |
| One shared action helper; case DTOs moved to `continuity/schemas.py` | Verified | Full suite passes unchanged |
| Judge sign-in card with copyable credentials; one-click sign-in confirmed in production | Verified | `/sign-in?as=owner` redirects to `/workspaces` |
| Interface polish: pointer cursors, animated dropdowns, landing figures never freeze | Implemented | Checked in the browser |
| Nightly encrypted backup with automatic restore drill, through a read-only `relay_backup` role | Verified | `Backup` workflow run on 16 Nov: restore at schema 0049, forced RLS on every tenant table |
| Judge role accounts linked to their sample people; coordinators can record acceptance | Verified | Team manager (Dev Patel) sees *Accept ownership* in production; `security/test_case_lifecycle.py` |
| Connector health in one query; reconnect link | Verified | Integration health tests pass |
| One sign-in route; one-click role accounts; no "demo" in any URL | Verified | Production `/sign-in?as=wizard` falls back to the hosted sign-in; role preview tests pass |
| Judges' per-role accounts seeded in production | Verified | `Seed judges` workflow run, success |
| Submission docs (architecture, matrix, traceability, security, performance, tests, next steps, roadmap) | Verified | `docs/submission/` |

## Checks run

| Check | Result |
|---|---|
| `uv run pytest` | 365 passed, 2 skipped |
| `ruff`, `mypy` | Clean |
| `pnpm format:check`, `lint`, `typecheck`, `build` | Clean |
| `migrate.yml` (0046 to 0049) | Success |
| Production smoke (100 signed-out GET routes) | No 5xx |

## Waiting on the owner

| Item | Why |
|---|---|
| Connect Slack in the production workspace | The webhook URL is a secret and is pasted by the owner |
| Run the signed-in browser journeys (`pnpm e2e:login`, then the `round3` and `beyond` projects) | The saved test login has expired |
| Rotate secrets after judging | Some passed through development chats |
