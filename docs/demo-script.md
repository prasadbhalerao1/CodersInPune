# Demo script (about 8 minutes)

This walks through the core loop on a synthetic organisation:

1. find the risk;
2. reconstruct the context with evidence;
3. hand over with review;
4. acknowledge;
5. prove it was governed.

Everything shown is fictional.

## Setup (once)

```sh
docker compose up -d --wait
cd backend && uv run alembic upgrade head
uv run relay-api            # terminal 1
uv run relay-worker         # terminal 2
cd ../frontend && pnpm build && pnpm start   # terminal 3
```

1. Sign in at `http://localhost:3000` and copy your WorkOS user ID. It's on your profile, or in the `sub` of the access token.
2. Seed the demo organisation:

   ```sh
   cd backend && uv run relay-demo-seed --owner <your WorkOS user id>
   ```

   This creates **Northwind Labs (demo)**: 8 people, 3 teams, a responsibility catalogue with gaps, conflicting procedures, connector problems, and three cases (completed, active and planned).

Optional: set `RELAY_LLM_PROVIDERS` and a key in `backend/.env` to show AI drafts next to
the deterministic findings. The demo works without them.

## 1. The problem, in one screen (1 min)

- **Landing page → How it works.** The walkthrough plays the loop.
- **Open Northwind Labs (demo).** The overview shows coverage gaps and open risks. Point out:
  - a critical responsibility with no backup;
  - an asset nobody stewards;
  - a stale Linear connector and a failing GitHub connector (Integrations → Health).
- **Risks → open the high-severity risk.**
  - It explains why the risk exists and recommends an action.
  - **Assign** it to a member.
  - **Open a case to fix this**, which creates a transfer case scoped to that responsibility.
  - Say: *Relay finds the gap with rules, not guesses.*

## 2. A real departure: "Arjun Rao is leaving Platform" (3 min)

- **Cases → Arjun Rao is leaving Platform.**
  - **Overview:** state, due date, readiness, and a blocker with an owner and escalation time.
  - **Impact:** every responsibility Arjun holds, with criticality and coverage after he leaves.
- **Analysis.**
  - Findings are labelled **Fact / Rule / AI inference / Conflict / Missing evidence**, each with a citation chip.
  - Expand a citation to show its source, revision and time.
  - Show the **conflict**: two deploy runbooks that disagree, both shown, with no "newest wins".
  - Show **missing evidence**: no rollback procedure, which became a targeted interview question.
- **Interview.** Answer a question as the outgoing owner would, then propose it as knowledge. The new knowledge stays unverified until a steward verifies it.
- **Proposals.** Accept one task and reject one with a reason. Rejected proposals aren't proposed again.
- **Tasks and readiness.** A mandatory readiness check blocks completion until it's met or waived with a reason. Try to complete the case and show the refusal.

## 3. The handover capsule (2 min)

- **Handover → the capsule for you.**
  - It is role-specific, versioned, and **approved by a second person**.
  - Every statement cites its source.
  - **Omissions** list what you can't see (managers-only evidence) without revealing it.
- **Acknowledge receipt.** Acknowledgement is recorded per version.
  - An edit would create a new version that needs approval and acknowledgement again.

## 4. Trust and governance (1.5 min)

- **Audit log.** Every step just taken (assign, case opened, proposal decisions, approval, acknowledgement) appears with actor and time. Filter by category, then download the audit log as CSV.
- **Settings → Roles & permissions.** Roles are scoped, and a denial names the roles that would be allowed.
- **Settings → Data & privacy.** Covers:
  - what Relay reads and why;
  - export;
  - retention;
  - ownership transfer;
  - deletion with a 30-day grace period.
- **Agents.** The kill switch and each capability toggle, with run history, tokens, cost and acceptance rate.
- **Integrations → Health.** Pause a connector. Read-only by default; issue creation needs approval of the exact content.

## 5. Close (30 s)

- **Insights → Trends.** Handover cycle time, readiness completion and knowledge-gap resolution, each with its definition, denominator and limitations.
- Say: *Rules find the gaps, evidence rebuilds the context, people approve every change, and the audit log proves it.*

## If something goes wrong

| Symptom | Fix |
|---|---|
| "Not configured" on AI | Expected without a provider; deterministic findings still show |
| Jobs not moving (analysis stays queued) | Start `uv run relay-worker` |
| Seed fails partway | Re-run it. Each run creates a new workspace. Delete the partial one in Settings → Data & privacy |
