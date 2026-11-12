# Round 3: the three committed improvements, delivered

In Round 2 we committed to three improvements ([docs/improvements.md](../improvements.md)).
All three are built, tested in CI against real PostgreSQL, and usable on the live
deployment with the sample workspace. This page shows where each one is, how to see it,
and what proves it works. Where we stopped short of the commitment, it says so.

To see all three in about five minutes: sign in, click **Create sample workspace** on
Workspaces, then follow the "Try it" steps below. The sample organisation ships with a
year of synthetic GitHub, Linear and Notion history so every feature has something to show.

---

## 1. AI Handover Copilot

**What the incoming owner gets.** The handover brief now uses the committed sections
(What you now own, In-flight work, Decisions already made, Knowledge gaps and open
questions, Risks and conflicts, Recommended first steps) and marks each statement whose
source changed after the brief was written. Beside it, **Ask about this handover** answers
questions using only the sources behind that brief, citing them.

**Try it.** Cases → *Arjun Rao is leaving Platform* → Capsules → *For you*. Ask
"How should I deploy payments-api?". The answer cites the runbook and points out that an
older runbook says the opposite.

**How it stays honest.**

| Rule | Where it is enforced | Test |
|---|---|---|
| Only evidence the asker may see is in the pool (managers-only sources never reach a member) | `intelligence/copilot.py::_evidence` | `test_answer_cites_the_handover_evidence`, `test_injection_in_evidence_does_not_leak_restricted_data` |
| An answer is served as an answer only if it cites evidence that exists in the pool | `copilot.py::ask` | `test_uncited_found_answers_are_rejected` |
| A citation to a source that doesn't exist is treated as invented: no answer, run flagged for human review | `copilot.py::ask` | `test_invented_citations_are_never_served_as_answers` |
| "Not in the evidence" is a real reply, with the closest sources to check | `copilot.py::ask` | `test_unanswerable_questions_get_a_cited_not_found` |
| With AI off, over budget or failing, the reply is a keyword search, labelled as such | `copilot.py::search`, `intelligence/instant.py` | `test_without_ai_the_reply_is_a_labelled_search` |
| Only the recipient and the handover's editors can ask or read the thread | `capsules._load` | `test_only_the_recipient_and_editors_can_ask` |
| Answers are re-checked on every read: withdrawn sources drop out | `copilot.py::_views` | covered by the thread assertions above |
| The brief uses the committed sections | `intelligence/capsules.py::SECTIONS` | `test_brief_uses_the_committed_sections` |

Every question is audited (`ai.copilot_question`, identifiers only) and every model call
is recorded as an agent run with tokens and cost, so it counts against the workspace's
monthly AI budget and shows on the AI agents page. Storage: migration `0040`
(`intelligence.capsule_question`, tenant RLS, append-only for the app role).

**Versions, drafts and the recipient's next steps.** Every version is kept; **Compare**
shows the statements added and removed between any two versions, section by section. The
AI draft reports its state honestly (`running`, then "taking longer than expected" after
two minutes, `stalled` after the 15-minute run limit, or `failed`) instead of spinning;
editors can retry, stalled runs are closed first and a live draft is never duplicated
(`test_a_stalled_ai_draft_is_reported_and_can_be_retried`). After acknowledging, the
recipient sees their open tasks in the case, what they are taking over with links to its
history, the case status, and where to ask.

**Brief coverage.** Above the brief, every responsibility in the case's scope is listed as
*backed by evidence*, *mentioned without a source* or *not covered*, critical first, with a
link to the handover interview to close the gaps. The rule is deterministic: a statement
covers a responsibility when it names it, and is backed when it cites an active source.
Redacted or withheld statements don't count for a viewer who cannot see them
(`capsules.py::_coverage`, asserted in
`test_interview_capsule_approval_and_acknowledgement`).

---

## 2. "What If?" Continuity Simulator

