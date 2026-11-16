# Relay: Evidence-Backed Organizational Continuity Engine

## Executive Summary

Relay is an organizational continuity and knowledge succession platform built to prevent institutional amnesia. Modern engineering and product teams operate across fragmented tools: tasks in Linear, code and maintainership in GitHub, documentation in Notion. When a principal engineer, tech lead or domain owner departs, moves teams or takes extended leave, their context rarely transfers with them. Traditional offboarding relies on rushed exit interviews and static checklists that decay before new owners can use them.

Relay turns succession from a reactive checklist into an evidence-backed workflow. It maps who is accountable for what, detects single points of failure, simulates an absence before it happens, runs the transfer as an audited case, and then checks whether the transfer actually took hold.

Every claim below links to the code and tests that implement it. The [judge guide](../../Documentation/1-start-here/judge-guide.md) has the full evidence table, and the live product is at [relay-continuity-nine.vercel.app](https://relay-continuity-nine.vercel.app).

---

## The Problem Space: Institutional Amnesia and Key-Person Risk

Every organization faces key-person dependency (the "bus factor"): the vulnerability created when knowledge, access and responsibilities concentrate in one person. In technology teams it shows up in three ways:

1. **Undetected ownership gaps.** Teams discover that a critical service, migration script or compliance duty has no owner only after an incident. Org charts change faster than documentation.
2. **Superficial knowledge transfers.** Outgoing people write unstructured summaries that omit dependencies, escalation paths, access prerequisites and open edge cases. Successors spend months reverse-engineering the context.
3. **No follow-through.** A handover is marked "complete" once a meeting ends. Nothing checks whether the new owner actually picked the work up.

---

## Architecture and Technology Stack

**Backend.** FastAPI on Python 3.14, async SQLAlchemy 2 and psycopg 3, on **PostgreSQL 18**. Tenant data lives in domain schemas (`identity`, `catalog`, `continuity`, `governance`, `integrations`, `intelligence`, `audit`) protected by **forced Row-Level Security**: the application connects as a restricted role with no superuser or BYPASSRLS, and each transaction sets its tenant context, so a bug in application code still cannot read another tenant's rows. Every tenant table uses composite `(tenant_id, id)` keys and foreign keys, and a test inspects the schema to keep it that way ([`tests/security/test_schema_conventions.py`](../../backend/tests/security/test_schema_conventions.py), [`test_tenant_isolation.py`](../../backend/tests/security/test_tenant_isolation.py)).

**Background work.** Domain events are written through a **transactional outbox** in the same transaction as the change and processed by **Procrastinate** with idempotent handlers and stalled-job recovery, which removes dual-write inconsistencies ([`relay/jobs/`](../../backend/src/relay/jobs), [`test_stalled_jobs.py`](../../backend/tests/test_stalled_jobs.py)).

**Frontend.** Next.js 16 (App Router, cache components), React 19, TypeScript and Tailwind. Authentication is server-side through **WorkOS AuthKit**; tokens are verified on the server and never handled by client code. Frontend types mirror the backend's response models field for field.

---

## Core System Pillars

### 1. Catalog, ownership and governance

The catalog is the canonical registry of responsibilities, assets, people, teams and departments. Each responsibility has a criticality tier (`critical`, `high`, `standard`, `low`), a primary owner, and optional co-owners and backups (people or teams), with full ownership history. Review cadences are configurable per responsibility (7 to 730 days), and governance policies decide whether a backup is required and whether a change needs separation-of-duties review ([`relay/catalog/`](../../backend/src/relay/catalog), [`test_catalog.py`](../../backend/tests/security/test_catalog.py)).

### 2. Risk detection and the What If? simulator

Risks come from explicit rules (no owner, no backup, a single holder of critical work, stale knowledge), and every risk shows the rule that raised it. Insights rank **key-person exposure**: people who are the only holder of work, critical first ([`relay/risks/`](../../backend/src/relay/risks), [`relay/insights/service.py`](../../backend/src/relay/insights/service.py)).

The **What If? simulator** answers "what if this person were unavailable?" for any absence length. It is deterministic and read-only: it never changes a real ownership record ([`relay/continuity/simulation.py`](../../backend/src/relay/continuity/simulation.py), [`test_simulation.py`](../../backend/tests/test_simulation.py)). It shows:

- every responsibility left without cover, and the deadlines that fall due during the absence;
- the knowledge that only that person holds;
- cover candidates from recorded links, each simulated, with an overload flag when a candidate's load would reach max(2× typical, typical + 3);
- a readiness score with a published formula: cover 60%, usable (non-stale) knowledge 25%, a second holder remaining 15%, weighted by criticality.

### 3. Audited continuity cases

A transition (departure, coverage, team move, onboarding) runs as a **case**: plan → approve → execute → verify. The case gathers the responsibilities, assets, open work and knowledge in scope; readiness criteria gate execution; and critical work needs a second person to approve, so nobody can approve their own handover. Every transition is written to an append-only audit log in the same transaction ([`relay/continuity/lifecycle.py`](../../backend/src/relay/continuity/lifecycle.py), [`test_case_lifecycle.py`](../../backend/tests/security/test_case_lifecycle.py)).

### 4. Evidence and the AI Handover Copilot

Read-only connectors for **GitHub** (a GitHub App), **Linear** and **Notion** collect repositories, pull requests, issues, ownership files and pages. Relay never reads source code, commit diffs or discussion bodies, and credentials are encrypted at rest ([`relay/integrations/`](../../backend/src/relay/integrations)).

The **Handover Brief** is generated per recipient. Every statement is labelled Fact, Rule or AI inference and carries its evidence. Statements with missing or invented citations are rejected, conflicts need two distinct sources, and evidence the viewer may not see is removed before any model call ([`relay/intelligence/validate.py`](../../backend/src/relay/intelligence/validate.py), [`capsules.py`](../../backend/src/relay/intelligence/capsules.py)). Any edit creates a new version that needs approval, and the recipient acknowledges a specific version. The **Copilot** answers questions only from the brief's authorised evidence and says *Not in the evidence* otherwise ([`copilot.py`](../../backend/src/relay/intelligence/copilot.py), [`test_copilot.py`](../../backend/tests/intelligence/test_copilot.py)). With AI switched off, Relay falls back to labelled search and rule-based briefs.

### 5. Memory Replay and follow-through

**Memory Replay** merges GitHub, Linear, Notion and Relay events for a responsibility into one filterable timeline that can be replayed. AI groups events into chapters labelled *Inferred*, drops any event reference it invented, and answers history questions with cited events or says nothing was found ([`relay/intelligence/memory.py`](../../backend/src/relay/intelligence/memory.py), [`test_memory_replay.py`](../../backend/tests/intelligence/test_memory_replay.py)).

**Follow-through** checks, per transferred responsibility, whether the new holder is recorded, whether there has been a review or recorded activity since, and whether the handover tasks are closed. Each transfer shows as *settled*, *settling in* or *check in* (14 days without review or activity, or open tasks). It measures the work, not the person ([`follow_through.py`](../../backend/src/relay/continuity/follow_through.py)).

---

## Security and Integrity

- **Row-Level Security** forced on every tenant table, with a restricted application role.
- **Permissions** from one registry: every service calls `authorize()` and lists filter with `visible()`; unknown permissions and roles are denied ([`relay/policy/permissions.py`](../../backend/src/relay/policy/permissions.py)).
- **Append-only audit** of authorization decisions, role changes, case transitions and exports, with CSV export.
- **AI boundaries**: models only produce proposals and hold read-only tools; evidence text is treated as data, and prompt-injection attempts are tested ([`test_eval.py`](../../backend/tests/intelligence/test_eval.py)).
- **Graceful failure**: error boundaries and retry on every route, honest AI states (running, slow, stalled, failed) with safe retries.

---

## Verification

As of 15 November 2026 the backend suite passes in full (314 tests) against real PostgreSQL as the restricted application role, with Ruff and mypy clean; the frontend passes lint, type checks, formatting and a production build; Playwright journeys cover the public pages and the signed-in lifecycle from the landing page. Details: [testing notes](../../Documentation/5-testing-and-quality/testing-notes.md).

## Conclusion

Relay connects daily work to long-term organizational resilience. It replaces spreadsheets and ad-hoc exit interviews with an evidence-backed succession engine, so teams can see their exposure before someone leaves, hand work over with proof, and confirm that the work kept moving.
