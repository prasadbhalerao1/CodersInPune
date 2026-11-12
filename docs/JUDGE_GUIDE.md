# Relay: guide for judges

**Live product:** <https://relay-continuity-nine.vercel.app> · **Ten-minute walkthrough:**
[README → For judges](../README.md#for-judges) · **Everything else:** [docs index](README.md)

## The problem

Every team has work that only one or two people really understand: the deploy pipeline, the
vendor contract renewal, the quarterly compliance export. When one of those people resigns,
goes on leave or moves team, three things usually happen:

1. Nobody has a complete list of what that person was accountable for.
2. The context behind the work (why the canary exists, which runbook is outdated, what was
   decided in which thread) is spread across GitHub, Linear, Notion and people's heads.
3. The handover is a document written in the last week of notice, read once, and never
   checked against what actually changed hands.

The tools teams already use each hold a piece of this. A catalogue knows which team owns a
service, a wiki knows what was written down, an issue tracker knows the history of each
ticket, and HR software knows the leaving date. None of them answers *"if Arjun is away for
two weeks, what breaks, who should cover, and did the handover actually happen?"* See the
[competitive analysis](competitive-analysis.md) for the products we compared.

## What Relay does

Relay keeps one record of **who is accountable for what** (people and teams, primary owners
and backups, any kind of work), attaches the **evidence** behind that work from the tools
the team already uses, and moves ownership through **reviewed, audited handovers**. AI drafts
and answers, always with citations it cannot invent; people decide.

### The continuity lifecycle

The three Round 3 improvements are steps of one journey, not separate features:

```
 Investigate history ─► Simulate absence ─► Choose a successor ─► Create the handover case
  (Memory Replay)        (What If?)          (What If? candidates,   (pre-filled from the
                                              overload, readiness)    scenario)
        ▲                                                                   │
        │                                                                   ▼
 Verify continuity ◄── Execute ◄── Acknowledge ◄── Approve ◄── Prepare the brief
 (separation of duties,  (ownership     (recipient    (version-     (Handover Copilot:
  ownership history,      changes        next steps)   specific)     coverage, Q&A,
  audit trail)            applied)                                   version compare)
```

Each arrow is a link in the product:

| From | To | How the product connects them |
|---|---|---|
| Responsibility | Memory Replay | **Memory replay** button on every responsibility |
| Person | What If? | **What if … is unavailable?** on every person |
| What If? result | Case | **Plan a real handover** opens the case form with the person and case type pre-selected |
| Case | Brief | **Capsules** tab; the brief is built from the case's analysis and interview |
| Brief | Memory Replay | **Open memory replay** under *Where this work came from* |
| Brief coverage gap | Interview | **Asking the current owner in the handover interview** link |
| Acknowledged brief | Recipient work | **Next steps**: open tasks, inherited responsibilities with history links, case status |
| Executed case | Verification | Separation-of-duties check on completion; ownership history per responsibility |
| Executed case | Follow-through | Per responsibility: settled, settling in or check in, with a link back to Memory Replay |
| Insights | What If? | **What if … is away?** on every person in Key-person exposure |

## Why the approach matters

- **Deterministic where it decides, generative where it explains.** Risks, readiness,
  simulation and overload are rules you can read on the page. AI writes drafts, chapters and
  answers; every AI statement must cite evidence that Relay validates, or it is dropped.
- **AI never holds write access.** It cannot change ownership, approve, acknowledge or edit
  source records. Those are human actions with audit events.
- **Permissions apply before retrieval.** Evidence a viewer may not see is removed before any
  model sees it, and omissions are counted on the page, not silently hidden.
- **Tenant isolation is enforced by PostgreSQL**, not only by application code: forced
  row-level security, a restricted application role, and composite tenant foreign keys,
  checked by tests that inspect the schema.

## Implementation evidence

Every row names code you can open and tests that fail if the behaviour breaks. Test paths are
relative to `backend/tests/` unless they start with `e2e/` (Playwright, in `frontend/`).

| Product commitment | Implemented behaviour | Code | API | Tests |
|---|---|---|---|---|
| Ownership with backups | Primary, co-owner and backup assignments for people and teams; ownership history | `relay/catalog/service.py` | `/responsibilities/{id}/assignments` | `security/test_catalog.py`, `e2e/smoke.spec.ts` |
| Risks from rules | No owner, no backup, single holder, stale knowledge; each risk shows its rule | `relay/risks/` | `/risks` | `security/test_risk_lifecycle.py` |
| Audited handover cases | Plan → approve → execute → verify, with separation of duties for critical work | `relay/continuity/lifecycle.py`, `workflow.py` | `/cases/{id}/submit`, `/execute`, `/complete` | `security/test_case_lifecycle.py`, `test_case_state_properties.py`, `e2e/smoke.spec.ts` (transfer end to end) |
| Memory Replay | Merged GitHub, Linear, Notion and Relay events per responsibility; filters; replay; links; pages of 200 | `relay/intelligence/memory.py`, `responsibilities/[responsibilityId]/timeline/` | `GET /responsibilities/{id}/timeline` | `intelligence/test_memory_replay.py` (12), `e2e/round3.spec.ts` |
| Inferred chapters and history Q&A | Chapters labelled *Inferred*; invented event references dropped; answers cite events or say not found | `relay/intelligence/memory.py` | `…/timeline/narrative`, `…/timeline/questions` | `test_narrative_cites_events_and_drops_invented_ones`, `test_history_questions_cite_events_or_say_not_found` |
| What If? simulation | Read-only, deterministic impact per responsibility, deadlines in the window, readiness | `relay/continuity/simulation.py` | `POST /simulation` | `test_simulation.py` (12), `e2e/round3.spec.ts` |
| Cover candidates and overload | Candidates from recorded links, each simulated; overload when load ≥ max(2× typical, typical + 3) | `relay/continuity/simulation.py` | `/simulation/candidates` | `test_candidates_already_carrying_a_lot_are_flagged_as_overloaded` |
| Handover Brief | Fixed sections; each statement labelled Fact / Rule / AI inference with evidence; recipient-specific audience | `relay/intelligence/capsules.py` | `/cases/{id}/capsules`, `/ai/capsules/{id}` | `test_handover.py`, `test_brief_uses_the_committed_sections` |
| Brief coverage | Which in-scope responsibilities have a cited statement; critical gaps first | `capsules.py::_coverage`, `capsules/[capsuleId]/coverage.tsx` | `GET /ai/capsules/{id}` (`coverage`) | `test_interview_capsule_approval_and_acknowledgement` |
| Approval invalidation | Any edit creates a new version needing approval; acknowledgement is per version | `capsules.py::edit/approve/acknowledge` | `PATCH/POST /ai/capsules/{id}` | `test_handover.py` |
| Changed or withdrawn sources | Statements citing a changed source are flagged; withdrawn sources drop out and are counted | `capsules.py::view` | `GET /ai/capsules/{id}` | `test_handover.py`, `security/test_knowledge.py` |
| Honest AI states | Running, slow, stalled, failed; stalled runs retired before a retry; no duplicate runs | `capsules.py::_generation/_retire_stalled` | `POST /cases/{id}/capsules` | `test_a_stalled_ai_draft_is_reported_and_can_be_retried`, `test_stalled_jobs.py` |
| Copilot Q&A | Answers only from authorised brief evidence; invented or missing citations rejected; *Not in the evidence* otherwise | `relay/intelligence/copilot.py` | `POST /ai/capsules/{id}/questions` | `intelligence/test_copilot.py` (8) |
| AI off | Labelled search results and rule-based briefs; nothing breaks | gateway and fallbacks | — | `test_without_ai_the_reply_is_a_labelled_search`, `test_narrative_without_ai_or_events_says_why` |
| Prompt-injection resistance | Evidence text treated as data; restricted data never reaches the model for that viewer | `relay/intelligence/evidence.py`, `validate.py` | — | `test_injection_in_evidence_does_not_leak_restricted_data`, `test_eval.py` |
| Key-person exposure | People who are the only holder of work, critical first, with a link to simulate their absence; managers and auditors only | `relay/insights/service.py::_key_people` | `GET /insights` (`key_people`) | `test_key_people_are_the_only_holders_of_work_ranked_by_criticality`, `test_insights_are_for_managers_and_auditors_only` |
| Follow-through after a handover | Per transferred responsibility: holder recorded, reviewed or recorded activity since, tasks closed; settled / settling in / check in; measures the work, not the person | `relay/continuity/follow_through.py`, `cases/[caseId]/follow-through.tsx` | `GET /cases/{id}/follow-through` | `test_follow_through_shows_whether_each_transfer_took_hold`, `e2e/smoke.spec.ts` |
| Guidance and tutorials | Per-user switch; tours unlock from workspace state; resume/replay/reset | `relay/guidance/`, `components/tour.tsx` | `GET/PATCH /guidance` | `test_guidance.py` (4), `e2e/round3.spec.ts` |
| Integration readiness | Ready only after first sync drains; retrying and attention states from the outbox and connector health | `relay/guidance/service.py` | `GET /guidance` | `test_guidance.py` (Linear syncing → retrying → ready → attention) |
| Connectors | GitHub App, Linear and Notion, read-only, encrypted credentials, signed webhooks | `relay/integrations/` | `/integrations/*` | `security/test_github_evidence.py`, `test_linear.py`, `test_notion.py`, `e2e/public.spec.ts` |
| Tenant isolation | Forced RLS, restricted role, composite tenant FKs | `migrations/`, `relay/shared/` | all | `security/test_tenant_isolation.py`, `test_schema_conventions.py`, `test_workspace_access.py` |
| Permissions | Registry-based `authorize()` / `visible()` in every service | `relay/policy/permissions.py` | all | `security/test_permissions_audit_jobs.py`, `test_route_auth.py` |
| Audit | Append-only audit events in the same transaction | `relay/audit/` | `/audit-events`, `/audit/export.csv` | `security/test_permissions_audit_jobs.py`, `test_briefing_audit.py` |
| Reliable jobs | Transactional outbox, idempotent handlers, stalled-job recovery | `relay/jobs/` | — | `test_stalled_jobs.py`, `test_job_correlation.py` |

## The five judging criteria

| Criterion | What to look at in the product | Where it is documented | What proves it |
|---|---|---|---|
| **Completeness (25)** | The full lifecycle above on the sample workspace: replay → simulate → plan → brief → approve → acknowledge → execute → verify | [README walkthrough](../README.md#for-judges), [improvements delivered](round3/improvements-delivered.md) | 23 browser journeys from the landing page, including a transfer case end to end |
| **Improvements (20)** | The three Round 3 features and how they hand off to each other; overload flags, brief coverage, version compare, recipient next steps | [improvements delivered](round3/improvements-delivered.md), [competitive analysis](competitive-analysis.md) | `test_simulation.py`, `test_memory_replay.py`, `test_copilot.py`, `test_handover.py` |
| **Reliability (20)** | Honest AI states and retry; *Not in the evidence*; changed/withdrawn sources flagged; integration states that wait for real syncs | [testing notes](round3/testing-notes.md), [architecture → reliability](architecture.md) | Backend suite on real PostgreSQL as the restricted role; failure-case tests listed in testing notes |
| **Usability (20)** | Learn Relay tours, the setup checklist, the guidance switch, next-step text on every case, keyboard search (Ctrl K), phone layout | [README](../README.md#for-judges) | `e2e/round3.spec.ts` (guidance), `e2e/smoke.spec.ts` (phone navigation, command menu) |
| **Documentation and roadmap (15)** | This guide, the docs index, API reference with OpenAPI, limitations and roadmap | [docs index](README.md), [README → Roadmap](../README.md#roadmap) | `docs/openapi.json` is generated from the code |

## Honest limits

- The sample workspace's GitHub, Linear and Notion records are **synthetic** and labelled as
  such; live connectors are read-only and tested against faked provider APIs.
- AI prose needs a configured model; without one Relay falls back to labelled search and
  rule-based briefs.
- Brief coverage matches statements to responsibilities by name. It can miss a statement
  that refers to a responsibility indirectly, so it shows a gap to check, never a verdict.
- The nightly backup workflow needs a dedicated backup role (see
  [README → Known limitations](../README.md#known-limitations)); Neon's point-in-time restore
  protects production meanwhile.
- The free API host sleeps when idle; the first request can take up to a minute.
