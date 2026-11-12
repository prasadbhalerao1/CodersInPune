# Round 3 testing notes

How Relay was tested for the final round: the main journeys, the failure cases, permissions
and the reliability work. Everything below runs against real PostgreSQL (never SQLite) as
the restricted `relay_app` role, so row-level security is exercised on every query.

## At a glance

| Suite | Where | Count | Result |
|---|---|---:|---|
| Backend (API, services, security, AI validation) | `backend/tests` | 297 (+2 opt-in) | All pass (2026-11-12, 7 min) |
| of which Round 3 features | `test_simulation.py`, `intelligence/test_memory_replay.py`, `intelligence/test_copilot.py`, `intelligence/test_handover.py`, `test_guidance.py`, `test_sample_workspace.py` | 45 | All pass |
| Browser journeys, public (no account) | `frontend/e2e/public.spec.ts` | CI | Pass |
| Browser journeys, real account | `frontend/e2e/smoke.spec.ts`, `frontend/e2e/round3.spec.ts` | 12 + 5 | All pass locally (2026-11-12) |
| Static checks | ruff, mypy (strict), ESLint, TypeScript, Prettier | | Clean |

The two opt-in tests call a live model (`RELAY_EVAL_LIVE=1`) and measure API latency at
1,000 responsibilities (`RELAY_PERF=1`).

## Main journeys

Each journey starts at the landing page and clicks through the app the way a judge would
(`frontend/e2e/round3.spec.ts`), on a freshly seeded sample organisation.

1. **Landing → sample workspace.** The Overview leads with "A handover is waiting for you"
   and the continuity-health panel.
2. **Memory Replay.** Filter by Incident (only incidents remain in the event list), play
   and pause the replay, inspect an event (shown as a Fact with its source), read or
   generate the AI explanation, and ask a question about the history.
3. **What If?** From a person's profile: "What if Arjun is unavailable?", two weeks,
   run, open "Why it is affected", compare cover candidates and simulate with Dev. Then
   open the real responsibility and confirm Dev is **not** an owner: the simulation changed
   nothing.
4. **Guidance.** Switch automatic guidance off (the Overview shows no prompts), start a
   tour from Learn Relay anyway, skip at step 2, resume at step 2, finish, see it marked
   for replay, switch guidance back on (the Overview offers the next tour).
5. **Handover Copilot.** Open the handover, ask an answerable question (cited answer) and
   an unanswerable one ("Not in the evidence"), then follow the link into Memory Replay.

The existing smoke journey (`smoke.spec.ts`) covers the Round 2 workflow end to end:
workspace, people, responsibilities, knowledge, a transfer case through approval and
execution, temporary cover, command menu, automations, mobile navigation and workspace
deletion.

## Failure cases

| Situation | What the person sees | Test |
|---|---|---|
| AI not configured, switched off, over budget or failing | Copilot returns labelled search results ("Search results, not an answer") or "Not in the evidence"; Memory Replay says why there is no explanation; the simulator and timeline are deterministic and unaffected | `test_without_ai_the_reply_is_a_labelled_search`, `test_narrative_without_ai_or_events_says_why`, `test_provider_failure_keeps_the_deterministic_analysis` |
| The model cites a source that does not exist | Not shown as an answer; the run is flagged "needs human review" | `test_invented_citations_are_never_served_as_answers`, `test_narrative_cites_events_and_drops_invented_ones` |
| The model answers without citing anything | Rejected; shown as "Not in the evidence" with the closest sources | `test_uncited_found_answers_are_rejected` |
| A source contains instructions ("ignore previous instructions…") | Treated as data; nothing is executed and restricted content does not leak | `test_injection_in_evidence_does_not_leak_restricted_data`, `test_model_output_is_validated_injection_is_inert_and_restricted_stays_restricted` |
| A cited source is withdrawn or edited later | Withdrawn sources drop out; edited ones are marked "Source changed since" | `test_cancel_kill_switch_and_withdrawn_evidence`, `test_evidence_edited_after_the_analysis_is_flagged_as_changed` |
| History grows after the AI reading was written | "New events arrived after this reading was written" with Regenerate | `test_narrative_is_stored_filtered_per_viewer_and_marked_outdated` |
| A connector is partial (lost access, failed sync) | Shown on the timeline as "history may be incomplete", never as "nothing happened" | sample workspace's failing GitHub connector |
| Someone holds nothing | Simulator says so; score 100 | `test_score_is_explained_and_full_for_someone_holding_nothing` |
| Bad input (unknown ids, zero-day absence, same person as backup, too-short questions, extra fields) | 404 / 422 with a plain message | `test_other_workspaces_and_bad_input_are_rejected`, `test_duration_flags_work_due_while_away`, `test_only_the_recipient_and_editors_can_ask` |
| Too many sample workspaces or AI questions | Rate limited with a clear message | `test_samples_are_rate_limited_per_user` |
| The AI draft never finishes (worker down, provider hang) | "Taking longer than expected" after 2 minutes; after the 15-minute limit "did not finish in time" with a retry; the rule-based brief stays usable; retrying never queues a duplicate | `test_a_stalled_ai_draft_is_reported_and_can_be_retried` |
| An integration is connected but its sync is queued, failing or broken | Shown as syncing, retrying or needs attention; tours that need its data stay locked until the first sync finished and no sync is pending | `test_an_integration_is_ready_only_after_its_sync_finishes` |
| Guidance switched off, tour interrupted, bad tour ids | No prompts, tutorials still start, resume at the saved step, 422 for unknown ids or fields | `test_switch_progress_resume_and_reset` |

