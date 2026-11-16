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
| Incremental GitHub sync with checkpoint, overlap and daily reconcile | Verified | `test_sync_checkpoint.py`; migration 0048 applied |
| Connector health in one query; reconnect link | Verified | Integration health tests pass |
| One sign-in route; one-click role accounts; no "demo" in any URL | Verified | Production `/sign-in?as=wizard` falls back to the hosted sign-in; role preview tests pass |
| Judges' per-role accounts seeded in production | Verified | `Seed judges` workflow run, success |
| Submission docs (architecture, matrix, traceability, security, performance, tests, next steps, roadmap) | Verified | `docs/submission/` |

## Checks run

| Check | Result |
|---|---|
| `uv run pytest` | 363 passed, 2 skipped |
| `ruff`, `mypy` | Clean |
| `pnpm format:check`, `lint`, `typecheck`, `build` | Clean |
| `migrate.yml` (0046 to 0048) | Success |
| Production smoke (100 signed-out GET routes) | No 5xx |

## Waiting on the owner

| Item | Why |
|---|---|
| Click *Owner* in the home page's "Sign in as any role" once on production | Confirms one-click sign-in end to end (and that WorkOS Radar doesn't ask for a code) |
| Connect Slack in the production workspace | The webhook URL is a secret and is pasted by the owner |
| Run the signed-in browser journeys (`pnpm e2e:login`, then the `round3` and `beyond` projects) | The saved test login has expired |
| Rotate secrets after judging | Some passed through development chats |
