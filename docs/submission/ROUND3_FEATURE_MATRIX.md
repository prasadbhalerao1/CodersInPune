# Relay: feature matrix (Round 3)

Every product module, where it lives and how it is tested.

Status values:
- **Verified**: an automated test exercises it, and it was checked in the running product.
- **Implemented**: built and wired end to end; covered indirectly.

UI paths are under `/w/<workspace>/`. Backend paths are under `backend/src/relay/`; test paths
are under `backend/tests/`.

| # | Module | UI | Backend | Tests | Status |
|---|---|---|---|---|---|
| 1 | Overview (health, debt, next step) | `/` | `insights/`, `guidance/` | `security/test_insights.py`, `test_guidance.py` | Verified |
| 2 | My Work | `my-work` | `continuity/service.py: my_work` | `security/test_collaboration.py` | Verified |
| 3 | Continuity Cases | `cases`, `cases/[id]` | `continuity/` | `security/test_cases.py`, `test_case_lifecycle.py` | Verified |
| 4 | Responsibilities | `responsibilities` | `catalog/service.py` | `security/test_catalog.py`, `test_catalog_governance.py` | Verified |
| 5 | People and Teams | `people`, `teams`, `departments` | `directory/` | `security/test_org_structure.py`, `test_profiles.py` | Verified |
| 6 | Projects and Systems, Assets | `assets` | `catalog/assets.py` | `security/test_departments_assets.py` | Verified |
| 7 | Knowledge (stewardship, versions, disputes, code drift) | `knowledge` | `catalog/knowledge.py`, `catalog/drift.py` | `test_code_drift.py`, `security/test_knowledge.py`, `test_knowledge_governance.py` | Verified |
| 8 | Continuity Intelligence (case analysis, Autopilot) | `cases/[id]/analysis` | `intelligence/runs.py`, `autopilot.py` | `intelligence/test_analysis.py`, `test_autopilot.py` | Verified |
| 9 | Continuity Debt and Risks | `risks`, `insights` | `risks/`, `insights/` | `security/test_risk_lifecycle.py`, `security/test_insights.py` | Verified |
| 10 | Insights and Reports | `insights`, simulator report | `insights/`, `continuity/simulation.py` | `test_simulation.py` | Verified |
| 11 | Integrations (GitHub, Linear, Notion, Slack, health) | `integrations/*` | `integrations/` | `security/test_github_evidence.py`, `security/test_linear.py`, `security/test_notion.py`, `test_slack.py`, `test_sync_checkpoint.py` | Verified |
| 12 | Agents and Automations | `agents`, `automations` | `automation/` | `security/test_automation.py` | Verified |
| 13 | Roles and Permissions | `settings/roles`, `/docs#roles` | `policy/permissions.py` | `test_role_docs.py`, `test_new_features_access.py` | Verified |
| 14 | Audit Log | `audit` | `audit/` | `security/test_permissions_audit_jobs.py` | Verified |
| 15 | Organisation Settings | `settings` | `platform/`, `identity/` | `security/test_members_and_github.py`, `security/test_governance_admin.py` | Verified |
| 16 | Context Capsules (handover brief per recipient) | `cases/[id]/capsules/[id]` | `intelligence/capsules.py` | `intelligence/test_handover.py`, `test_brief_strength.py` | Verified |
| 17 | Knowledge Capture Interview (voice-capable) | `cases/[id]/interview` | `intelligence/interviews.py` | `intelligence/test_handover.py` | Verified |
| 18 | Handover (approve, execute, accept, complete) | `cases/[id]` | `continuity/service.py`, `workflow.py` | `security/test_case_lifecycle.py` (acceptance, completion gate) | Verified |
| 19 | Handover Readiness | `cases/[id]` readiness | `continuity/service.py` criteria | `security/test_cases.py` | Verified |
| 20 | Project Memory Replay | `responsibilities/[id]/timeline` | `catalog/timeline.py`, `intelligence/memory.py` | `intelligence/test_memory_replay.py` | Verified |
| 21 | Search (Ctrl K, expertise map) | `search`, `expertise` | `search/` | `security/test_search.py`, `test_expertise.py` | Verified |
| 22 | User-facing documentation | `/docs`, `help`, tours, ⓘ | `guidance/` | `test_role_docs.py`, `e2e/a11y.spec.ts` | Verified |

## The three Round 2 commitments

| Commitment | What a judge can do | Key code | Tests |
|---|---|---|---|
| **AI Handover Copilot** | Open a handover brief: cited sections, evidence strength, "Who to ask", omissions, version history. Ask the Copilot (streamed, stoppable, saved per brief, with follow-up suggestions); it answers "not in the evidence" when it can't cite. Approve, acknowledge, rehearse. | `intelligence/capsules.py`, `copilot.py`, `rehearsal.py` | `intelligence/test_copilot.py`, `test_handover.py`, `test_brief_strength.py`, `test_rehearsal.py` |
| **What If? Continuity Simulator** | Pick a person and a duration; see affected responsibilities, coverage before and after, single-person dependencies and recommended actions; compare candidate backups side by side; pin up to three scenarios and compare them; download the report; open a pre-filled case. | `continuity/simulation.py` | `test_simulation.py` (asserts no writes) |
| **Project Memory Replay** | Replay a responsibility's history from GitHub, Linear, Notion and Relay: grouped events, filters (category, source, person, date range, major only) kept in the URL so a view can be shared, search, play and pause, evidence per event, gaps flagged, AI narrative kept separate from recorded facts. | `catalog/timeline.py`, `intelligence/memory.py` | `intelligence/test_memory_replay.py` |

## Beyond the three (Round 3 additions)

Handover Autopilot · meeting intelligence (decisions and actions become ADRs and tasks) ·
Ask Relay (workspace Q&A with citations) · decision log · expertise map · 30/60/90 plan ·
handover rehearsal · code drift on knowledge · Slack sharing · incoming-owner acceptance ·
evidence strength and "Who to ask" on briefs · idempotent creates · incremental GitHub and Linear sync ·
per-role judge accounts with one-click sign-in.