## Permissions

| Rule | Test |
|---|---|
| Only owners, admins and continuity managers can simulate (`continuity.simulate`) | `test_only_managers_can_simulate` |
| Another workspace's people, responsibilities and handovers return 404 | `test_other_workspaces_and_bad_input_are_rejected`, `test_outsiders_cannot_read_a_timeline`, `test_only_the_recipient_and_editors_can_ask` |
| Only the recipient and the handover's editors can ask the Copilot or read its thread | `test_only_the_recipient_and_editors_can_ask` |
| Members never get managers-only evidence: not in the Copilot's pool, not in timelines, not in stored AI readings | `test_answer_cites_the_handover_evidence`, `test_members_see_only_workspace_audience_sources`, `test_narrative_is_stored_filtered_per_viewer_and_marked_outdated` |
| The simulation writes nothing (checked with a SQLAlchemy cursor listener), and neither does reading a timeline | `test_simulation_writes_nothing`, `test_timeline_reads_without_writing`, browser journey 3 |
| Every new table has tenant RLS, composite keys and explicit grants | `tests/security/test_schema_conventions.py` (covers migration 0040) |
| Every route rejects anonymous requests | `tests/security/test_route_auth.py` |

## Reliability work in this round

- **Interactive AI calls are recorded**: every Copilot answer and Memory Replay reading is an
  agent run with tokens and cost, counted against the workspace's monthly budget, visible
  on the AI agents page, and stopped by the kill switch.
- **Stored readings**: Memory Replay opens without a model call and reports when it is out
  of date, instead of calling the model on every page view.
- **Provider cooldowns**: tests reset the process-wide provider cooldown so one test's
  simulated quota error cannot fail another.
- **Simulator correctness**: work in a responsibility that a backup covers no longer counts
  as stalled; candidates connected to the uncovered work are ranked first.
- **Found by clicking through as a user** and fixed: on People, the department and manager
  controls covered the person's name so it couldn't be clicked (this was the "What If?"
  journey timeout); the Workspaces page raised a prerender error from per-request keys; a
  tour anchored to the hidden copy of a previously visited page. Earlier: the landing page showed the app
  sidebar and raised a prerender error; the recipient's handover was hidden behind the last
  tab; the sidebar scrolled away on long pages; anchors scrolled under the sticky header;
  the local dev script could stall on Windows when a tool printed Unicode.

## How to run

```bash
cd backend && uv run pytest                                  # needs `docker compose up -d`
cd frontend && pnpm exec playwright test --project=public    # no account needed
cd frontend && pnpm e2e:login                                # once, real sign-in
cd frontend && pnpm exec playwright test --project=round3    # the judge journey
```

## Known gaps

- Browser journeys that need a real account are run locally, not in CI (they need a
  WorkOS session).
- The sample workspace's GitHub, Linear and Notion records are synthetic rows; live
  connector syncs are covered by the integration tests with faked provider APIs.
- AI answer quality beyond citation validity is measured by the 31-case evaluation set
  (`tests/intelligence/test_eval.py`) and spot checks, not by every test.
