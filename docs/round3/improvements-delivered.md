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

**Not done.** A diff view between brief versions. Every version is kept and can be
opened, and statements whose sources changed are flagged, but there is no line-by-line
comparison yet.

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
| `GET /workspaces/{id}/simulation?person_id=&backup_id=` | Done | all 8 |
| Correct impact for a person with known responsibilities | Done | `test_impact_of_removing_a_person` |
| A backup covering everything leaves `uncovered_responsibilities` empty | Done | `test_a_backup_covering_everything_leaves_nothing_uncovered` |
| Newly exposed single-person dependencies and undocumented work | Done | `test_exposed_risks_name_the_new_gaps` |
| Team-held responsibilities count only when the person is the team's last member | Done | `test_team_held_responsibility_is_affected_only_when_they_are_the_last_member` |
| 403 for non-managers (new permission `continuity.simulate`: owner, admin, continuity manager) | Done | `test_only_managers_can_simulate` |
| Inherits the caller's visibility; other workspaces return 404 | Done | `test_other_workspaces_and_bad_input_are_rejected` |
| **No write reaches the database** | Done: verified with a SQLAlchemy cursor listener | `test_simulation_writes_nothing` |
| Score explained and 100 when nothing is at stake | Done | `test_score_is_explained_and_full_for_someone_holding_nothing` |

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

**Not done.** Commit-level history: Relay reads pull request and issue metadata, never
commits or code, by design. The narrative is not cached; each request costs one model call
(it shares the AI rate limit of 20 runs per 10 minutes per user).

---

## Design refresh

The interface moved from the default grey theme to a calm neutral palette with a single
teal accent, grouped navigation with icons, sticky page headers with a one-line purpose,
and shared stat and panel components. Colour still carries meaning only: red means act
now, amber needs attention, teal marks the current place and primary actions.