**What a manager gets.** Pick a person; Relay recomputes, in memory, what would happen if
they were unavailable: which responsibilities lose their owner, which become new
single-person dependencies, which have no knowledge to hand over, what open work (Relay
tasks, GitHub pull requests and issues, Linear issues) would stall, and a readiness score
out of 100 that explains its own formula. Add a backup to see the gap close.

**Try it.** What-if simulator (sidebar) → choose *Arjun Rao* → Run. Readiness is about 55,
Production deployments is left with nobody. Then choose *Dev Patel* as backup: nothing is
left uncovered and the score rises.

| Commitment | Status | Test (`backend/tests/test_simulation.py`) |
|---|---|---|
| `GET /workspaces/{id}/simulation?person_id=&backup_id=&days=` | Done | all 11 |
| Correct impact for a person with known responsibilities | Done | `test_impact_of_removing_a_person` |
| A backup covering everything leaves `uncovered_responsibilities` empty | Done | `test_a_backup_covering_everything_leaves_nothing_uncovered` |
| Newly exposed single-person dependencies and undocumented work | Done | `test_exposed_risks_name_the_new_gaps` |
| Team-held responsibilities count only when the person is the team's last member | Done | `test_team_held_responsibility_is_affected_only_when_they_are_the_last_member` |
| 403 for non-managers (new permission `continuity.simulate`: owner, admin, continuity manager) | Done | `test_only_managers_can_simulate` |
| Inherits the caller's visibility; other workspaces return 404 | Done | `test_other_workspaces_and_bad_input_are_rejected` |
| **No write reaches the database** | Done: verified with a SQLAlchemy cursor listener | `test_simulation_writes_nothing` |
| Score explained and 100 when nothing is at stake | Done | `test_score_is_explained_and_full_for_someone_holding_nothing` |
| "Why is this affected?": reasons per responsibility, each read from a record, plus the assets it looks after | Done | `test_reasons_explain_why_each_responsibility_is_affected` |
| Absence duration: work falling due while the person is away is flagged | Done | `test_duration_flags_work_due_while_away` |
| Cover candidates by deterministic signals (planned recipient, existing role, team, department), each simulated and compared with "no replacement" | Done | `test_candidates_are_compared_against_nobody_stepping_in`, `test_sample_powers_the_round_three_features` |

Candidates are ranked first by whether they are connected to the work that would
otherwise have nobody, then by how many recorded links they have. A candidate who would hold
at least twice the workspace's typical load (and three more) is flagged as overloaded
(`test_candidates_already_carrying_a_lot_are_flagged_as_overloaded`). **Plan a real
handover** opens the case form with the person pre-selected: acting on a simulation is a
separate, authorised and audited step. There is no AI score;
the signals are shown next to each name. Entry points: the sidebar, the Overview's "Test
your readiness" card, and "What if … is unavailable?" on each person's profile.

The score is deliberately simple so a manager can argue with it: per affected
responsibility, weighted by criticality, cover is 60%, usable (non-stale) knowledge 25%,
and a second holder remaining 15%.

---

## 3. Project Memory Replay

**What a successor gets.** On any responsibility, **Memory replay** shows how the work got
here: ownership periods, merged pull requests, resolved issues, incidents, recorded
decisions with their rationale, and Notion edits, grouped by month, filterable by
category, and playable from the first event forward. Events that reference each other
("fixes #12", "PAY-103") are linked. **Explain this history** asks the AI to group events
into chapters and connect them; every chapter cites the events it rests on.

**Try it.** Responsibilities → *Production deployments* → **Memory replay** → press
**Replay history**, then **Explain this history**.

**Fact versus inference.** Every event is `factual`: its date and source come straight
from the record, and the category says how it was derived (the source's labels, words in
the title, or a default). Chapters and connections are `inferred` and labelled as such.
A chapter or link citing nothing, or an event that doesn't exist, is dropped and counted.

