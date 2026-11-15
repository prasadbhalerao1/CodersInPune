# Security and privacy review

A code-level review by the builder's assistant. **This is not a penetration test and not a
compliance assessment.** No SOC 2, ISO 27001, GDPR or WCAG conformance is claimed.

## 1. Assets

| Asset | Where | Sensitivity |
|---|---|---|
| Responsibility catalogue, ownership history | `catalog` | Internal; restricted items confidential |
| Cases, interviews, capsules | `continuity`, `intelligence` | Confidential (departures, absences) |
| Knowledge (incl. imported Notion pages) | `catalog` | Internal → restricted by classification |
| Connector tokens | `integrations` (Fernet-encrypted) | Secret |
| Audit log | `audit` | Internal; integrity-critical |
| AI prompts/outputs | Sent to provider; outputs stored as claims | Inherits source audience |
| Secrets (WorkOS, encryption key, LLM keys) | Environment variables | Secret |

## 2. Threat actors

1. Another tenant's user (cross-tenant access).
2. A workspace member reaching beyond their role (privilege escalation, BOLA).
3. A removed member or revoked integration (stale access).
4. Malicious content inside a connected source (prompt injection, XSS payloads).
5. An attacker on the internet (forged webhooks, forged tokens, abuse).
6. A compromised application process (SQL access as `relay_app`).
7. An operator with database access.

## 3. Attack paths and controls

| # | Path | Controls (code) | Verified by | Residual risk |
|---|---|---|---|---|
| T1 | Read another tenant's rows by guessing IDs | Tenant from membership; transaction-local `app.tenant_id`; forced RLS on every tenant table; composite FKs | `test_tenant_isolation.py` (12 tests as `relay_app`), `test_schema_conventions.py`, cross-workspace tests in every module | Low |
| T2 | Member calls an admin endpoint | `authorize()` in every service; route enumeration test; unknown roles/permissions denied | `test_route_auth.py`, `test_permissions_audit_jobs.py::test_service_cannot_be_called_around_authorization` | Low |
| T3 | Member sees restricted responsibility | Restrictive RLS policy (`catalog.can_see_responsibility`) | `test_catalog_governance.py::test_restricted_responsibilities_fail_closed` | Low |
| T4 | Restricted evidence leaks via AI summary/capsule/search/email | Evidence pool built with requester visibility; audience = intersection; capsule per-viewer; search `visible()`; emails carry titles only | Canary test `test_analysis.py::...restricted_stays_restricted`; `test_search.py`; `test_email.py::test_mentions_never_include_the_comment_text` | Low–medium (titles of restricted cases can appear in a recipient's email if they're a participant) |
| T5 | Removed member keeps access | No authorization cache; active membership resolved per request | `test_workspace_access.py`, `test_email.py::test_removed_members_are_not_emailed` | Low (WorkOS session lives on, but grants nothing) |
| T6 | Revoked source keeps feeding evidence | Live re-check on render; withdrawn status; NEW 30-day source purge after disconnect | `test_analysis.py` withdrawal; `test_linear.py::test_disconnected_source_data_is_purged_after_30_days` | Medium: per-user source ACLs not mirrored (FR-INT-010) |
| T7 | Prompt injection in a README/page | Untrusted-content envelope; models hold only read tools; validator drops invented citations; proposals need human approval | `test_analysis.py` injection test | Medium: no external red-team; outputs could still mislead a reviewer |
| T8 | Forged GitHub webhook / replay | HMAC over raw body before parsing; delivery-ID dedupe; updated-at guard | `test_github_evidence.py`, e2e public | Low |
| T9 | Forged / expired access token | JWKS, issuer, audience, expiry, algorithm checks | `test_route_auth.py::test_a_forged_token_is_rejected` | Low |
| T10 | OAuth state fixation / installation hijack | Random state stored hashed, single-use, bound to user+workspace; GitHub installer verified | `test_linear.py::test_state_is_single_use_and_bound_to_the_user`, `test_members_and_github.py::test_connect_verifies_installation_ownership` | Low |
| T11 | XSS from source content | React escaping; no `dangerouslySetInnerHTML`; CSP, X-Frame-Options DENY, HSTS | Code search | Low |
| T12 | SSRF | No user-supplied URL is fetched; provider hosts fixed in config | Code search | Low |
| T13 | Abuse / resource exhaustion | Rate limits on 10 route groups; CSV 1,000 rows/512 KB; webhook 5 MB; AI token budgets; job serialisation per tenant | `test_rate_limits.py`, `test_imports.py`, `test_gateway.py`, `test_linear.py::test_syncs_are_serialised...` | Medium: rate limiter is per process |
| T14 | Audit tampering | No UPDATE/DELETE grant + trigger; deletion only for workspaces past their 30-day grace, by the owner role | `test_permissions_audit_jobs.py::test_audit_records_cannot_be_modified_or_deleted`, `test_workspace_deletion.py` | Low (an operator with the owner role could change triggers via a migration) |
| T15 | Compromised `relay_app` | No superuser, no BYPASSRLS, owns nothing, no DDL; owner URL kept out of the app (migrations run from CI) | `test_tenant_isolation.py::test_tests_run_as_restricted_application_role` | Low |
| T16 | Secrets in logs | Access logs log route templates only; audit metadata identifiers only; prompts/keys never logged | `test_health.py`, code review | Low |
| T17 | Unsafe external write by AI | AI has no write tools; external issues created only after a person approves exact content; idempotent | `test_external_actions.py` | Low |
| T18 | Stolen backup | Compose backups are plain `pg_dump` on a Docker volume | — | **Medium**: encrypt backups / use provider-encrypted storage |

