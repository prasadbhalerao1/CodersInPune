# Relay: Round 3 submission pack

One page that maps the problem statement to the product, the code and the tests. Every row
can be checked on the sample workspace and in the repository.

## 1. Traceability: the required workflow

The problem statement asks for **Connect → Reconstruct → Verify → Review → Handover**.

| Stage | What the user does in Relay | Code | Tests |
|---|---|---|---|
| **Connect** | Connect GitHub (App), Linear and Notion read-only; Slack for sharing; or import a CSV | `relay/integrations/`, `relay/imports/` | `security/test_github_evidence.py`, `test_linear.py`, `test_notion.py`, `test_slack.py` |
| **Reconstruct** | Memory Replay of a responsibility's history; case analysis and **Handover Autopilot**; **meeting intelligence**; **Ask Relay**; **Decision log** | `catalog/timeline.py`, `intelligence/memory.py`, `runs.py`, `autopilot.py`, `meetings.py`, `ask.py` | `intelligence/test_memory_replay.py`, `test_analysis.py`, `test_autopilot.py`, `test_meetings.py`, `test_ask.py` |
| **Verify** | Rule-based continuity risks; readiness checks; the **What If?** simulator with its score working; **expertise map**; **code drift** on knowledge; follow-through after transfer | `risks/`, `continuity/simulation.py`, `search/service.py`, `catalog/drift.py`, `continuity/follow_through.py` | `test_simulation.py`, `test_expertise.py`, `test_code_drift.py`, `security/test_cases.py` (follow-through) |
| **Review** | Accept or reject every AI proposal with a reason; confirm or dismiss claims; review interview answers; approve a brief version (separation of duties) | `intelligence/service.py`, `capsules.py`, `continuity/workflow.py` | `intelligence/test_analysis.py`, `test_handover.py`, `security/test_permissions_audit_jobs.py` |
| **Handover** | Handover brief per recipient, with the Copilot answering from its evidence; acknowledgement; execution; **30/60/90 plan**; voice-capable exit interview | `intelligence/capsules.py`, `copilot.py`, `interviews.py`, `continuity/plan.py` | `intelligence/test_copilot.py`, `test_handover.py`, `test_continuation_plan.py` |

### Success criteria

| Criterion | How Relay meets it | Proof |
|---|---|---|
| **Traceable** | Every AI statement cites evidence; a citation of anything not given is removed and an uncited claim is dropped. Meeting items cite transcript lines; numbers show their working in the ⓘ. | `validate.py`, `ask.finalise`, `meetings._valid`; `test_analysis.py` (invented citations), `test_ask.py`, `test_meetings.py` |
| **Actionable** | Proposals become tasks, knowledge or readiness checks on acceptance; meeting actions become case tasks; plan steps become tasks; the simulator opens a pre-filled case. | `service.accept_proposal`, `meetings._apply`, `ai-actions.addPlanStepAction` |
| **Permission-aware** | Forced row-level security per tenant; `authorize()`/`visible()` in every service; restricted evidence never reaches a model for a viewer who can't see it. | `security/test_tenant_isolation.py`, `test_schema_conventions.py`, `test_ask.py` (managers-only knowledge hidden from a member) |

## 2. Feature inventory

| Area | Features |
|---|---|
| Accountability | Responsibilities for any kind of work, primary/backup/temporary owners (people or teams), ownership history, review cadence, dependencies, assets |
| Evidence | GitHub, Linear, Notion connectors; CSV import; knowledge with stewardship, versions, disputes, classification; code drift |
| Intelligence | Case analysis (4 reviewers), Handover Autopilot, exit interview (voice), handover brief per recipient, Copilot (streamed), Memory Replay narrative, meeting intelligence, Ask Relay, decision log |
| Continuity | Risks with rules, continuity debt, insights, key-person exposure, expertise map, What If? simulator with candidates, overload and a downloadable report |
| Handover | Cases (transfer, temporary cover, departure), approvals with separation of duties, tasks, readiness, acknowledgement, follow-through, 30/60/90 plan, Slack sharing |
| Trust | WorkOS sign-in, roles and permissions registry, append-only audit, data export and deletion, encrypted integration secrets, AI budget and kill switch |
| Experience | Sample workspace (with meetings), guided tours, ⓘ on every number, Ctrl K search, product guide at `/docs`, phone layout, dark mode |

## 3. Quality scorecard

| Check | Result | How to reproduce |
|---|---|---|
| Backend tests (real PostgreSQL, restricted role) | 336 passed, 2 opt-in skipped (16 Nov 2026) | `cd backend && uv run pytest` |
| Static checks | ruff, mypy strict, ESLint, TypeScript, Prettier: clean | see README → Checks |
| Production build | `pnpm build` succeeds | `cd frontend && pnpm build` |
| AI safety evaluation | 31 labelled cases in CI, 0 unsupported claims stored, 0 permission leaks | `backend/tests/intelligence/test_eval.py` |
| Browser journeys | Public and signed-in journeys from the landing page | `frontend/e2e/` |
| Tenant isolation and schema conventions | Enforced by tests that inspect the live schema | `tests/security/` |

## 4. Disclosures

- **Libraries and services:** listed in `backend/pyproject.toml` and `frontend/package.json`;
  hosted on Render, Vercel and Neon; sign-in by WorkOS; AI through Google Gemini (with Groq,
  NVIDIA and local Ollama as alternatives); optional Slack incoming webhooks.
- **AI assistance:** AI coding assistants were used throughout development. How AI is used
  inside the product, and what it may never do, is in [`docs/ai.md`](../ai.md).
- **Team and contributions:** see the README, *Team and contributions*.