| Commitment | Status | Test (`backend/tests/intelligence/test_memory_replay.py`) |
|---|---|---|
| `GET …/responsibilities/{id}/timeline`, rebuilt from live data, nothing stored | Done | `test_timeline_is_factual_ordered_and_categorised` |
| Non-empty for the sample workspace's deploy pipeline | Done | `tests/test_sample_workspace.py::test_sample_powers_the_round_three_features` |
| `?category=bug_fix` returns only bug fixes | Done | `test_category_filter_returns_only_that_category` |
| Linked events | Done (factual links from references in titles) | `test_references_in_titles_link_events` |
| Members see only workspace-audience sources | Done | `test_members_see_only_workspace_audience_sources` |
| Non-members are refused | Done | `test_outsiders_cannot_read_a_timeline` |
| Read-only | Done: no writes during a timeline read | `test_timeline_reads_without_writing` |
| Inferred content always cites events; invented refs dropped | Done | `test_narrative_cites_events_and_drops_invented_ones` |
| Clear message when AI is off or there is nothing to explain | Done | `test_narrative_without_ai_or_events_says_why` |
| The reading is stored with the events it saw: the page opens without a model call, says when newer events exist, and never shows a member a chapter built on a source they can't see | Done | `test_narrative_is_stored_filtered_per_viewer_and_marked_outdated` |
| "Ask about this history": answers cite events, invented citations are refused | Done | `test_history_questions_cite_events_or_say_not_found` |

The page also shows a chapter axis (the project's span with chapters as bands and every
event as a dot), an event inspector (provenance, how the category was derived, related
events, the chapters citing it, a link to the source), and each handover brief links to
the memory replay of every responsibility it covers.

**Not done.** Commit-level history: Relay reads pull request and issue metadata, never
commits or code, by design. Historical state snapshots ("at this point there were N open
issues") are not shown: the sources don't let Relay establish past counts reliably, and we
would rather show nothing than an invented number. The timeline is per responsibility, not
per repository or asset.

---

## How the three connect

Memory replay shows how a responsibility got here → the simulator shows what breaks if its
owner is away and who could cover → "Prepare handover" starts the transfer → the handover
brief links back to the memory replay and the Copilot answers questions from the same
evidence. A recipient sees "A handover is waiting for you" on the Overview and My Work.

## Onboarding that follows the workspace

**Learn Relay** (sidebar) holds eight short tours: basics, ownership, connected evidence,
Memory Replay, What If?, Handover Copilot, recipient next steps and verifying a transfer.
Each unlocks only when the workspace has what it demonstrates (`relay/guidance/service.py`):
for example the What If? tour needs ownership records and a role that may simulate, and the
connected-evidence tour needs a provider whose first sync finished with no sync job still
queued or retrying. A tour spotlights the real element, can be skipped at any step, resumes
where it was closed and can be replayed. A per-member **Product guidance** switch turns off
the Overview's setup checklist and tour suggestions; tutorials stay available. State is
stored per member (migration `0041`, tenant RLS). Tests: `tests/test_guidance.py` (switch,
resume, reset, per-member isolation, input validation, and Linear moving through
syncing → retrying → ready → attention) and the browser journey "guidance" in
`frontend/e2e/round3.spec.ts`.

## Brand and interface

Relay now has a consistent identity: the relay mark (two strokes handing over), Instrument
Serif for headlines, Geist for the interface, a deep teal for primary actions and a warm
"baton" amber reserved for handover moments, and a relay-lines motif on the landing page,
Workspaces and the Overview's continuity-health panel. The Overview is a dashboard (coverage
ring, risk-severity bar, icon metrics, cases with people, an activity feed). Motion is short
and quiet (page entrances, staggered lists, filling bars) and switches off for people who
prefer reduced motion. Colour still carries meaning: red means act now, amber needs
attention, teal marks the current place and primary actions.

## Run it yourself

`python scripts/setup.py` then `python scripts/dev.py` (see the README). Sign-in needs a
free WorkOS staging account; AI features need a model key (a free Gemini key works).