## 4. Findings from this review

| ID | Severity | Finding | Status |
|---|---|---|---|
| S-01 | High (privacy) | AI provider data terms: the Decision Register (D10) verified "no training on customer content" for Anthropic. The configured provider is Gemini; its data use depends on the account tier and was not verified. | **Open — external**. Confirm paid-tier terms or use a provider with verified terms before real customer data |
| S-02 | Medium | Rate limiting is in-process; with more than one API replica limits multiply | Open — fix before scaling out |
| S-03 | Medium | Per-user source permissions (e.g. private-repo collaborators, Notion page ACLs) are not mirrored; imported content is workspace- or managers-visible | Open — documented; limit imports to org-shared material |
| S-04 | Medium | Disconnected sources kept data forever (FR-INT-012, D13) | **Fixed** (`f879fdf`, migration 0036) |
| S-05 | Medium | Lists silently truncated at 500 rows could hide records from reviewers | **Fixed** (`741d634`, keyset pagination) |
| S-06 | Low | Interactive API docs exposed in production | **Fixed** (`775ed84`) |
| S-07 | Low | Backups unencrypted on self-host | Open — operator config |
| S-08 | Low | Request ID not propagated into job logs | Open |
| S-09 | Info | Dependency/container scan results unknown until CI runs on a pushed branch | Open — run CI |

No critical or high-severity *code* vulnerability is known after this review. S-01 is a
data-handling decision, not a code defect, but it blocks use with real customer data.

## 5. Privacy questions from the brief

| Question | Answer |
|---|---|
| Does Relay ingest more than it needs? | Mostly no: GitHub metadata/CODEOWNERS only, no code; Linear titles/states; Notion only mapped pages. Imported Notion page bodies are the largest content store |
| Can an admin expose an outgoing employee's private content? | Only content already in connected, shared sources. The outgoing owner can review what a case shares (`test_outgoing_owner_reviews_what_a_case_shares`). Private messages are never ingested |
| Can the incoming employee see what they shouldn't? | Capsules render per viewer; managers-only evidence is omitted and counted under omissions |
| Can AI output broaden the audience? | No: audience is the intersection of cited evidence (canary test) |
| Can a removed integration keep supplying stale information? | Evidence is re-checked on render; data is purged 30 days after disconnect |
| Can confidential information appear in an email subject? | Subjects contain workspace name and event type only; bodies may contain case/task titles |
| Can data be permanently deleted? | Yes: workspace deletion (30-day grace, owner-role purge including audit). Per-person erasure is a manual procedure |
| Does the audit log retain sensitive data? | Identifiers and enums only; no tokens or user content |

## 6. External assessment still needed

1. Independent penetration test (web app + API + multi-tenancy) before a customer pilot.
2. AI red-team on prompt injection through connected sources.
3. Legal/privacy review: retention periods (D13), DPA and subprocessors (WorkOS, Render/
   Vercel/Neon, LLM provider), data residency.
4. WCAG 2.2 AA audit with assistive-technology users.
