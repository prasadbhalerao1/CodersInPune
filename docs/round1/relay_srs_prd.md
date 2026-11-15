# Document control

| Field | Value |
|---|---|
| Product name | Relay |
| Product category | Organisational continuity platform |
| Primary problem | Loss of operational context and interrupted work when people, projects, teams, processes, systems or responsibilities change |
| Primary product objects | Responsibility and Continuity Case |
| Primary user outcome | Work continues with less confusion, fewer missing details and a verifiable transfer of responsibility |
| Initial customer profile | Engineering-led organisations with connected work systems and recurring ownership or knowledge-transfer needs |
| Long-term customer profile | Cross-functional organisations across engineering, HR, operations, support, product, sales, IT and project teams |
| Requirement terms | MUST, SHOULD and MAY are normative requirement terms |
| Priority terms | P0 = release-critical; P1 = important; P2 = later enhancement |

## Revision history

| Version | Date | Change |
|---|---|---|
| 0.1 | 8 Nov 2026 | Product concept and initial feature map consolidated |
| 1.0 | 8 Nov 2026 | Combined PRD and SRS baseline, including agentic design, UX, roles, edge cases and release plan |

## How to read this document

- **PRD sections** explain why Relay exists, who it serves, what outcomes it should create and how the product should feel.
- **SRS sections** specify system behaviour, interfaces, data, access controls, quality attributes and acceptance criteria.
- **P0/P1/P2** indicate delivery priority, not product importance in the abstract.
- Items marked **provisional target** are engineering targets to validate through testing, not existing performance claims.
- Features described as **later phase** belong in the product architecture but are not required for the first release.


# 1. Executive product brief

## 1.1 What is Relay?

Relay is an AI-powered organisational continuity platform. It connects the people, responsibilities, operational knowledge, projects, processes and systems that keep an organisation running. When a person becomes unavailable, leaves, changes roles, transfers a project, or when a process or system changes, Relay identifies relevant context, analyses potential impact, prepares an actionable plan, coordinates the transfer and verifies whether the receiving person or team is ready to continue the work.

Relay is not intended to replace source systems such as GitHub, Linear, Jira, Slack, Notion, Google Workspace, Microsoft 365, HR systems or CRM platforms. It connects to them and provides a continuity layer across their data and workflows.

## 1.2 The problem in one sentence

Organisations lose operational context when things change: knowledge is scattered, responsibilities are not explicitly transferred, and missing information is often discovered only after work is blocked or an operational problem occurs.

## 1.3 A simple example

A senior engineer is leaving a company. They own three services, review critical pull requests, understand a deployment process and maintain undocumented relationships with other teams. Some information exists in GitHub, some in Linear, some in Notion and some only in the engineer's experience.

Without Relay, a manager asks for documentation, collects links, manually creates tasks and hopes the incoming owner understands the system. Important work may be missed.

With Relay, the manager creates a transition case. Relay discovers authorised responsibilities and associated sources, identifies affected systems and open work, detects missing or conflicting knowledge, prepares a proposed handover plan, asks targeted questions, routes drafts for review, creates approved tasks and guides the incoming owner through acceptance criteria. A case is not considered complete merely because a document was generated; completion depends on required reviews, tasks and readiness checks.

## 1.4 The three product promises

1. **Understand the organisation.** Know what responsibilities exist, who owns them, where related knowledge lives and what depends on what.
2. **Keep work moving.** Detect relevant changes, identify gaps and coordinate the actions required to maintain continuity.
3. **Verify the transfer.** Confirm that the receiving person or team has the authorised context, access, understanding and ability required to take responsibility.

## 1.5 Product positioning

**Relay — Organisational Continuity, Powered by AI.**  
*Keep work moving. Preserve what matters.*

Relay should be positioned as an operational continuity platform, not as an HRMS, project-management tool, developer portal, document editor, generic enterprise chatbot or employee-surveillance product.

## 1.6 Product scope philosophy

Relay has a broad, cross-functional long-term domain model. It should support engineering, HR, operations, customer support, product, IT, sales and project-management use cases over time. However, the initial release should enter through engineering-led organisations because GitHub, Linear and Notion provide concrete, testable sources and demonstrable workflows. A broad architecture does not mean every department-specific integration and playbook must ship in version one.

---

# 2. Product vision, problem and positioning

## 2.1 Problem statement

Modern organisations operate across disconnected applications and distributed teams. Responsibilities and knowledge are rarely represented in one consistent, current and permission-aware system. People become unavailable, projects are reassigned, teams reorganise, procedures evolve and systems change. The information needed to preserve continuity is distributed across documents, tickets, repositories, conversations, runbooks, decisions and human expertise.

Common failure modes include:
- A new owner does not know what they have inherited.
- A departing employee's important operational knowledge is not captured.
- A temporary absence causes unresolved tasks or unclear escalation paths.
- Critical responsibilities have no backup owner.
- A project is transferred without its decisions, risks or stakeholder context.
- Documentation is stale, contradictory or unowned.
- A manager cannot determine whether a handover is genuinely complete.
- The organisation discovers single-person dependencies only after a disruption.
- A generic AI assistant produces plausible summaries without proving that information is current, authoritative or accessible to the person asking.

## 2.2 Target outcomes

Relay should improve organisational resilience and reduce manual coordination during change. Desired outcomes include:
- Lower time to transfer a responsibility.
- Less time for an incoming owner to reach operational independence.
- Higher coverage of critical responsibilities by accountable primary and backup owners.
- Fewer unresolved knowledge gaps.
- Better visibility into incomplete or overdue continuity cases.
- More reliable and traceable operational knowledge.
- Fewer interruptions caused by undocumented procedures or unavailable people.
- Clearer accountability for actions, approvals and knowledge maintenance.

Relay must not claim it can eliminate all knowledge loss. It should expose uncertainty, record unresolved gaps and help people reduce risk.

## 2.3 Initial customer profile

### Initial ideal customer profile

Engineering-led organisations with multiple engineers, teams, services or repositories; work distributed across code hosting, issue tracking and documentation systems; recurring changes in project or service ownership; critical procedures that depend on individual expertise; managers responsible for onboarding, offboarding or temporary coverage; and a willingness to connect approved work systems and establish responsibility records.

### Long-term customer profile

Cross-functional organisations with multiple departments and shared operational processes. Relay should eventually support responsibilities that are not software-related, including customer accounts, approval processes, vendors, operating procedures, recruitment pipelines, support escalations and project portfolios.

## 2.4 Jobs to be done

| User need | Job to be done | Desired Relay outcome |
|---|---|---|
| Manager handling departure | Understand what the departing person owns and transfer it safely | Complete, reviewed transition case |
| Employee taking leave | Ensure urgent work has coverage and return context is preserved | Temporary coverage plan and return briefing |
| New employee | Learn the context needed to contribute | Role-specific onboarding path and readiness checks |
| Project manager | Transfer a project without losing decisions and stakeholders | Project context package and accepted ownership |
| Operations lead | Find uncovered or undocumented critical processes | Prioritised Continuity Debt and assigned remediation |
| Engineering manager | Understand service ownership and technical dependencies | Evidence-backed responsibility and asset records |
| Knowledge steward | Keep important knowledge current and trusted | Review queue, source history and verification records |
| Organisation administrator | Understand systemic continuity exposure | Organisation-level insights and policy controls |
| Auditor | Reconstruct who accessed, approved or changed information | Traceable audit history within authorised scope |

## 2.5 Product boundaries and non-goals

Relay is not intended to:
- Replace HRIS, payroll, applicant tracking or employee-performance systems.
- Replace GitHub, GitLab, Jira, Linear, Notion, Confluence, Slack or document-storage systems.
- Become a full project-management suite or general-purpose task tracker.
- Become a generic chatbot with no continuity workflow.
- Treat a visual graph as the primary value proposition.
- Automatically determine employee performance, promotion, termination or hiring suitability.
- Make autonomous employment decisions.
- Copy all user-created content into a central knowledge store without appropriate purpose, scope and permissions.
- Treat an AI-generated summary as authoritative without source references and review status.
- Guarantee that a recipient is competent solely because they completed a checklist.

## 2.6 Product principles

1. **Outcome over visualisation.** A graph is an optional exploration surface; action queues, cases and responsibility records are primary.
2. **Responsibility first.** The product models what must continue, not just who belongs to a team.
3. **Evidence over confidence theatre.** Important claims must link to source evidence and show uncertainty.
4. **Human accountability.** AI prepares and coordinates; authorised people approve consequential decisions.
5. **Least privilege.** Relay and its agents may only use information and actions the initiating user and configured service identities are allowed to access.
6. **Source-aware knowledge.** External source systems remain authoritative for their original records unless an explicit Relay-owned record is created.
7. **Graceful incompleteness.** Relay should still provide useful manual workflows when data or integrations are incomplete.
8. **Explainable risk.** Risks need a reason, evidence, scope, owner and suggested remediation.
9. **No silent failure.** Stale sync, expired credentials, incomplete analysis and unresolved errors must be visible.
10. **Progressive disclosure.** Everyday users see actions and outcomes; administrators can inspect integration, agent and audit detail.
11. **Configurable playbooks, shared foundation.** Different continuity scenarios reuse common entities and workflow capabilities.
12. **Privacy by design.** Capture only relevant, authorised operational context; do not turn Relay into employee surveillance.

---

# 3. Product strategy and competitive landscape

## 3.1 Competitive benchmark

Individual capabilities already exist. Relay must not claim that AI document search, knowledge verification, developer catalogues or AI-assisted handover are novel by themselves. The product opportunity is the integrated lifecycle from organisational context discovery through impact analysis, human-reviewed transfer and verification of continued work.

| Product | Existing capability relevant to Relay | Product lesson |
|---|---|---|
| ServiceNow Now Assist offboarding knowledge transfer | Agentic offboarding workflow can discover employee-authored resources, categorise them, create knowledge-transfer tasks and request employee review/consent [R1] | Use structured journeys, employee review, manager control and explicit transfer state |
| Guru | Knowledge verification, Knowledge Agents, content freshness and review workflows [R2, R3] | Knowledge needs ownership, validity, feedback and verification status |
| Atlassian Rovo | Agents use specialised tools and reusable skills; consequential actions can require confirmation and respect the user's permissions [R4, R5] | Separate tools from skills; enforce permissions and human confirmation |
| Glean | Connectors fetch content and permission maps, keep indexes current and enforce source-aware retrieval [R6] | Permissions and sync freshness are core connector requirements |
| OpsLevel | Software catalogue, ownership, operational metadata, workflow context and generated service descriptions [R7] | Engineering ownership and service context are valuable, but Relay must extend into transfer and readiness |
| Backstage | Software catalogue tracks ownership and metadata for services and other software entities [R8] | Borrow entity/catalogue patterns; do not make a developer portal the entire product |
| Temporal | Durable workflows, activities, workers, timers, cancellation, retries and workflow versioning [R9] | Long-running continuity cases may eventually need durable workflow infrastructure |

## 3.2 Differentiation hypothesis

Relay's differentiation should be validated around this combination:
- A generic responsibility model spanning people, teams, projects, services, processes, accounts and other assets.
- A persistent Continuity Case as the workflow record for a change.
- Evidence-backed impact analysis across multiple connected sources.
- Knowledge capture that identifies uncertainty and missing operational context.
- Human-reviewed task assignment, approvals and consent.
- A measurable readiness and transfer outcome, not merely document creation.
- Proactive detection of continuity debt beyond one-off employee departure.
- Role-specific workspaces for managers, outgoing owners, incoming owners, knowledge stewards and administrators.

This is a product hypothesis, not a claim that no competitor can provide comparable functionality. Competitive research should be repeated before public positioning and pricing decisions.

## 3.3 Ideas to borrow, not copy wholesale

- From ServiceNow: journey-based offboarding and explicit review/consent steps.
- From Guru: freshness, verification, knowledge ownership and feedback.
- From Rovo/GitLab agent platforms: tools, skills, scoped agent capabilities, execution traces and approval gates.
- From Glean: connector architecture, ACL mirroring, source-aware retrieval and incremental indexing.
- From OpsLevel/Backstage: catalogue entities, ownership, service context and discoverability.
- From Temporal: durable workflow principles, retry, timeout, cancellation and versioning.

## 3.4 Proposed product modules

1. Overview and My Work.
2. Continuity Cases.
3. Responsibilities.
4. People and Teams.
5. Projects and Systems / Assets.
6. Knowledge.
7. Continuity Intelligence and Continuity Debt.
8. Insights and Reports.
9. Integrations.
10. Agents and Automations (admin-facing).
11. Roles, Permissions, Audit Log and Settings.

The exact navigation may be permission-dependent. Not every role sees every module.

---

# 4. Goals, non-goals and success criteria

## 4.1 Product goals

- G1: Make critical responsibilities discoverable and accountable.
- G2: Reduce manual effort to prepare and execute continuity workflows.
- G3: Preserve relevant, authorised context with source provenance.
- G4: Detect continuity weaknesses before they cause disruption.
- G5: Make handovers and coverage measurable through task completion and readiness evidence.
- G6: Support multiple departments through configurable entities and playbooks.
- G7: Keep AI actions auditable, permission-aware and safely bounded.

## 4.2 Initial release goals

- An administrator can create an organisation, invite users, configure teams and connect initial integrations.
- A manager can create an ownership-transfer, temporary-absence or onboarding case.
- Relay can discover relevant authorised information from GitHub, Linear and Notion.
- Relay can generate an evidence-backed impact report and proposed action plan.
- A manager and relevant owners can review, edit, approve or reject proposed content.
- Approved tasks can be created in connected systems where permissions permit.
- The incoming owner can complete tasks and readiness criteria.
- Relay can display case state, evidence, agent runs, approvals and audit history.
- Relay can expose continuity gaps with traceable reasons and suggested remediation.

## 4.3 Non-goals for initial release

- Full HRIS or payroll functionality.
- Complete integrations with every enterprise application.
- Autonomous access revocation or employee lifecycle decisions.
- Fully autonomous agents with broad write access.
- Full workflow-builder UI.
- Advanced cross-company benchmarking.
- Sophisticated simulations requiring high-confidence inferred data.
- Replacing the original content editor for every connected knowledge source.
- Automatic employee competence scoring.

## 4.4 Success metrics

Metric definitions must be documented and configurable. Baselines should be collected before claiming improvement.

| Metric | Definition | Measurement |
|---|---|---|
| Critical responsibility coverage | Critical responsibilities with accountable owner and required backup / all in-scope critical responsibilities | Responsibility catalogue |
| Handover cycle time | Elapsed time from case initiation to verified completion | Case timestamps |
| Case completion rate | Cases completed within period / eligible cases | Workflow data |
| Knowledge gap resolution | Identified gaps resolved or accepted as exceptions / all identified gaps | Gap records |
| Readiness completion | Incoming owners who satisfy required criteria / incoming owners assigned | Readiness records |
| Unowned critical work | Critical responsibilities/assets without accountable owner | Coverage analysis |
| Knowledge freshness | Critical knowledge within review/validity window / critical knowledge items | Knowledge metadata |
| Integration freshness | Sources synced within configured freshness objective / connected sources | Connector telemetry |
| Agent proposal acceptance | Proposals accepted, edited or rejected, by capability | Review events |
| Agent correction rate | Materially incorrect proposals / reviewed proposals | Human feedback and evaluations |
| User time saved | Measured task time before/after where baseline is available | Pilot study, not inferred from token counts |

No single composite continuity score should be introduced until its components, weighting, data coverage and limitations are transparent.

---

# 5. Customers, personas and jobs to be done

## 5.1 Personas

- **Workspace Owner:** owns the Relay workspace and organisational configuration. Needs workspace settings, administrator assignment and governance controls.
- **Organisation Administrator:** manages identity, teams, roles, connected applications, data scope, retention and audit access. Needs integration health and permission diagnostics.
- **Continuity Manager:** coordinates organisation- or department-level cases. Needs prioritised cases, ownership gaps, overdue actions and reporting.
- **Department / Team Manager:** owns local responsibilities and approves transitions. Needs an efficient case workflow, impact review, backup assignment and verification.
- **Current / Outgoing Owner:** provides context and reviews knowledge proposed for transfer. Needs low-friction interviews and control over corrections/disputes.
- **Incoming Owner:** receives context and completes the transfer. Needs a role-specific package, manageable task list, source links and acceptance criteria.
- **Knowledge Steward / Subject-Matter Expert:** maintains knowledge quality. Needs a review queue, evidence, version history and review schedules.
- **Member:** searches authorised information, contributes knowledge and completes tasks. Should not see administrative complexity.
- **Auditor:** reviews permitted evidence, approvals and audit events. Generally read-only and scoped.

## 5.2 Multi-role users

A person may be a Team Manager in one team, Current Owner in one case, Incoming Owner in another case and Knowledge Steward for a specific process. Roles must be composable. A user should not be forced into one global job title that determines every permission.

## 5.3 User jobs to be done

- “Show me what I am responsible for and what needs my attention.”
- “I need to transfer a responsibility without losing critical context.”
- “I need to cover somebody's work while they are away.”
- “I need to know what changed while I was unavailable.”
- “I need to onboard a new person without asking them to read everything.”
- “I need to know whether important procedures are current.”
- “I need to find the right person to ask about a system or process.”
- “I need to know whether a critical responsibility has an appropriate backup.”
- “I need to verify that the incoming owner can continue the work.”

---

# 6. Product scope and feature catalogue

## 6.1 Module A — Overview and My Work

### Overview
A role-aware action centre that answers: what needs attention, what is active, what is at risk and what should happen next.

Core widgets:
- Priority actions.
- Active Continuity Cases.
- Cases awaiting the current user's approval.
- Responsibilities needing an owner or backup.
- Critical knowledge requiring review.
- Integration health (admins only or compact indicator).
- Recent activity relevant to the user.
- Upcoming planned transitions or absences where dates are available and the user is authorised.

Do not prioritise vanity metrics such as total indexed documents, graph nodes, agent runs or number of connected apps.

### My Work
A unified personal task and review queue with filters: Assigned to me; Awaiting my approval; Needs my input; Blocked; Overdue; Completed. Tasks may originate in Relay or external systems. External tasks must retain a source link and sync state.

## 6.2 Module B — Continuity Cases

Supported case types should be extensible. Initial types:
- Ownership transfer.
- Temporary absence coverage.
- New-owner onboarding.
- Project handover.

Later types:
- Employee offboarding.
- Internal role/team transfer.
- Service ownership transfer.
- Customer/account handover.
- Vendor/process transition.
- Incident/emergency continuity.
- Return-from-absence briefing.

A case has:
- Unique ID and human-readable title.
- Case type and template version.
- Initiator and accountable manager.
- Affected person(s), team(s), responsibility/asset(s).
- Current and receiving owner(s), if applicable.
- Effective date, due date and time zone.
- Priority / criticality.
- Purpose and scope.
- Status and status history.
- Evidence and findings.
- Tasks, dependencies and blockers.
- Knowledge items and proposed changes.
- Approvals, consent and acceptance.
- Readiness criteria and results.
- Activity and agent execution history.
- Closure outcome and exceptions.

Case creation must be possible manually even when a connected source is unavailable.

## 6.3 Module C — Responsibilities

Responsibility records describe ongoing work that must remain accountable. Examples include maintaining a service, handling customer escalations, approving a business process or owning a project outcome.

A responsibility should support:
- Name, description, type and criticality.
- Primary owner, co-owners and backup owners.
- Owning team/department.
- Effective dates and historical assignments.
- Related assets, projects, processes and knowledge.
- Required procedures and access prerequisites.
- Dependencies and escalation paths.
- Verification requirements.
- Review cadence and last-reviewed timestamp.
- Source provenance and confidence.

Responsibilities must not be inferred solely from commit frequency, document authorship or message volume. Such signals may produce a suggestion requiring review.

## 6.4 Module D — People, Teams and Organisation Structure

Capabilities:
- Organisation, department and team directory.
- User invitations and identity mapping.
- Multiple roles and team memberships.
- Manager/reporting relationship where explicitly configured and authorised.
- Team membership history where needed for continuity.
- External collaborator / contractor support.
- Identity reconciliation across connected systems.
- Deactivated, suspended and pending users.

Relay should not infer sensitive personal attributes or create employee-performance profiles from connected activity.

## 6.5 Module E — Projects, Systems and Assets

The generic Asset concept may represent:
- Software service, repository, application or infrastructure component.
- Project, programme or product.
- Business process or procedure.
- Customer account or vendor relationship.
- Team-owned operational resource.
- Document collection or knowledge collection.

Asset types should support typed metadata without making every department depend on engineering-specific fields. Asset records may include owners, source identifiers, lifecycle state, tags, criticality, dependencies, linked knowledge, open work and ownership history.

## 6.6 Module F — Knowledge Operations

Knowledge Item types may include:
- Runbook / procedure.
- Architecture Decision Record (ADR).
- Project overview.
- Process guide.
- System/service overview.
- FAQ / operational answer.
- Incident postmortem.
- Account/customer context.
- Contact/escalation information.
- Handover note.
- Onboarding resource.

Each item needs source attribution, owner, scope, verification status, version, review date and permission metadata.

Features:
- Unified search and cited answers.
- Structured knowledge records.
- AI-generated drafts.
- Human review and verification.
- Version history and comparison.
- Duplicate detection suggestions.
- Contradiction detection suggestions.
- Validity windows and review schedules.
- Knowledge ownership and escalation.
- Context Capsules.
- Knowledge Capture Interview.
- Decision Lineage.
- Return Briefing.

A **Context Capsule** is a scoped package of relevant, permission-checked context for a person, project, responsibility or transition. It should contain links or authorised excerpts, not indiscriminately duplicate all source data.

## 6.7 Module G — Continuity Intelligence and Continuity Debt

Continuity Intelligence detects actionable weaknesses such as:
- Critical responsibility with no primary owner.
- Critical responsibility with no backup where policy requires one.
- Asset with no accountable team.
- Knowledge item outside its review window.
- Important procedure with no verified owner.
- Conflicting source information.
- Ownership mismatch between declared metadata and observed system state.
- Unresolved handover tasks.
- Dependency on a person with no approved coverage.
- Project or process with missing escalation path.

Each finding must include finding ID and category; severity and affected scope; evidence references and dates; detection method (rule, source signal or AI inference); confidence/uncertainty where applicable; recommended remediation; assigned owner or queue; status and resolution history.

**Continuity Debt** is the backlog of unresolved findings and accepted exceptions. Its priority should be based on configurable criticality, exposure, confidence, age and business context. Avoid false precision.

## 6.8 Module H — Onboarding, Readiness and Handover Rehearsal

An onboarding path should be generated from responsibilities and relevant context, then reviewed by a manager. It can include required access setup; key people and escalation contacts; required knowledge items; project and system walkthroughs; assigned starter tasks; required procedure demonstrations; question-and-answer opportunities; acceptance criteria and due dates.

**Handover Rehearsal** is an optional verification method. It may use a checklist, sandbox task, guided scenario or human-supervised demonstration. Relay must not claim competence from passive content consumption alone.

## 6.9 Module I — Insights and Reports

Reports should include responsibility and backup coverage; open and overdue Continuity Cases; knowledge gap backlog and resolution; knowledge freshness and verification coverage; time to complete transitions; readiness criteria completion; integration freshness and failure rate; agent proposal acceptance/correction rate; repeated issues associated with missing context.

Reports must explain filters, denominators, exclusions and data coverage. Do not rank employees by raw AI-derived continuity scores.

## 6.10 Module J — Integrations

Initial: GitHub, Linear and Notion. Planned next: Slack, Google Drive/Workspace, Jira, Confluence, Microsoft 365/SharePoint, selected HRIS/CRM and ticketing systems as validated.

Connector framework must support source-specific capabilities, scope configuration, data permissions, incremental sync, webhook processing, rate-limit handling, retry, full reconciliation, disconnect and deletion workflows.

## 6.11 Module K — Agents and Automations

Admin-facing capabilities:
- View available capabilities and workflows.
- Inspect agent tools and allowed scopes.
- Configure approved workflow triggers.
- Set human approval requirements.
- Review execution history, errors and costs.
- Disable a capability or connector.
- Configure policies and limits.

Everyday users should see the outcomes of agent work inside cases and tasks rather than being forced to operate an agent console.

---

# 7. Product information architecture and UI/UX specification

## 7.1 UX principles

- Organise screens by user jobs, not backend services.
- Prioritise actions over vanity metrics.
- Use familiar SaaS patterns: persistent sidebar, workspace switcher, global search, contextual actions and consistent tables.
- Keep case details as the primary operational workspace.
- Present AI as contextual assistance, not the entire product.
- Distinguish verified facts, source observations, AI inferences and human decisions.
- Use progressive disclosure for advanced configuration.
- Make permissions and visibility understandable at the point of action.
- Provide empty, loading, stale, partial, failure and success states for every data-driven screen.
- Avoid a graph-first experience. Graph visualisation is optional and secondary.

## 7.2 Proposed primary navigation

### Workspace navigation
1. Overview.
2. My Work.
3. Continuity Cases.
4. Responsibilities.
5. People & Teams.
6. Projects & Systems (or Assets).
7. Knowledge.
8. Continuity Debt / Insights.

### Administration navigation
1. Integrations.
2. Agents & Automations.
3. Roles & Permissions.
4. Audit Log.
5. Organisation Settings.
6. Workspace / Subscription settings if commercialised.

Navigation is permission-aware. A member may see Overview, My Work, relevant cases, Responsibilities and Knowledge, while an administrator additionally sees governance and integration configuration.

## 7.3 Global application shell

- Workspace selector.
- Global search with permission-aware results.
- Create button with quick actions (New Case, New Responsibility, Add Knowledge, Invite User, Connect Integration as permitted).
- Notifications / inbox.
- Help and product feedback.
- User profile and active role context.
- Current organisation / department scope.

The application must make it clear which workspace and organisation the user is acting in, especially when they belong to multiple organisations.

## 7.4 Overview screen

Purpose: show what needs attention and what the current user is expected to do next.

Suggested content: priority action queue; cases requiring the user's action; active transitions in the user's scope; coverage gaps; critical knowledge awaiting review; recent changes with operational relevance; upcoming planned coverage changes; integration freshness indicator for administrators.

Do not display employee activity surveillance metrics or raw ingestion counts as headline KPIs.

## 7.5 My Work screen

- Unified task list.
- Filters: assigned, approval, needs input, blocked, overdue, completed.
- Task origin and related case.
- Due date and priority.
- Source system link where task is external.
- Clear actions: Complete, Request clarification, Reassign (if permitted), Open source, Approve/Reject (if the task is an approval).
- Bulk actions only where safe and auditable.

## 7.6 Continuity Cases list

- Search and advanced filters.
- Case type, status, responsible manager, affected person/team, due date and priority.
- Sort by overdue, risk, due date and recently updated.
- Saved views for common manager/admin use.
- Case creation wizard with progressive disclosure.
- Duplicate-case warning when a similar active case exists.

## 7.7 Case creation wizard

1. Select case type.
2. Select affected person, team, responsibility, project or asset.
3. Specify dates, current owner, incoming/backup owner and scope.
4. Select relevant source systems and include/exclude scopes.
5. Confirm privacy, consent and data-use notice appropriate to the case.
6. Review the proposed investigation scope and create the case.

Do not make the wizard unnecessarily long. Only ask required questions at creation; ask follow-up questions when analysis reveals a real gap.

## 7.8 Case detail workspace

Recommended tabs or sections: Overview; Impact; Knowledge; Tasks / Work; People; Approvals; Activity.

Header should show case title, type, status, priority, due date, accountable manager and next required action. A persistent summary panel may show completion progress and outstanding blockers.

- **Overview:** purpose, scope, affected responsibilities/assets, participants, timeline and current status.
- **Impact:** affected projects, services, processes, open work, dependencies and ownership gaps. Every item links to a source record or Relay record.
- **Knowledge:** relevant knowledge items, source evidence, confidence, freshness, missing content and review status. User can approve, edit, reject or request clarification.
- **Tasks / Work:** tasks by owner, due date, status, external source and blocker. Distinguish Relay-native tasks from tasks mirrored to an external system.
- **People:** current owner, receiving owner, manager, backups, SMEs, approvers and case participants. Display why each person is included.
- **Approvals:** approval request, scope, approver, deadline, decision, comment and timestamp. Rejected content returns to an editable/review state.
- **Activity:** chronological event timeline with human actions, system events, connector changes and agent actions. Agent events link to execution details.

## 7.9 Responsibilities screen

A searchable catalogue with filters for team, owner, backup, criticality, type, verification status and review date. Detail page contains description, owner assignments/history, linked assets, required knowledge, procedures, dependencies, escalation, evidence and review history.

The graph explorer is an optional view for relationship exploration. It is not required to complete ordinary tasks.

## 7.10 People & Teams screen

- Directory and team view.
- Team membership and role assignments.
- Responsibility coverage per team.
- Pending invitations and deactivated identities.
- Identity-matching conflicts.
- Access summary where authorised.

Avoid exposing private employee details to users who do not need them.

## 7.11 Knowledge screen

- Search and filters.
- Types, owner, team, source, last updated, last verified, review date and verification state.
- Knowledge detail with content or authorised excerpt, source links, evidence, version history and approvals.
- Review queue for Knowledge Stewards.
- Clear stale, disputed, expired, conflicting and inaccessible states.

## 7.12 Continuity Debt / Insights screen

- Prioritised findings list.
- Filters by type, criticality, department, owner, confidence and age.
- Explanation of why each finding exists.
- Suggested remediation.
- Assignment and case creation actions.
- Metrics and trend charts with definitions and sample sizes.

## 7.13 Integrations screen

Each connector card/detail should show connected/disconnected/attention-required state; connected identity and installation/tenant; scope and permissions granted; included/excluded projects, spaces, repositories or sites; last successful sync and current sync status; records discovered/updated/deleted where meaningful; recent errors and rate limits; test connection, resync, pause, disconnect and credential renewal actions.

A connector must not show green/healthy when its last successful sync is older than its configured freshness objective.

## 7.14 Agents & Automations screen

For administrators and authorised operators: agent capability catalogue; workflow templates; trigger configuration; tool access and scopes; approval rules; run history and trace details; token/cost budgets; evaluation metrics; disable/kill switch.

For normal users, show an inline summary of what the agent found, what it recommends and what needs approval.

## 7.15 Notifications and communication

- In-app notifications are required.
- Email notifications should be supported for case assignments, approvals, reminders and critical integration/security events.
- Slack/Teams notifications are later integrations.
- Notification preferences must be configurable within policy constraints.
- Avoid repeated noisy notifications; group related events and provide digest options.
- Sensitive content should not be placed in email/Slack notification bodies by default; use secure links to Relay.

## 7.16 Responsive and accessibility requirements

- Desktop-first for managers, administrators and case operations.
- Tablet and mobile support for task completion, review, approvals and reading.
- Do not force complex admin configuration onto mobile.
- Keyboard-operable controls and visible focus.
- Semantic headings and landmarks.
- Accessible form labels and validation messages.
- Status not conveyed by colour alone.
- Sufficient text contrast and scalable text.
- Tables should provide accessible headers and responsive alternatives.
- Confirm destructive or sensitive actions.

## 7.17 UX state catalogue

Every major screen must support empty state, loading state, partial data, stale data, error with retry/diagnostics, no permission, archived/deleted source, conflict, offline/degraded state where relevant, and success confirmation with next step.

---

# 8. Roles, permissions and governance

## 8.1 Role catalogue

| Role | Primary responsibilities |
|---|---|
| Workspace Owner | Workspace ownership, organisation configuration and owner transfer |
| Organisation Admin | Users, teams, connectors, roles, access policies, retention and audit configuration |
| Continuity Manager | Cross-team cases and continuity oversight within assigned scope |
| Department / Team Manager | Team responsibilities, case initiation, assignments and approvals |
| Current / Outgoing Owner | Provide, correct and review context for responsibilities being transferred |
| Incoming Owner | Receive authorised context, complete transfer tasks and submit readiness evidence |
| Knowledge Steward | Maintain knowledge quality and review important records within scope |
| Member | Search authorised information, contribute knowledge and complete tasks |
| Auditor | Read-only access to permitted audit records and case evidence |

Roles are assignable at workspace, department, team, resource or case scope where appropriate. Users can hold multiple roles.

## 8.2 Permission model

Use a layered model:
1. **Tenant boundary:** all requests are scoped to the authenticated organisation/workspace.
2. **Workspace role:** baseline capability.
3. **Department/team scope:** limits organisational reach.
4. **Resource scope:** specific responsibility, asset, knowledge item or project access.
5. **Case participation:** access to a specific continuity case and its permitted content.
6. **Source ACL:** connected source permissions must be enforced for source-derived content.
7. **Action policy:** additional policy for sensitive write operations, exports, deletion and access changes.

RBAC should not be the only mechanism. Contextual attributes such as team membership, case participation, source permissions and sensitivity classification must be considered.

## 8.3 Permission matrix (summary)

| Action | Admin | Continuity Mgr | Team Mgr | Current Owner | Incoming Owner | Knowledge Steward | Member | Auditor |
|---|---|---|---|---|---|---|---|---|
| Manage workspace | Yes | No | No | No | No | No | No | No |
| Manage connectors | Yes | No | No | No | No | No | No | No |
| Create case | Yes | Yes | Team scope | By policy | No by default | No by default | Request only | No |
| View case | Scope | Scope | Team/case | Participating | Participating | Knowledge scope | Assigned | Audit scope |
| Edit outgoing context | If authorised | Review | Review | Yes | Comment/question | Knowledge scope | Own contribution | No |
| Approve transfer | Policy | Scope | Team scope | Review/consent | Accept receipt | Knowledge approval | No | No |
| Assign tasks | Yes | Scope | Team scope | No | No | Knowledge tasks | No | No |
| Verify knowledge | If role | If role | If role | Own items | Feedback | Yes, scope | Feedback | No |
| Execute external write | Policy + approval | Policy + approval | Policy + approval | No by default | No by default | Scoped approval | No | No |
| Read audit history | Yes | Scope | Team/case | Own case | Own case | Knowledge scope | Limited | Read-only scope |

This is a baseline. The final implementation must use an explicit permission registry and endpoint-level authorisation rather than relying only on hiding UI controls.

## 8.4 Sensitive data handling

- HR, compensation, performance, health and other sensitive employee records are out of scope for default ingestion.
- If an organisation later enables a sensitive connector/use case, it must be explicitly configured, separately permissioned, purpose-limited and legally reviewed.
- Personal notes and private messages must not be indexed by default.
- The product must explain why a source is being accessed and who can receive resulting content.
- A manager's authority to initiate a case does not automatically permit copying every document authored by the affected employee.

## 8.5 Separation of duties

For high-impact transitions, the same person should not necessarily initiate, approve and verify the entire process. Policies may require separate manager, current owner, incoming owner and knowledge steward participation. Small organisations may allow exceptions, which must be recorded.

---

# 9. Core domain concepts and lifecycle workflows

## 9.1 Responsibility

A Responsibility is a defined operational obligation or area of accountability that must continue over time. It may be assigned to a person, team or shared group. It can relate to assets, processes, projects, accounts, systems and knowledge items.

Key attributes:
- Responsibility ID.
- Name and description.
- Type/category.
- Organisation and team scope.
- Criticality and impact description.
- Primary owner(s) and backup owner(s).
- Effective ownership periods.
- Related assets and dependencies.
- Required procedures and knowledge.
- Escalation contacts.
- Review cadence and verification state.
- Source and provenance.

## 9.2 Continuity Case

A Continuity Case is a managed workflow for responding to an organisational change that could interrupt work or cause context loss. Case type controls required participants, evidence categories, workflow stages, approval rules, task templates, readiness criteria, data retention rules and closure conditions.

## 9.3 Ownership assignment history

Ownership must be time-aware. Do not overwrite the previous owner when an assignment changes. Store an assignment record with owner, scope, role type, effective start, effective end, source, change reason and actor. Support overlapping co-ownership where valid, but prevent accidental ambiguous primary ownership under policies that require one.

## 9.4 Knowledge and evidence distinction

- **Source Item:** a record that exists in an external system or an uploaded authorised source.
- **Evidence:** a specific source reference, excerpt, event or record supporting a claim.
- **Knowledge Item:** a Relay-managed structured representation or curated record.
- **Finding:** a detected condition or gap with evidence and status.
- **AI Inference:** an unverified interpretation generated from evidence; it must be labelled as such.
- **Human Decision:** an approval, correction, rejection or acceptance recorded by an authorised person.

## 9.5 Ownership transfer workflow

1. Manager creates an ownership-transfer case.
2. Relay identifies current responsibility, current owner, assets and related work.
3. Relay checks incoming owner and access eligibility.
4. Discovery and impact analysis produce findings with sources.
5. Missing knowledge is captured through questions or requests.
6. Handover plan is proposed.
7. Current owner reviews outgoing context and sharing.
8. Manager reviews scope, tasks and risk.
9. Approved tasks are assigned internally or synchronised externally.
10. Incoming owner reviews context and completes acceptance criteria.
11. Readiness is submitted and reviewed.
12. Ownership assignment is updated with effective date and audit record.
13. Case is completed or closed with accepted exceptions.

## 9.6 Temporary absence workflow

1. Manager or authorised user creates an absence-coverage case.
2. Relay identifies responsibilities and time-bounded work within scope.
3. It retrieves open tasks, deadlines, upcoming events, procedures and escalation paths.
4. It proposes temporary coverage and flags missing backups.
5. Manager approves assignments and any delegated authorities.
6. Temporary owners receive context capsules and tasks.
7. During absence, relevant changes are collected within policy and used to maintain a return briefing.
8. On return, original owner receives a concise update and outstanding actions.
9. Temporary assignments expire or are explicitly extended.
10. Case closes with unresolved items preserved.

## 9.7 New employee onboarding workflow

1. Manager or HR-integrated trigger creates onboarding case.
2. Relay maps approved role/team/responsibilities to a proposed onboarding path.
3. Access prerequisites are listed; actual access grant remains with the identity/source system and approval policy.
4. Knowledge items and contacts are selected with permission checks.
5. Starter tasks and milestones are assigned.
6. Incoming employee completes tasks and asks questions.
7. Manager/mentor reviews progress and readiness.
8. Completion is recorded; incomplete criteria remain visible as exceptions.

## 9.8 Project handover workflow

1. Current project owner initiates or manager creates a case.
2. Relay retrieves project status, milestones, tasks, risks, decisions, stakeholders and relevant source records.
3. Relay identifies work without a new accountable owner.
4. It prepares project context capsule and transfer tasks.
5. Current owner confirms or corrects project state.
6. Incoming owner reviews and accepts.
7. Project source system ownership/assignment is changed only after authorised approval.
8. Case closes with history retained.

## 9.9 Employee offboarding workflow (later phase)

1. Authorised manager/HR role initiates case with required purpose and date.
2. Relay searches only approved sources and configured time/scope.
3. It categorises work-related resources and excludes restricted/private content.
4. The departing employee reviews proposed knowledge-transfer items where policy requires.
5. The employee may correct, dispute or flag an item as private/restricted.
6. Manager decides approved recipients and required tasks.
7. Tasks and access changes are routed to authorised systems and human approval.
8. Completion is tracked separately from account deactivation.
9. Legal/retention policy determines what may be preserved or deleted.

## 9.10 Emergency continuity workflow

- A case can be created when a primary owner is unexpectedly unavailable.
- The system should use already authorised organisational sources and existing responsibility records.
- It must not require the unavailable person to complete an interview.
- Unknown information must remain unknown and be routed to manager/SME follow-up.
- Emergency access elevation, if ever supported, must be handled by the source identity/security system, not inferred or granted autonomously by Relay.

## 9.11 Case state model

Recommended states: Draft; Investigating; Awaiting Input; Awaiting Review; Ready for Transfer; In Progress; Verification; Completed; Blocked; Cancelled; Reopened.

State changes must be validated against case type, actor permissions and required data. `Completed` must not be reached if mandatory closure criteria remain unmet, unless an authorised exception path is used and documented.

---

# 10. Agentic system requirements and architecture

## 10.1 Design objective

The agentic layer should reduce repetitive investigation, drafting, coordination and verification work. It should not become an unbounded autonomous system. Agents operate as scoped capabilities inside explicit workflows, with deterministic state transitions, permission checks, evidence requirements, action limits and human approval for consequential actions.

## 10.2 Agent architecture

Recommended logical architecture:
1. **Event/request intake:** manual user action, webhook, scheduled check or approved workflow trigger.
2. **Policy gate:** validates tenant, user, purpose, scope, permission and action budget.
3. **Workflow orchestrator:** creates and advances a persisted workflow instance.
4. **Specialised capabilities:** discovery, impact analysis, knowledge extraction, planning, interviewing, coordination and verification.
5. **Tool gateway:** exposes typed, scoped tools for internal and external operations.
6. **Evidence and state store:** persists inputs, source references, outputs, checkpoints, approvals and execution events.
7. **Human review:** presents suggestions, evidence and consequences before approved actions.
8. **Audit/observability:** traces each run and any side effect.

The architecture does not require a swarm of concurrently autonomous agents. One orchestrator may call specialised agent workflows or deterministic services as appropriate.

## 10.3 Agent capabilities

### A. Continuity Monitor
**Purpose:** Detect events and conditions that may indicate a continuity risk. Inputs include source events, responsibility changes, sync deltas, review dates, task status and configured rules. Outputs include candidate finding, severity proposal, evidence, confidence and suggested next action. It may create a draft finding or notification; it must not alter ownership or initiate sensitive workflows without policy. Most checks should be deterministic. LLMs may classify/explain ambiguous cases but should not be the sole source of criticality.

### B. Discovery Agent / Context Retriever
**Purpose:** Gather relevant authorised information for a case, responsibility or query. Inputs include case scope, entity IDs, authorised connector scope, time range and purpose. Outputs include ranked source records, evidence references, freshness and access state. Requirements: permission-aware retrieval, source links, deduplication and explicit missing-source reporting.

### C. Impact Analyst
**Purpose:** Identify affected responsibilities, assets, projects, processes, open tasks, dependencies and relevant people. Outputs are structured findings grouped by category, each with evidence, confidence, reason and recommended action. It must distinguish direct source evidence from inferred relationships.

### D. Knowledge Steward
**Purpose:** Draft, compare, classify and review knowledge records; identify stale, duplicated or contradictory information. It may create drafts, suggest updates, request verification and flag contradictions. It must not silently overwrite authoritative source documents or mark content verified without an authorised verification event.

### E. Knowledge Interviewer
**Purpose:** Ask targeted questions that fill gaps in a responsibility or handover record.

Requirements:
- Start with known context to avoid asking questions already answered.
- Ask one question or a small coherent group at a time.
- Identify why the answer is required.
- Allow “unknown”, “not applicable” and “cannot share”.
- Capture answer author, timestamp, scope and consent/visibility.
- Convert answers into draft knowledge requiring review where configured.
- Avoid collecting irrelevant personal information.

### F. Handover Planner
**Purpose:** Convert approved scope and evidence into a structured plan. Outputs include tasks, owners, dependencies, due dates, required documents, approvals, readiness criteria and unresolved exceptions. It may recommend assignees but must not infer authority to assign a person without policy.

### G. Coordination Agent
**Purpose:** Prepare reminders, task creation, status summaries and permitted notifications. Actions may include creating a task in Linear/Jira or posting a notification after approval. It must use idempotency keys and record external object IDs. It should not repeatedly message a person or create duplicate tickets.

### H. Readiness Verifier
**Purpose:** Evaluate whether the receiving owner has completed explicit acceptance criteria. Inputs include checklist completion, submitted evidence, task state, review records and optional rehearsal result. Outputs are passed, failed, needs human review or unable to assess, with criterion-level explanation. It must not claim to establish competence from document views, chat activity or AI confidence alone.

### I. Return Briefing Generator
**Purpose:** Produce a scoped briefing for someone returning from temporary absence or taking back a responsibility. Outputs include changes during absence, completed work, open actions, decisions, incidents, temporary ownership and links. Every item should include source and time period.

### J. Continuity Simulation Assistant (later phase)
**Purpose:** Simulate the effect of a primary owner becoming unavailable and identify uncovered tasks or missing knowledge. It is a planning tool, not a definitive measure of employee capability or business resilience.

## 10.4 Agent tools

Agents must call explicit, typed tools through a central gateway. Tool access is capability-scoped and tenant-aware.

**Initial read tools:**
- `get_responsibility`
- `list_responsibilities_for_person`
- `get_asset`
- `list_related_assets`
- `search_authorised_sources`
- `get_open_work_items`
- `get_knowledge_item`
- `get_case_context`
- `get_team_membership`
- `get_connector_sync_status`

**Draft tools:**
- `create_knowledge_draft`
- `create_case_finding`
- `create_proposed_task`
- `create_context_capsule_draft`
- `create_proposed_approval`
- `create_readiness_criteria_draft`

**Write tools (approval-gated according to policy):**
- `create_external_task`
- `update_external_task`
- `notify_user`
- `request_knowledge_review`
- `assign_case_task`
- `update_ownership_assignment`

**Sensitive tools requiring explicit authorised approval and potentially excluded from initial product:**
- `grant_or_revoke_access`
- `change_employment_state`
- `export_sensitive_records`
- `delete_source_content`

Relay should not implement employment-state changes or autonomous access revocation as agent capabilities in the initial product.

## 10.5 Agent autonomy levels

| Level | Meaning | Example | Initial policy |
|---|---|---|---|
| L0 Observe | Read and analyse permitted information | Find open PRs | Allowed within scope |
| L1 Prepare | Draft content or recommendations | Prepare a handover plan | Allowed; clearly labelled draft |
| L2 Execute approved | Perform a defined write after human approval | Create approved Linear tasks | Allowed with audit and idempotency |
| L3 Restricted | High-impact or sensitive action | Change access or expose sensitive records | Disabled initially or explicit multi-party approval |

The initiating user's permissions and connector service permissions must both be enforced. A background agent must not gain broader permissions merely because it runs under a service account.

## 10.6 Agent run lifecycle

Suggested states: Queued; Running; Waiting for tool; Waiting for approval; Completed; Partially completed; Failed; Cancelled; Timed out; Requires human review.

Every run stores:
- Run ID and workflow ID.
- Tenant, initiating user/system event and purpose.
- Agent capability and version.
- Prompt/configuration version (or immutable reference).
- Model/provider and configuration metadata where appropriate.
- Input entity IDs and source references.
- Tool calls and tool responses (redacted as required).
- Structured outputs and schema version.
- Evidence links.
- Approval decisions.
- Side-effect records and external IDs.
- Retry/checkpoint history.
- Token/cost/latency metrics.
- Error details and final disposition.

## 10.7 Evidence and output contract

Agent outputs that affect cases or decisions should use structured schemas rather than free-form prose alone. A finding should include:
- `claim` — concise statement.
- `category` — finding type.
- `evidence[]` — source IDs, URLs or record IDs, timestamps and excerpts where allowed.
- `basis` — direct source observation, deterministic rule or AI inference.
- `confidence` — calibrated/qualitative value where appropriate; never presented as objective truth without evaluation.
- `freshness` — source update/last-sync information.
- `impact_scope` — affected entities.
- `recommendation` — suggested action.
- `requires_review` — boolean and reason.
- `limitations[]` — missing or inaccessible sources.

If evidence is absent, the output must say so and must not be promoted to verified knowledge.

## 10.8 Human approval gates

Human approval should be required before publishing knowledge to a broader audience; sharing an outgoing owner's proposed knowledge with new recipients where policy requires review; creating/changing external tasks in initial release unless explicitly approved; changing primary/backup assignments; closing a high-criticality case; sending broad communications about employee transitions; and any sensitive export, permission or access action.

Approval must display what will happen, where it will happen, who will see the result, what source data is involved and whether the action is reversible.

## 10.9 Prompt injection and untrusted content

All retrieved source content is untrusted data. Instructions embedded in documents, code, issue comments or web pages must not override system policy or tool permissions. The model must not treat source text as executable policy. Tool calls must be validated independently of model output. External content must be bounded, labelled and screened for suspicious instruction-like content where feasible.

## 10.10 Agent evaluation and quality

Before enabling a capability for production use, evaluate source retrieval precision/recall; evidence citation accuracy; correct identification of missing data; hallucination and unsupported claim rate; false positive/negative rates; permission filtering; tool argument validity; duplicate side-effect prevention; human acceptance/correction/rejection rates; latency/cost; and robustness to prompt injection, stale data and conflicting sources.

Use representative, permission-sensitive test data. Evaluation datasets must not contain real employee-sensitive content unless explicitly authorised and protected.

## 10.11 Agentic feature workflows

### Workflow 1: Developer ownership transition
1. Manager creates case.
2. Discovery retrieves relevant authorised repositories, PRs, issues, project records and knowledge.
3. Impact Analyst identifies affected work and responsibilities.
4. Knowledge Steward finds gaps and drafts runbook updates.
5. Knowledge Interviewer asks the outgoing owner targeted questions.
6. Handover Planner creates tasks and acceptance criteria.
7. Manager and outgoing owner review.
8. Coordination Agent creates approved external tasks.
9. Incoming owner completes context review and practical criteria.
10. Readiness Verifier produces a criterion-level result.

### Workflow 2: Stale operational documentation
1. Connector receives or discovers a relevant source change.
2. Deterministic matching identifies related knowledge items.
3. Knowledge Steward compares current source state with the knowledge record.
4. If mismatch is plausible, create a review finding.
5. Owner receives a review task with evidence.
6. Human approves correction or dismisses finding with reason.
7. Knowledge version and audit history update.

### Workflow 3: Temporary absence coverage
1. Case is created with dates and scope.
2. Discovery identifies responsibilities, due work, key events and approved procedures.
3. Impact Analyst identifies deadlines, dependencies and uncovered work.
4. Handover Planner proposes temporary cover and context packages.
5. Manager reviews assignments and authority boundaries.
6. Tasks and notifications are issued after approval.
7. Relay tracks relevant changes during absence within configured scope.
8. Return Briefing Generator creates a sourced summary.
9. Original owner and manager resolve temporary assignments and outstanding actions.

### Workflow 4: Incident-to-knowledge loop (later phase)
1. An incident/postmortem is ingested from an approved system.
2. Relay links the incident to assets, responsibilities and existing procedures.
3. Knowledge Steward identifies candidate runbook or decision updates.
4. Remediation tasks are proposed.
5. Human reviewers approve the changes.
6. Continuity Debt findings are resolved or accepted with an owner and review date.

## 10.12 Agent safety, governance and privacy requirements

- Agents operate within tenant, user, case and connector scope.
- No agent may read a record solely because it appears relevant if the user lacks permission.
- Every write is validated by the backend permission layer, not trusted from LLM intent.
- Tool schemas reject unknown fields and validate IDs against tenant and actor scope.
- Use idempotency keys for external writes.
- Require human approval for configured consequential actions.
- Provide a kill switch per agent capability and per connector.
- Store versioned prompts/configuration and run traces with appropriate redaction.
- Support timeouts, retry limits, cancellation and budget limits.
- Do not use employee message volume, commit count or response speed as performance scoring.
- Do not infer sensitive personal attributes from knowledge sources.
- Allow authorised users to challenge, correct or delete erroneous inferred facts under retention and audit policy.

---

# 11. System architecture and technology decisions

## 11.1 Architectural direction

Relay should initially use a **modular monolith** with a separate background-worker process. This offers a manageable deployment and strong domain boundaries without introducing premature microservices. Modules can be extracted later if scale, security isolation or independent deployment requires it.

### High-level architecture

```text
NEXT.JS / TYPESCRIPT
  Overview | My Work | Cases | Responsibilities | Knowledge
  People & Teams | Insights | Integrations | Admin
                     |
                REST / SSE
                     |
FASTAPI APPLICATION
  Identity & Tenant Context
  Organisation / People / Teams
  Responsibilities / Assets / Ownership
  Knowledge / Evidence / Search
  Continuity Cases / Tasks / Approvals
  Integrations / Connector APIs
  Agent Orchestrator / Policies / Audit
                     |
          POSTGRESQL (SOURCE OF TRUTH)
       SQLAlchemy 2.x | Alembic | pgvector
                     |
        BACKGROUND WORKER / SCHEDULER
  Connector sync | Embedding | AI jobs | Notifications
  Scheduled reviews | Retry/reconciliation | Reports
                     |
      CONNECTED SYSTEMS / MODEL PROVIDERS
  GitHub | Linear | Notion | Later: Slack, Drive, Jira,
  Confluence, M365, HRIS, CRM and other validated sources
```

## 11.2 Technology decisions

| Layer | Selected direction | Status / rationale |
|---|---|---|
| Frontend | Next.js + TypeScript | Selected; familiar React ecosystem and suitable application shell |
| UI | Tailwind CSS + shadcn/ui | Proposed implementation choice; validate accessibility and design system |
| Data fetching | TanStack Query or equivalent | Proposed; avoid duplicating server-state logic |
| Backend | FastAPI + Python | Selected direction; aligns with AI/data ecosystem |
| Validation | Pydantic | Selected direction for API schemas and structured outputs |
| ORM | SQLAlchemy 2.x | Selected; native Python ORM and flexible relational querying |
| Migrations | Alembic | Selected with SQLAlchemy |
| Database | PostgreSQL | Selected as primary system of record |
| Async driver | asyncpg | Proposed with SQLAlchemy AsyncIO; validate deployment and library compatibility |
| Vector support | pgvector | Proposed only where semantic retrieval needs it; do not add a separate vector DB initially |
| AI orchestration | LangGraph or PydanticAI/custom orchestrator | Open decision; run a focused proof of concept and choose one primary framework |
| Workflow durability | Database-backed state machine + worker initially; Temporal later if justified | Phased decision |
| Queue/scheduler | To be selected after job-volume and hosting spike | Do not assume Redis/Celery is mandatory; choose the simplest reliable option |
| Authentication | OIDC-compatible identity provider / secure session model | Provider and implementation TBD |
| Observability | Structured logs, traces, metrics and error reporting | Required; vendor TBD |
| Deployment | Vercel frontend + Python-capable backend platform | Candidate direction; production hosting and networking require validation |

## 11.3 ORM and database conventions

- SQLAlchemy 2.x is the ORM for the Python backend; do not add Prisma or Drizzle as a second data-access layer.
- Pydantic request/response schemas must remain separate from SQLAlchemy ORM models.
- Alembic migrations are version-controlled and run through a controlled deployment step.
- Use one `AsyncSession` per concurrent task/transaction scope; do not share one `AsyncSession` across concurrent tasks [R10].
- Avoid implicit lazy-loading in asynchronous paths; design query loading deliberately.
- Use PostgreSQL constraints, indexes, foreign keys and transactions for domain integrity.
- pgvector should store embeddings linked to source/knowledge metadata; relational permissions and provenance remain authoritative [R11].
- Use raw SQL for genuinely complex/reporting operations where it improves clarity or performance; do not force every query through ORM abstractions.

## 11.4 Backend modular boundaries

Recommended modules/packages:
- `identity` — authentication context, users, identities and membership.
- `tenancy` — organisation/workspace context and isolation.
- `organisation` — departments, teams and memberships.
- `responsibilities` — responsibility catalogue and ownership assignments.
- `assets` — projects, services, processes and other asset types.
- `knowledge` — items, versions, evidence, review and search.
- `continuity` — cases, case types, lifecycle and templates.
- `tasks` — assignments, deadlines, dependencies and external sync references.
- `approvals` — approval policies and decisions.
- `integrations` — connectors, credentials, sync runs and webhooks.
- `agents` — orchestration, tools, runs, evaluation and budgets.
- `insights` — findings, continuity debt and metrics.
- `notifications` — in-app and email events.
- `audit` — immutable/security-relevant event records.
- `policy` — permission evaluation, action policies and data-use policies.

Modules should expose service interfaces and avoid direct cross-module table mutation. Domain events or application services should coordinate cross-module operations.

## 11.5 Search and retrieval

Search should support exact identifier and title search; keyword/full-text search; semantic search where useful; metadata filters (tenant, team, source, owner, type, date, criticality); permission filtering before results are returned to the user or model; source freshness and verification status; deduplication and canonical links; and hybrid ranking with optional reranking after evaluation.

Retrieval must preserve citations to original source records. A model response must not contain source material that the user is not authorised to access. Re-check permissions at query time; sync-time ACL mirrors alone may become stale.

## 11.6 RAG ingestion pipeline

1. Connector fetches a source record and permission metadata.
2. Source identity, tenant and scope are validated.
3. Content is normalised and classified within configured policy.
4. Source/version metadata is stored.
5. Content is chunked where appropriate, preserving document/section references.
6. Embeddings are produced if semantic retrieval is enabled.
7. Chunks and embeddings are linked to source and permission metadata.
8. Incremental changes update or supersede previous versions.
9. Deletion/revocation events update availability and retrieval eligibility.
10. Query-time retrieval filters by user permissions, tenant, case scope and freshness.
11. Answer generation emits citations and limitations.

## 11.7 Background processing

Workers handle connector polling and webhook processing; incremental/full reconciliation; document parsing; embedding generation; agent execution; scheduled knowledge reviews; due-date reminders; return briefings; report aggregation; and deletion/retention jobs.

Jobs must be retryable, idempotent, observable and safe to cancel. Long-running AI work must not hold open an API request.

## 11.8 Deployment environments

- Local development.
- Automated test environment.
- Staging environment with non-sensitive fixtures or approved masked data.
- Production environment.

Environment secrets must be isolated. Production connector credentials and customer content must not be copied into developer/test environments without explicit, approved controls.

---

# 12. Integration requirements

## 12.1 Connector design contract

Each connector must implement a common interface or equivalent contract:
- Authorisation handshake and credential lifecycle.
- Connection validation.
- Scope selection and exclusion rules.
- Full sync and incremental sync.
- Webhook handling where source supports it.
- Rate-limit handling and retry/backoff.
- Pagination and checkpointing.
- Normalised source identity.
- Permission/ACL extraction where source supports it.
- Record deletion/archival handling.
- Sync health and error reporting.
- Disconnect, credential revocation and data deletion/retention behaviour.

## 12.2 Initial connectors

### GitHub
Initial use cases:
- Discover repositories and organisation/team metadata within authorised scope.
- Read repository metadata, README and selected documentation.
- Retrieve issues and pull requests as configured.
- Retrieve code ownership metadata where available.
- Identify open work and related repository context.
- Create or update approved issues/tasks only when write permission is separately granted.

Do not crawl all source code by default. Use configurable repository scope, file exclusions, secret scanning and data minimisation.

### Linear
Initial use cases:
- Retrieve teams, projects, issues, assignees, statuses, labels and deadlines.
- Link tasks to responsibilities, assets and cases.
- Identify open work and project state.
- Create/update approved issues after user confirmation.
- Track external task IDs and sync state.

### Notion
Initial use cases:
- Retrieve authorised pages and database records.
- Preserve page hierarchy and source links.
- Identify knowledge items, process documents and project context.
- Generate draft updates, not silently overwrite pages.
- Respect workspace/page access restrictions where available.

## 12.3 Later connector candidates

- **Slack:** relevant channel/project context and approved messages; private messages should be excluded by default.
- **Google Drive/Docs:** policies, process docs, project docs and approved knowledge.
- **Jira/Confluence:** enterprise project and documentation ecosystems.
- **Microsoft 365/SharePoint/Teams:** enterprise documents, identity and communication context.
- **HRIS:** employee lifecycle triggers and organisation metadata, with strict purpose limitation.
- **CRM:** customer/account context and relationship handovers.
- **Service management/ticketing:** incident and support case context.

Connector priority must be validated with target customers rather than assuming all integrations are universally needed.

## 12.4 Integration health states

- Connected / Healthy.
- Connected / Syncing.
- Connected / Stale.
- Connected / Partial Failure.
- Credentials Expired.
- Permission Changed.
- Rate Limited.
- Source Unavailable.
- Paused.
- Disconnected.
- Deletion Pending.

A connector must show last successful sync, expected cadence/freshness, last error and whether its results may be incomplete.

## 12.5 Identity mapping

A person may have different IDs/emails/usernames in GitHub, Linear, Notion, HRIS and Relay. Relay needs explicit identity mapping with confidence and an admin resolution process. It must not merge people on display name alone. Unresolved matches should remain separate and be flagged rather than guessed.

---

# 13. Data model and information architecture

## 13.1 Core entities

| Entity | Purpose | Important relationships |
|---|---|---|
| Organisation | Tenant boundary and policy owner | Users, teams, roles, integrations, cases |
| User | Relay identity | Memberships, roles, assignments, audit events |
| External Identity | Mapping to source identities | User, connector, source account ID |
| Department | Organisational grouping | Teams, responsibilities, assets |
| Team | Operational group | Members, owners, assets, responsibilities |
| Responsibility | Work/accountability that must continue | Owners, assets, knowledge, cases, dependencies |
| Ownership Assignment | Time-bounded assignment record | Responsibility, person/team, role type, effective dates |
| Asset | Project, service, system, process, account or resource | Owners, dependencies, knowledge, source records |
| Dependency | Relationship between responsibilities/assets | Source/target entities, relation type, validity |
| Source Connector | External app connection | Sync runs, external identities, source records |
| Source Record | Normalised external item reference | Connector, permissions, versions, evidence |
| Knowledge Item | Curated operational knowledge | Evidence, versions, owners, reviews, cases |
| Knowledge Version | Versioned content/metadata | Knowledge item, actor, source, review |
| Evidence | Traceable support for a claim | Source record, claim/finding/knowledge item |
| Finding | Continuity issue or gap | Evidence, affected entities, tasks, case |
| Continuity Case | Managed continuity workflow | Participants, affected scope, tasks, approvals |
| Case Task | Action required to progress a case | Case, assignee, dependency, external task |
| Approval | Human decision on a scoped action | Case/task/knowledge/action, approver |
| Workflow Template | Reusable playbook | Case type, tasks, approvals, criteria |
| Workflow Instance | Running template instance | Case, state, checkpoint, version |
| Readiness Criterion | Measurable completion requirement | Case, assignee, evidence, result |
| Agent Capability | Versioned agent role/workflow | Tools, policies, evaluations |
| Agent Run | Particular execution | Trigger, inputs, tools, outputs, cost, errors |
| Tool Execution | Call to internal/external tool | Agent run, actor, approval, result |
| Audit Event | Security and accountability history | Actor, action, target, timestamp, context |
| Notification | User-facing alert | Recipient, source event, delivery status |

## 13.2 Multi-tenancy

All customer-owned domain records must be scoped to an organisation/workspace. Tenant context must be established from authenticated server-side identity, never trusted solely from a client-supplied organisation ID. Queries, jobs, vector retrieval, caches, object storage and logs must not allow cross-tenant leakage.

Database row-level security may be considered as defence in depth, but it does not replace application-layer authorisation. Every repository/service method must enforce tenant context.

## 13.3 Ownership history model

Do not store only `responsibility.owner_id`. Use an ownership-assignment table or equivalent temporal model.

Suggested fields:
- `id`
- `tenant_id`
- `responsibility_id`
- `assignee_type` (user/team/group)
- `assignee_id`
- `assignment_role` (primary/co-owner/backup/temporary)
- `effective_from`
- `effective_to` (nullable)
- `created_at`, `created_by`
- `change_reason`
- `source` and `source_reference`
- `status`

Enforce policy constraints for overlapping primary ownership, but support valid co-ownership and temporary coverage.

## 13.4 Provenance model

Every imported or generated record should have sufficient metadata to answer:
- Where did it originate?
- Which connector/account retrieved it?
- When was it last fetched?
- Which version or source revision was used?
- What permissions were observed?
- Was the content transformed or summarised?
- Which agent/model/prompt version generated a derivative?
- Who reviewed or approved it?

## 13.5 Data classification

Suggested classes:
- Public to organisation.
- Internal.
- Confidential.
- Restricted / sensitive.

Classification may be inherited from source systems or assigned by policy. Unknown classification should default to the safer configured behaviour. Sensitive content should not be placed into broad search indexes or agent contexts without explicit approval.

---

# 14. Functional software requirements (SRS)

The following requirements are testable system requirements. Priorities may be adjusted after architecture spikes and customer validation.

## 14.1 Identity, authentication and tenancy

| ID | Requirement | Priority |
|---|---|---|
| FR-IAM-001 | The system MUST authenticate users before exposing organisation data. | P0 |
| FR-IAM-002 | The system MUST derive tenant context from trusted authenticated membership, not solely from client-supplied IDs. | P0 |
| FR-IAM-003 | The system MUST support users belonging to multiple organisations/workspaces. | P1 |
| FR-IAM-004 | The system MUST support invitation, acceptance, suspension and deactivation flows. | P0 |
| FR-IAM-005 | The system MUST support multiple roles and scoped role assignments per user. | P0 |
| FR-IAM-006 | The system MUST support identity mapping between Relay users and external connector identities. | P0 |
| FR-IAM-007 | The system MUST flag ambiguous identity matches for human resolution. | P0 |
| FR-IAM-008 | The system SHOULD support OIDC/SSO for enterprise environments. | P1 |
| FR-IAM-009 | The system MUST terminate or restrict sessions according to configured deactivation/security policy. | P0 |

## 14.2 Organisation, people and teams

| ID | Requirement | Priority |
|---|---|---|
| FR-ORG-001 | An authorised administrator MUST be able to create and configure an organisation. | P0 |
| FR-ORG-002 | An administrator MUST be able to create departments and teams. | P0 |
| FR-ORG-003 | An authorised user MUST be able to assign users to teams and roles. | P0 |
| FR-ORG-004 | The system MUST preserve membership history where needed for continuity and audit. | P1 |
| FR-ORG-005 | The system MUST support contractors and external collaborators as distinct identity/member types. | P1 |
| FR-ORG-006 | The system MUST allow manual records where no integration exists. | P0 |
| FR-ORG-007 | The system MUST prevent duplicate user merges based only on display name. | P0 |
| FR-ORG-008 | An authorised admin MUST be able to resolve or reject identity-matching suggestions. | P1 |

## 14.3 Responsibilities and ownership

| ID | Requirement | Priority |
|---|---|---|
| FR-RESP-001 | An authorised user MUST be able to create, view, edit and archive a responsibility. | P0 |
| FR-RESP-002 | A responsibility MUST support user, team or group ownership. | P0 |
| FR-RESP-003 | A responsibility MUST support primary, co-owner, backup and temporary assignment roles. | P0 |
| FR-RESP-004 | Ownership changes MUST create historical assignment records rather than destructively overwriting prior assignments. | P0 |
| FR-RESP-005 | Assignments MUST support effective start and end dates. | P0 |
| FR-RESP-006 | The system MUST detect or prevent invalid overlapping primary assignments according to configured policy. | P0 |
| FR-RESP-007 | Responsibilities MUST link to assets, knowledge, procedures and dependencies. | P0 |
| FR-RESP-008 | Responsibilities MUST support criticality, review cadence and escalation metadata. | P1 |
| FR-RESP-009 | The system MUST allow a responsibility to be marked as needing human verification. | P0 |
| FR-RESP-010 | The system MUST not treat inferred ownership as confirmed ownership without review. | P0 |
| FR-RESP-011 | Users MUST be able to filter responsibilities by team, owner, backup, type, criticality and review state. | P0 |

## 14.4 Assets and dependencies

| ID | Requirement | Priority |
|---|---|---|
| FR-ASSET-001 | The system MUST support generic assets with configurable types. | P0 |
| FR-ASSET-002 | Initial asset types MUST include repositories, services/systems, projects and processes. | P0 |
| FR-ASSET-003 | Assets MUST support owners, source IDs, status, tags and criticality. | P0 |
| FR-ASSET-004 | Assets MUST link to responsibilities, knowledge items, cases and tasks. | P0 |
| FR-ASSET-005 | The system SHOULD support typed metadata schemas for different asset types. | P1 |
| FR-ASSET-006 | Dependencies MUST include relation type, source, target and provenance. | P1 |
| FR-ASSET-007 | A graph visualisation MAY display relationships but MUST NOT be required to complete workflows. | P1 |
| FR-ASSET-008 | The system MUST support archived/deleted source assets and show their unavailable state. | P1 |

## 14.5 Continuity Cases

| ID | Requirement | Priority |
|---|---|---|
| FR-CASE-001 | An authorised user MUST be able to create a Continuity Case manually. | P0 |
| FR-CASE-002 | Initial case types MUST include ownership transfer, temporary absence coverage and new-owner onboarding. | P0 |
| FR-CASE-003 | The case model MUST permit future types such as offboarding, project transfer, service transfer, account handover and emergency continuity. | P0 |
| FR-CASE-004 | A case MUST record its initiator, accountable manager, scope, participants, dates, type, status and priority. | P0 |
| FR-CASE-005 | A case MUST link to affected responsibilities and assets. | P0 |
| FR-CASE-006 | A case MUST maintain a timestamped status history. | P0 |
| FR-CASE-007 | Case state changes MUST be validated against role, case type and required criteria. | P0 |
| FR-CASE-008 | The system MUST support Draft, Investigating, Awaiting Input, Awaiting Review, Ready for Transfer, In Progress, Verification, Completed, Blocked, Cancelled and Reopened states or approved equivalents. | P0 |
| FR-CASE-009 | The system MUST detect likely duplicate active cases and allow an authorised user to proceed or link them. | P1 |
| FR-CASE-010 | A case MUST support blockers, exceptions, deadlines and escalation. | P0 |
| FR-CASE-011 | The system MUST preserve cancelled and reopened case history. | P0 |
| FR-CASE-012 | A high-criticality case MUST NOT close without required approvals and readiness criteria unless an authorised exception is recorded. | P0 |

## 14.6 Tasks, approvals and readiness

| ID | Requirement | Priority |
|---|---|---|
| FR-TASK-001 | A case MUST support tasks with assignee, creator, due date, priority, status and dependencies. | P0 |
| FR-TASK-002 | Tasks MUST be assignable to a user or team. | P0 |
| FR-TASK-003 | A task MUST identify whether it is Relay-native or mirrored to an external system. | P0 |
| FR-TASK-004 | External tasks MUST retain external IDs, URLs and sync state. | P0 |
| FR-TASK-005 | Tasks MUST support completion evidence and comments. | P1 |
| FR-TASK-006 | The system MUST support approval requests with scope, approver, deadline, decision, comment and timestamp. | P0 |
| FR-TASK-007 | Approval must be bound to the specific version/scope of the content or action being approved. | P0 |
| FR-TASK-008 | If approved content materially changes, prior approval MUST be invalidated or re-evaluated according to policy. | P0 |
| FR-TASK-009 | Readiness criteria MUST be explicit, measurable and linked to evidence where appropriate. | P0 |
| FR-TASK-010 | Readiness results MUST support pass, fail, needs human review and unable to assess. | P0 |
| FR-TASK-011 | The system MUST not infer readiness solely from document views or chat engagement. | P0 |

## 14.7 Knowledge and evidence

| ID | Requirement | Priority |
|---|---|---|
| FR-KNOW-001 | The system MUST store knowledge metadata, owner, scope, type, status, version and review date. | P0 |
| FR-KNOW-002 | Knowledge items MUST retain source provenance or explicitly be marked as Relay-authored. | P0 |
| FR-KNOW-003 | The system MUST support evidence records linked to claims, findings, knowledge items and cases. | P0 |
| FR-KNOW-004 | Users MUST be able to distinguish verified, draft, disputed, stale, expired and inaccessible knowledge. | P0 |
| FR-KNOW-005 | The system MUST preserve version history for Relay-managed knowledge. | P0 |
| FR-KNOW-006 | The system MUST support authorised review and verification assignments. | P0 |
| FR-KNOW-007 | The system SHOULD detect potential duplicate and conflicting knowledge items. | P1 |
| FR-KNOW-008 | The system MUST allow a reviewer to dispute or reject AI-generated content with a reason. | P0 |
| FR-KNOW-009 | The system MUST support search filters for source, owner, type, team, status, freshness and permissions. | P0 |
| FR-KNOW-010 | AI-generated knowledge MUST be labelled as draft until required review is complete. | P0 |
| FR-KNOW-011 | A source deletion or revocation MUST update the availability and retrieval eligibility of dependent evidence. | P0 |
| FR-KNOW-012 | The system MUST support Context Capsules with scoped source links and approved excerpts. | P1 |
| FR-KNOW-013 | The system SHOULD support knowledge review schedules and validity windows. | P1 |
| FR-KNOW-014 | The system MUST distinguish direct source facts, deterministic rules, AI inference and human decisions. | P0 |

## 14.8 Continuity Intelligence

| ID | Requirement | Priority |
|---|---|---|
| FR-CI-001 | The system MUST detect critical responsibilities with missing primary owners. | P0 |
| FR-CI-002 | The system MUST detect missing backups where policy requires them. | P0 |
| FR-CI-003 | The system SHOULD detect stale critical knowledge using configurable review and source-change signals. | P1 |
| FR-CI-004 | The system SHOULD identify potential mismatches between declared ownership and source activity/metadata. | P1 |
| FR-CI-005 | Every finding MUST include evidence, scope, detection basis, status and recommended remediation. | P0 |
| FR-CI-006 | Inferred findings MUST be labelled and reviewable. | P0 |
| FR-CI-007 | The system MUST support assignment, dismissal with reason, resolution and accepted-risk states. | P0 |
| FR-CI-008 | The system MUST maintain a Continuity Debt backlog. | P1 |
| FR-CI-009 | Risk prioritisation MUST be explainable and configurable. | P1 |
| FR-CI-010 | The system MUST not rank employee performance using continuity findings. | P0 |

## 14.9 Search and AI answers

| ID | Requirement | Priority |
|---|---|---|
| FR-SEARCH-001 | Users MUST be able to search permitted responsibilities, assets, cases and knowledge. | P0 |
| FR-SEARCH-002 | Search results MUST be filtered by tenant and effective permissions before presentation. | P0 |
| FR-SEARCH-003 | AI answers MUST cite source records when based on connected content. | P0 |
| FR-SEARCH-004 | AI answers MUST state when evidence is missing, stale, conflicting or inaccessible. | P0 |
| FR-SEARCH-005 | The system SHOULD support hybrid keyword and semantic retrieval. | P1 |
| FR-SEARCH-006 | The system MUST preserve source links and timestamps. | P0 |
| FR-SEARCH-007 | The system MUST not use inaccessible source content in answer generation. | P0 |
| FR-SEARCH-008 | Users SHOULD be able to provide feedback or report an incorrect answer. | P1 |

## 14.10 Agent orchestration and tools

| ID | Requirement | Priority |
|---|---|---|
| FR-AGENT-001 | The system MUST persist agent runs and their state. | P0 |
| FR-AGENT-002 | Agent capabilities MUST have explicit tool allowlists. | P0 |
| FR-AGENT-003 | Tool calls MUST validate tenant, actor, case and resource scope on the server. | P0 |
| FR-AGENT-004 | Agent output MUST conform to versioned structured schemas for workflow-critical outputs. | P0 |
| FR-AGENT-005 | Agent findings MUST include evidence references or explicitly state that evidence is unavailable. | P0 |
| FR-AGENT-006 | The system MUST support human approval gates before configured consequential actions. | P0 |
| FR-AGENT-007 | The system MUST use idempotency controls for external write operations. | P0 |
| FR-AGENT-008 | Agent runs MUST support timeout, cancellation, retry limits and failure state. | P0 |
| FR-AGENT-009 | Agent runs MUST record tool calls, outputs, approvals, errors and side effects. | P0 |
| FR-AGENT-010 | Administrators MUST be able to disable a capability or connector. | P0 |
| FR-AGENT-011 | The system MUST support per-run and per-tenant cost/usage limits. | P1 |
| FR-AGENT-012 | The system SHOULD support offline evaluation datasets and regression tests for agent capabilities. | P1 |
| FR-AGENT-013 | The system MUST treat retrieved source content as untrusted data and defend against prompt injection. | P0 |
| FR-AGENT-014 | Agents MUST not make autonomous employment, promotion, termination or performance decisions. | P0 |
| FR-AGENT-015 | Agent actions MUST execute under an auditable user/service identity with explicit scope. | P0 |
| FR-AGENT-016 | The system MUST allow authorised users to review, correct or reject agent outputs. | P0 |

## 14.11 Integrations and connectors

| ID | Requirement | Priority |
|---|---|---|
| FR-INT-001 | The system MUST support a common connector lifecycle interface. | P0 |
| FR-INT-002 | Initial release MUST provide GitHub, Linear and Notion connector paths or a demonstrable connector integration for each. | P0 |
| FR-INT-003 | Connectors MUST store encrypted credentials/tokens using a managed secret mechanism. | P0 |
| FR-INT-004 | Connectors MUST support configurable source scope and exclusions. | P0 |
| FR-INT-005 | Connectors MUST support incremental sync and a reconciliation path. | P0 |
| FR-INT-006 | Webhook handlers MUST validate signatures/tokens where the source supports them. | P0 |
| FR-INT-007 | Connector sync MUST be idempotent and checkpointed. | P0 |
| FR-INT-008 | Connector health MUST expose last successful sync and incomplete/error state. | P0 |
| FR-INT-009 | Connectors MUST handle pagination, rate limits, retries and source outages. | P0 |
| FR-INT-010 | Source permission metadata MUST be ingested where available and checked during retrieval. | P0 |
| FR-INT-011 | Credential expiry or scope revocation MUST be visible to administrators. | P0 |
| FR-INT-012 | Disconnect MUST stop new fetches and invoke configured retention/deletion handling. | P0 |
| FR-INT-013 | The system SHOULD support Slack, Google Workspace, Jira, Confluence and Microsoft 365 in later phases. | P2 |
| FR-INT-014 | The system MUST reconcile duplicate webhook deliveries and out-of-order events. | P0 |

## 14.12 Notifications

| ID | Requirement | Priority |
|---|---|---|
| FR-NOTIF-001 | The system MUST provide in-app notifications for assignments, approvals and case updates. | P0 |
| FR-NOTIF-002 | The system SHOULD support email notifications for critical workflow events. | P1 |
| FR-NOTIF-003 | Users MUST be able to manage non-mandatory notification preferences. | P1 |
| FR-NOTIF-004 | Notifications MUST avoid exposing sensitive source content by default. | P0 |
| FR-NOTIF-005 | The system MUST prevent duplicate/repeated notifications from retried events. | P0 |
| FR-NOTIF-006 | The system SHOULD support digesting and grouping of low-priority events. | P2 |

## 14.13 Administration, audit and reporting

| ID | Requirement | Priority |
|---|---|---|
| FR-ADMIN-001 | Administrators MUST be able to manage organisation settings and members. | P0 |
| FR-ADMIN-002 | Administrators MUST be able to manage connector scope and health. | P0 |
| FR-ADMIN-003 | Administrators MUST be able to inspect agent configuration, runs and failures. | P0 |
| FR-ADMIN-004 | The system MUST record security-relevant actions in an audit log. | P0 |
| FR-ADMIN-005 | Audit events MUST include actor, action, target, timestamp, tenant and relevant context. | P0 |
| FR-ADMIN-006 | Audit records MUST be protected against unauthorised modification. | P0 |
| FR-ADMIN-007 | The system SHOULD support configurable retention policies. | P1 |
| FR-ADMIN-008 | Reports MUST show definitions, data scope, filters and time range. | P0 |
| FR-ADMIN-009 | The system MUST provide export only to authorised roles and log export actions. | P1 |
| FR-ADMIN-010 | The system MUST support deletion/retention workflows for source and Relay data subject to policy. | P0 |

---

# 15. Non-functional requirements

The following targets are provisional and must be validated with realistic load, deployment and dataset sizes.

## 15.1 Performance

| ID | Requirement / target | Priority |
|---|---|---|
| NFR-PERF-001 | Typical authenticated read API requests SHOULD achieve p95 latency below 500 ms under agreed baseline load, excluding external-source calls and expensive search. | P1 |
| NFR-PERF-002 | Typical write API requests SHOULD achieve p95 latency below 800 ms under agreed baseline load, excluding external-source calls. | P1 |
| NFR-PERF-003 | Long-running connector and agent operations MUST run asynchronously and return a job/run reference promptly. | P0 |
| NFR-PERF-004 | Search SHOULD return initial results within 2 seconds at the initial target dataset size, subject to benchmark validation. | P1 |
| NFR-PERF-005 | The application MUST paginate large lists and avoid unbounded result retrieval. | P0 |
| NFR-PERF-006 | Background workers MUST apply concurrency limits per tenant and connector. | P0 |

## 15.2 Availability and resilience

| ID | Requirement / target | Priority |
|---|---|---|
| NFR-REL-001 | The service SHOULD target 99.5% monthly availability for the initial hosted release, excluding declared maintenance and external provider outages. | P1 |
| NFR-REL-002 | Database backups MUST be automated and restoration MUST be periodically tested. | P0 |
| NFR-REL-003 | Background jobs MUST be retryable and idempotent. | P0 |
| NFR-REL-004 | External dependency failure MUST not corrupt the local case state. | P0 |
| NFR-REL-005 | The system MUST expose degraded/partial states when integrations or AI providers are unavailable. | P0 |
| NFR-REL-006 | Case state and approvals MUST be persisted independently of a transient agent process. | P0 |
| NFR-REL-007 | A workflow MUST be recoverable after worker or application restart. | P0 |

## 15.3 Scalability

- The modular monolith should support horizontal scaling of stateless API instances.
- Background workers should scale separately from API servers.
- Connector sync concurrency should be configurable per tenant/source.
- Large ingestion jobs should use checkpoints and bounded batches.
- Vector search should be benchmarked before index strategy changes.
- Tenant hotspots must not starve other tenants.
- Database indexes must be based on query patterns and measured plans.

## 15.4 Security

- TLS for all network transport.
- Encryption at rest for database, object storage and backups as supported by hosting platform.
- Secrets stored in a managed secrets system, never in source control or client bundles.
- Strict authentication and authorisation on all API routes.
- Tenant isolation in API, database access, background jobs, caches and vector search.
- Rate limiting and abuse protection for sensitive workflows.
- Webhook signature validation.
- Dependency and container scanning.
- Secure file parsing and size/type limits.
- SSRF protection for any URL fetching/import feature.
- Protection against broken object-level and function-level authorisation.
- Audit logging for access, approvals, exports and external writes.

OWASP API Security Top 10 is a baseline reference for API threats including broken object-level authorisation, broken authentication, unrestricted resource consumption, security misconfiguration and unsafe API consumption [R12].

## 15.5 Privacy and data governance

- Minimise ingestion to the sources and scopes needed for approved workflows.
- Mirror source permissions where available and re-check access at query/action time.
- Store content and metadata in tenant-isolated boundaries.
- Exclude private messages and sensitive HR data by default.
- Provide data-use explanations and configurable source exclusions.
- Support data export and deletion requests under defined retention and legal-hold rules.
- Establish retention periods for raw source content, derived knowledge, agent traces and audit records.
- Redact credentials, tokens and sensitive content from logs.
- Avoid training external/public models on customer data unless separately and explicitly authorised under contract/policy.
- Conduct legal and privacy review for applicable jurisdictions before commercial deployment. This document is not legal advice or a compliance certification.

## 15.6 Maintainability

- Type-checked Python and TypeScript.
- Versioned API contracts and schema migrations.
- Modular domain boundaries.
- Automated tests for permission and tenant isolation.
- Structured logs and correlated trace IDs.
- Documented runbooks for deployment, backup, restore and incident response.
- Linting, formatting and static analysis in CI.
- No direct database access from frontend code.
- No duplicate ORM/data-access layers.

## 15.7 Usability and accessibility

- Core tasks should be understandable without AI knowledge.
- Case creation should ask only necessary initial questions.
- Important actions should be visible and contextually placed.
- Search and tables should support filtering and keyboard access.
- Status should not rely on colour alone.
- Errors should explain what happened and how to recover.
- Recommend WCAG 2.2 AA as a project accessibility target, subject to audit.

## 15.8 Observability

Track API request rate, latency, errors and saturation; database pool health and slow queries; connector sync latency, failure, rate limiting and stale-source count; queue depth and worker execution age; agent run duration, cost, tool-call success and approval wait time; search latency and retrieval quality; notification delivery success; audit event persistence failures.

Use correlation IDs across API requests, workflow instances, agent runs and connector jobs. Do not log raw sensitive content by default.

---

# 16. API, event and background-processing requirements

## 16.1 API conventions

- Version the public API (e.g. `/api/v1`).
- Use resource-oriented endpoints and consistent response envelopes.
- Validate all request bodies with Pydantic.
- Return stable machine-readable error codes and human-readable descriptions.
- Use cursor pagination for large or frequently changing collections where appropriate.
- Use idempotency keys for external writes and other non-repeatable actions.
- Enforce authorisation at the service/domain layer, not only at the router.
- Use optimistic concurrency/version checks for sensitive mutable records.
- Never trust client-supplied tenant IDs or role claims.

## 16.2 Representative endpoint groups

These are illustrative, not a final OpenAPI contract.

```text
/api/v1/organisations
/api/v1/users
/api/v1/teams
/api/v1/responsibilities
/api/v1/ownership-assignments
/api/v1/assets
/api/v1/dependencies
/api/v1/knowledge
/api/v1/evidence
/api/v1/findings
/api/v1/continuity-cases
/api/v1/continuity-cases/{case_id}/tasks
/api/v1/continuity-cases/{case_id}/approvals
/api/v1/continuity-cases/{case_id}/readiness
/api/v1/integrations
/api/v1/integrations/{connector_id}/sync-runs
/api/v1/agent-runs
/api/v1/agent-runs/{run_id}/approvals
/api/v1/insights
/api/v1/audit-events
```

## 16.3 Event model

Events should be versioned and include event ID, tenant ID, occurred-at timestamp, actor, entity type/ID, correlation ID and payload version.

Candidate events:
- `responsibility.created`
- `ownership.assignment.created`
- `ownership.assignment.ended`
- `asset.updated`
- `source.record.changed`
- `connector.sync.started`
- `connector.sync.completed`
- `connector.sync.failed`
- `knowledge.review.due`
- `knowledge.conflict.detected`
- `continuity.finding.created`
- `continuity.case.created`
- `continuity.case.state_changed`
- `continuity.task.assigned`
- `continuity.task.completed`
- `approval.requested`
- `approval.decided`
- `agent.run.started`
- `agent.run.completed`
- `agent.run.failed`
- `readiness.result.submitted`
- `continuity.case.completed`

Events must be processed idempotently. Out-of-order events should be reconciled using source timestamps, event versions and periodic source reconciliation.

## 16.4 Workflow persistence

Initial release may use a database-backed state machine and background workers. Persist workflow state, checkpoints, pending approvals, deadlines, retry metadata and template version. Do not rely on an in-memory agent conversation as the source of workflow truth.

Consider Temporal if workflows become long-running, timer-heavy, cross-service and operationally complex enough to justify a dedicated durable workflow platform [R9].

---

# 17. Edge cases and failure-handling catalogue

The following cases are mandatory design and test considerations. The exact response may vary by policy, but the system must not silently ignore them.

## 17.1 People and ownership

| Edge case | Expected behaviour |
|---|---|
| Employee leaves unexpectedly | Create urgent case from available authorised data; mark interview unavailable; show unknowns |
| Current owner unavailable | Route questions to manager/SME; do not block the entire case indefinitely |
| No incoming owner identified | Keep case in Awaiting Assignment/Blocked; suggest role/team options, not an invented person |
| Multiple co-owners | Preserve shared ownership and split tasks by responsibility scope |
| Temporary absence extended | Update effective dates and review coverage; do not silently expire old assignments |
| Employee returns early | Reconcile temporary assignments and create a return briefing |
| Incoming owner declines | Reopen assignment decision and require authorised reassignment |
| Manager changes mid-case | Transfer approval authority according to policy; preserve original actions |
| Person exists under multiple external identities | Flag match conflict; do not merge by name alone |
| Contractor access ends | Separate knowledge-transfer and access-removal workflows; require source-system authority |
| No formal team structure | Allow responsibility to be assigned at organisation or project scope |
| Owner is a team rather than a person | Support team/group ownership and explicit accountable contact where required |

## 17.2 Knowledge and evidence

| Edge case | Expected behaviour |
|---|---|
| Two sources conflict | Present both with timestamps/authority metadata and request resolution |
| Newer source is not authoritative | Apply configured source authority; do not assume newest is correct |
| No evidence exists | Mark as unverified inference or unknown |
| Source is deleted | Mark evidence unavailable; apply retention policy and preserve lawful audit metadata |
| Source permission is revoked | Remove from retrieval immediately after detection; re-check ACL at access time |
| Knowledge item is stale | Flag review; do not automatically claim it is incorrect |
| Duplicate documents | Suggest canonical item and preserve links; do not delete automatically |
| Knowledge is region-specific | Preserve applicability scope and avoid applying one region's rule globally |
| Knowledge has restricted content | Restrict or redact; do not place in a general context capsule |
| Outgoing owner disputes content | Keep disputed state, collect correction and route review |
| AI draft is edited by human | Record human edit/version; re-evaluate approval scope |
| Evidence link expires | Mark unavailable and request refresh; do not leave a silent broken citation |

## 17.3 Integration failures

| Edge case | Expected behaviour |
|---|---|
| OAuth credential expires | Mark connector attention-required; notify admin; keep old data labelled with last-sync time |
| Scope revoked | Restrict affected content and show permission change |
| API rate limit | Back off, checkpoint and retry; expose delayed sync state |
| Duplicate webhook | Process idempotently using event/source identity |
| Out-of-order webhook | Reconcile using source version/timestamp and scheduled sync |
| Source outage | Do not mark sync healthy; queue retry and show stale state |
| Partial sync failure | Preserve successful records but clearly show incomplete sync and affected scope |
| Repository/page renamed | Resolve stable source identity; update display name and canonical URL |
| Source record archived/deleted | Update source state and relevant case/evidence links |
| Connector disconnected | Stop sync and apply configured retention/deletion rules |
| External write times out after success | Query external source by idempotency/correlation key before retrying |
| Rate-limited tenant | Apply per-tenant fairness and avoid starving other organisations |

## 17.4 Workflow failures

| Edge case | Expected behaviour |
|---|---|
| Case cancelled | Stop pending jobs, mark open tasks appropriately and retain audit history |
| Case deadline changes | Recompute reminders and show who changed it |
| Duplicate cases | Suggest linking/merging scope; do not silently merge records |
| Approval rejected | Return to draft/review with reason and required remediation |
| Approved content changes | Revoke or re-request approval based on change severity |
| External task completed outside Relay | Reconcile and update status with source timestamp |
| Task remains blocked | Escalate according to configured policy, not infinite reminders |
| Case partially complete | Support partial completion and explicit unresolved exceptions |
| One department completes and another does not | Keep overall case open or show scoped completion; do not imply global success |
| Case reopened | Preserve prior closure and start a new status segment/reason |
| Person unavailable for approval | Use authorised fallback approver or mark blocked |
| Source of truth changes during case | Refresh affected findings and invalidate outdated proposals as needed |

## 17.5 Agent failures

| Edge case | Expected behaviour |
|---|---|
| Hallucinated responsibility | Require evidence and human review; do not create confirmed responsibility |
| Wrong identity match | Flag ambiguity and avoid assigning sensitive content |
| Stale context | Check source freshness; request refresh or label limitation |
| Tool call contains wrong tenant ID | Backend rejects; security event logged |
| Agent asks for inaccessible content | Tool returns permission denial without leaking hidden content beyond policy |
| Prompt injection in source document | Treat as untrusted content; never override agent/system policy |
| Duplicate external task creation | Idempotency key and reconciliation prevent duplicate side effect |
| Agent run times out | Persist checkpoint/status; offer retry/resume where safe |
| Model/provider unavailable | Mark run failed/degraded; keep deterministic workflow usable |
| Token/cost budget exceeded | Stop or request authorised budget increase; do not silently continue |
| Conflicting agent outputs | Surface conflict and request human decision |
| Agent produces unsupported answer | Mark evidence insufficient and avoid presenting as verified |
| User rejects proposal | Capture feedback/reason; do not automatically re-propose the same action repeatedly |
| Agent tool permission changes during run | Revalidate before each action; stop if permission has been revoked |

## 17.6 Security and privacy edge cases

- Cross-tenant query, cache or vector-search leakage must be blocked and tested.
- A manager must not receive private content solely because an employee is leaving.
- Incoming owner must not inherit source permissions automatically.
- Case participants must not see unrelated case records.
- Export must be authorised and audited.
- Sensitive data must be redacted from logs and notifications.
- Source ACL revocation must invalidate cached/retrieved access.
- Untrusted document content must not be allowed to trigger agent tools.
- Deletion and retention requests must cover source-derived chunks/embeddings where policy requires.
- A connector's broad technical scope must not imply every user can search all ingested content.

## 17.7 UX and degraded operation

- If no integrations are connected, allow manual responsibility and case workflows.
- If only one connector is available, scope analysis to that source and state limitations.
- If analysis is incomplete, show which sources were unavailable.
- If there is no backup owner, provide a clear assignment action.
- If the user lacks permission, explain the required role/admin path without revealing restricted content.
- If a task is external, provide a source link and last sync time.
- If the source has been deleted, show an unavailable state and appropriate next action.
- If a user is on mobile, allow review/approval and task completion without exposing complex admin setup.

---

# 18. Testing strategy and acceptance criteria

## 18.1 Test layers

1. Unit tests for domain rules, state transitions, permissions, schemas and idempotency.
2. Integration tests for database transactions, migrations, connectors and job processing.
3. Contract tests for external APIs and connector normalisation.
4. End-to-end tests for core case workflows.
5. Agent evaluation tests for retrieval, evidence, structured output, tool selection and prompt-injection resilience.
6. Security tests for tenant isolation, object-level authorisation, role boundaries and source ACLs.
7. Load tests for connector sync, search, case lists and background queues.
8. Recovery tests for worker restart, provider failure, database restore and webhook duplication.
9. Accessibility tests for keyboard, focus, labels and contrast.
10. Usability tests with users unfamiliar with Relay.

## 18.2 Core release acceptance scenarios

### AC-01: Create and complete an ownership transfer
- **Given** an authorised manager and a responsibility with a current owner.
- **When** the manager creates an ownership-transfer case and selects an incoming owner.
- **Then** Relay discovers permitted linked context, creates a case, shows evidence and gaps, proposes tasks, routes approvals and records readiness.
- The case can only close after required criteria or an approved exception are recorded.

### AC-02: Incomplete source coverage
- **Given** GitHub is connected but Linear is unavailable.
- **When** an impact analysis runs.
- **Then** Relay shows GitHub-derived findings, marks Linear data unavailable/stale and does not claim the analysis is complete.

### AC-03: Permission revocation
- **Given** a user previously could access a source item but the permission is revoked.
- **When** the user searches or opens a related AI answer.
- **Then** the source must no longer be exposed after the revocation is recognised, and retrieval must enforce current permissions.

### AC-04: Agent proposal requires approval
- **Given** an agent proposes creating external tasks.
- **When** the plan is prepared.
- **Then** no external task is created until an authorised approver approves the exact proposed changes.

### AC-05: Duplicate webhook
- **Given** the same source event is delivered more than once.
- **When** it is processed.
- **Then** only one logical update and one set of downstream side effects are produced.

### AC-06: Employee unavailable
- **Given** the current owner cannot complete an interview.
- **When** a manager initiates an emergency or urgent transition.
- **Then** Relay proceeds using authorised existing data, marks unresolved questions and routes them to an appropriate manager/SME.

### AC-07: Knowledge conflict
- **Given** two permitted sources provide contradictory steps.
- **When** Relay prepares a knowledge answer or handover.
- **Then** both sources and timestamps are displayed, the conflict is flagged and no single version is silently marked authoritative.

### AC-08: Temporary absence and return
- **Given** an absence case with start/end date and approved backup.
- **When** work changes during the absence.
- **Then** relevant authorised changes are recorded and a sourced return briefing is available when the employee returns.

### AC-09: Multi-tenant isolation
- **Given** two organisations have records with overlapping external identifiers.
- **When** one tenant queries or triggers an agent run.
- **Then** the request cannot access records, vectors, cached results, jobs or audit data belonging to the other tenant.

### AC-10: Agent timeout and recovery
- **Given** an agent run times out after a checkpoint.
- **When** an authorised retry/resume is requested.
- **Then** the workflow resumes from a safe checkpoint or restarts idempotently without duplicating external side effects.

## 18.3 Agent evaluation set

Maintain a curated test set covering clear evidence and correct ownership; ambiguous identities; conflicting documents; missing sources; stale sources; permission-restricted sources; malicious prompt instructions in source content; duplicated source events; unsupported claims; incorrect task suggestions; high- and low-criticality cases; and human correction/rejection paths.

Every material prompt, model, retrieval or tool-schema change should run regression evaluations. Use representative, permission-sensitive test data. Evaluation datasets must not contain real employee-sensitive content unless explicitly authorised and protected.

## 18.4 Release quality gates

A release should not proceed if:
- Tenant isolation tests fail.
- Critical authorisation tests fail.
- Agent tools can bypass backend permission checks.
- External write operations are not idempotent.
- Case history can be lost on retry/cancellation.
- Source permission revocation is not handled.
- Sensitive source content leaks into logs or notifications.
- Critical workflow acceptance scenarios are failing.
- Database migrations cannot be safely applied or rolled back according to the release plan.

---

# 19. Release plan and delivery priorities

## 19.1 Phase 0 — Foundations and validation

- Validate initial customer pain with engineering managers and team leads.
- Validate the three initial workflows: ownership transfer, absence coverage and new-owner onboarding.
- Confirm minimum connector scopes for GitHub, Linear and Notion.
- Design the responsibility and Continuity Case domain model.
- Prove tenant isolation and source permission filtering early.
- Select agent orchestration approach through a small proof of concept.
- Define data retention and sensitive-data exclusions.

## 19.2 Phase 1 — First usable release

### Platform foundation
- Organisation, user, team and role model.
- Responsibility catalogue and ownership history.
- Generic asset model.
- Knowledge records and evidence.
- Continuity Case engine and state machine.
- Tasks, approvals and audit trail.

### User experience
- Overview.
- My Work.
- Continuity Cases list and detail.
- Responsibilities catalogue/detail.
- Knowledge search/review.
- Integration status.

### Integrations
- GitHub.
- Linear.
- Notion.

### Intelligence and agents
- Permission-aware discovery.
- Impact analysis.
- Knowledge gap detection.
- Handover Planner.
- Knowledge Interviewer.
- Knowledge Steward draft/review.
- Readiness Verifier.
- Human approval gates.

### First case templates
- Ownership transfer.
- Temporary absence coverage.
- New-owner onboarding.

## 19.3 Phase 2 — Cross-functional workflows

- Slack and Google Workspace/Microsoft 365 candidates based on customer demand.
- HRIS integration under strict data minimisation and policy controls.
- Employee offboarding and internal role transfer.
- Project, account and process handovers.
- Incident-to-knowledge loop.
- Better knowledge freshness and conflict resolution.
- More configurable responsibility/asset types.
- Advanced Insights and reporting.

## 19.4 Phase 3 — Enterprise continuity platform

- Custom workflow/playbook builder.
- Expanded enterprise connectors.
- SSO and advanced identity governance.
- More advanced retention, legal hold and audit controls.
- Continuity simulation.
- Cross-department dependency analysis.
- Workflow durability platform such as Temporal if justified.
- Agent capability administration and policy templates.

## 19.5 Prioritisation framework

Prioritise features based on customer pain and frequency; business impact of failure; ability to prove value in a demo/pilot; data availability and integration feasibility; security/privacy risk; implementation cost and operational complexity; and dependencies on other features.

A visually impressive feature should not outrank a dependable core workflow.

---

# 20. Product analytics and operational telemetry

## 20.1 Product events

Candidate analytics events:
- `case_created`
- `case_scope_confirmed`
- `impact_analysis_completed`
- `finding_created`
- `finding_resolved`
- `knowledge_draft_created`
- `knowledge_review_approved`
- `knowledge_review_rejected`
- `task_assigned`
- `task_completed`
- `approval_requested`
- `approval_decided`
- `readiness_criterion_completed`
- `readiness_submitted`
- `case_completed`
- `case_reopened`
- `connector_sync_failed`
- `agent_run_completed`
- `agent_run_corrected`
- `agent_run_rejected`

Avoid collecting more personal activity data than needed. Product analytics must be tenant-configurable and privacy-reviewed.

## 20.2 Operational telemetry

Monitor infrastructure and reliability separately from product outcomes: API performance; database health; worker health and backlog; connector sync latency and error rate; agent latency, cost and failure rate; search performance and evaluation quality; notification delivery; audit persistence; and data deletion/retention job completion.

## 20.3 Feedback loops

A user should be able to mark an answer as incorrect; correct a responsibility or owner suggestion; reject a proposed task; flag a document as stale or authoritative; explain why a finding is irrelevant; or request that a source be excluded from a case.

Feedback should improve quality through explicit evaluation and review. It must not be used to silently train a model on customer content without an appropriate agreement and policy.

---

# 21. Risks, assumptions and open decisions

## 21.1 Product risks

| Risk | Potential impact | Mitigation |
|---|---|---|
| Product scope becomes too broad | Poor execution and unclear value | Launch engineering-led; reuse generic model; phase workflows |
| Existing competitors overlap heavily | Weak differentiation | Focus on continuity lifecycle and measurable transfer outcomes; validate willingness to pay |
| Poor source data | Incorrect findings and low trust | Show gaps, allow manual correction, maintain evidence and confidence |
| Connector permissions are complex | Data leakage risk | Source ACL mirroring, query-time checks and permission tests |
| AI produces unsupported claims | Incorrect decisions | Evidence requirements, structured output, human review and evaluation |
| Agents create unwanted side effects | Operational disruption | Read/draft by default, approval gates, idempotency and kill switch |
| Integration maintenance burden | Engineering cost | Start with three connectors and shared connector contract |
| Product feels like another dashboard | Low adoption | Action-centred UX, contextual workflow integration and clear user tasks |
| Continuity metrics become employee surveillance | Trust and legal risk | Measure responsibility/process coverage, not individual productivity |
| Knowledge becomes stale despite sync | Misleading answers | Source freshness, verification windows and explicit stale states |
| Broad ingestion increases cost | High infrastructure/model spend | Scope controls, incremental sync, content limits and per-tenant budgets |
| Users do not complete interviews or reviews | Cases stall | Minimal-friction prompts, escalation, fallback sources and exception paths |

## 21.2 Assumptions

- Organisations will connect approved sources if value and permissions are clear.
- GitHub, Linear and Notion are useful initial sources for an engineering-led launch.
- Managers and employees will participate in structured transfer workflows if the effort is lower than current manual processes.
- Responsibility records can begin manually and become richer through integration.
- PostgreSQL is sufficient for the first domain model and initial vector retrieval needs.
- The first release can use a database-backed workflow engine and background workers.
- All external write operations can be separated from read/discovery and gated by approvals.

These assumptions require validation with pilot users.

## 21.3 Open technical decisions

1. Agent framework: LangGraph vs PydanticAI vs a small custom orchestrator. Choose one after a narrow workflow proof of concept; do not combine multiple frameworks without a demonstrated need.
2. Queue/scheduler: choose after validating background job volume, retry, scheduling and hosting requirements. Redis/Celery is an option, not a fixed requirement.
3. Authentication provider and SSO plan.
4. Object storage choice for permitted file snapshots/exports, if needed.
5. Search implementation: PostgreSQL full-text + pgvector initially, with external search only if benchmarks require it.
6. Model provider strategy and data-processing terms.
7. Notification email provider.
8. Hosting platform and network boundaries for Python backend, database and workers.
9. Exact connector scopes and write permissions.
10. Retention periods and legal review by launch jurisdiction.

## 21.4 Open product decisions

1. Whether the initial release includes a formal offboarding workflow or focuses on ownership transfer, absence and onboarding.
2. Whether Context Capsules are generated on demand, stored as versioned artefacts, or both.
3. How responsibility criticality is configured and who can assign it.
4. Whether readiness criteria are universal, template-defined or fully custom.
5. Whether customers can create custom case types in phase 2 or only configure existing templates.
6. Which cross-functional connector after the initial engineering stack has the highest customer value.
7. How much customer data is retained after source disconnection/deletion.
8. Which metrics are visible to managers vs administrators and employees.

## 21.5 Decisions already established in discussion

- Relay is a broad organisational continuity platform, not solely an engineering handover tool.
- Engineering-led organisations are the initial entry market, not the permanent product boundary.
- The product must support permanent transitions, temporary absence, onboarding, project handovers and later cross-functional continuity workflows.
- Responsibility and Continuity Case are central domain concepts.
- The graph is optional and secondary; it is not the primary user value.
- UI should centre on Overview, My Work, Cases, Responsibilities, People & Teams, Knowledge, Insights and administration.
- AI agents are specialised capabilities coordinated by a controlled orchestrator, not unrestricted autonomous bots.
- Evidence, permissions, human review, idempotency and auditability are foundational.
- Frontend direction: Next.js + TypeScript.
- Backend direction: FastAPI + Python.
- ORM: SQLAlchemy 2.x.
- Database: PostgreSQL.
- Alembic for migrations; pgvector is the initial vector-search candidate.
- GitHub, Linear and Notion are the first integration priorities.

---

# 22. Glossary

| Term | Definition |
|---|---|
| Asset | A project, service, process, system, account, repository or other resource the organisation depends on |
| Agent capability | A specialised AI or deterministic capability invoked by a workflow |
| Agent run | A persisted execution of an agent capability with inputs, tools, outputs and trace |
| Backup owner | An approved person/team able to cover a responsibility under defined conditions |
| Continuity Case | A managed workflow addressing a change that may interrupt work or lose context |
| Continuity Debt | Backlog of unresolved responsibility, knowledge, coverage and transition weaknesses |
| Context Capsule | A scoped package of permission-checked context for a person, project or responsibility |
| Evidence | Traceable source record or observation supporting a claim or finding |
| Finding | A detected issue, gap, risk or conflict with evidence and status |
| Knowledge Item | A structured or curated representation of operational knowledge |
| Knowledge Steward | A person accountable for maintaining knowledge quality within a scope |
| Ownership Assignment | A time-bounded record assigning a responsibility to a person/team/group |
| Readiness Criterion | An explicit condition the incoming owner must satisfy before transfer completion |
| Responsibility | Ongoing work or accountability that must continue over time |
| Source Record | A normalised reference to an item in a connected system |
| Source ACL | Access-control information from the original source system |
| Workflow Template | Reusable definition of stages, tasks, approvals and acceptance criteria |

---

# 23. External references and competitive benchmark

The following sources were used as a product and technical benchmark. Their capabilities may change; re-check them before implementation, procurement or public competitive claims. Product comparisons describe capabilities found in the cited official documentation, not exhaustive feature comparisons.

## Competitive and product references

- [R1] ServiceNow, *Offboarding knowledge transfer plan generation agentic workflow*: https://www.servicenow.com/docs/r/employee-service-management/now-assist-for-hrsd/offboarding-knowledge-x-agentic-wf.html
- [R2] Guru, *What is Verification?*: https://help.getguru.com/docs/what-is-verifcation
- [R3] Guru, *Creating Knowledge Agents*: https://help.getguru.com/docs/setting-up-and-managing-knowledge-agents
- [R4] Atlassian, *Agents in Rovo*: https://support.atlassian.com/rovo/docs/agents/
- [R5] Atlassian, *Add tools to Rovo agents*: https://support.atlassian.com/rovo/docs/agent-actions/
- [R6] Glean, *About connectors*: https://docs.glean.com/connectors/about
- [R7] OpsLevel, *Service Catalog*: https://www.opslevel.com/product/catalog
- [R8] Backstage, *Software Catalog*: https://backstage.io/docs/features/software-catalog/
- [R9] Temporal, *Python SDK developer guide*: https://docs.temporal.io/develop/python

## Technical references

- [R10] SQLAlchemy, *AsyncIO extension*: https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html
- [R11] pgvector-python, *Python support and SQLAlchemy integration*: https://github.com/pgvector/pgvector-python
- [R12] OWASP, *API Security Top 10*: https://devguide.owasp.org/en/07-training-education/07-api-top-ten/
- SQLAlchemy ORM documentation: https://docs.sqlalchemy.org/en/20/orm/
- Alembic documentation: https://alembic.sqlalchemy.org/en/latest/
- Backstage documentation: https://backstage.io/docs/

---

# 24. Appendices

## Appendix A. Minimum viable demonstration script

The demonstration should prove an end-to-end continuity outcome, not simply show a dashboard or agent chat.

1. Sign in as a Team Manager in a seeded engineering organisation.
2. Open a responsibility called “Payment Service Operations”. Show its primary owner, backup, linked repository, Linear project and runbook.
3. Create an ownership-transfer case from the current owner to an incoming owner.
4. Run discovery and impact analysis. Show affected open PRs, issues, related documentation and known dependencies.
5. Show one confirmed finding and one uncertain/missing item. Make the evidence distinction visible.
6. Run the Knowledge Interviewer to ask a targeted question about an undocumented deployment/recovery step.
7. Generate a proposed handover plan. Review tasks, evidence and deadlines.
8. Demonstrate that external writes are pending approval. Approve a single task creation and show its external ID/link.
9. Switch to the Incoming Owner view. Show the context capsule and tasks.
10. Complete a readiness criterion using a test/sandbox or documented evidence.
11. Open the case Activity tab and show agent/tool actions, approval and outcome history.
12. Open Continuity Debt and show how a related finding was resolved or assigned.

The demo must include at least one negative path: stale integration, missing backup, permission denial, rejected draft or agent uncertainty. This proves that the product handles more than the ideal path.

## Appendix B. Recommended initial test fixtures

Seed an illustrative organisation with:
- One organisation, two departments and three teams.
- Six to ten users with distinct roles.
- One primary owner, one backup and one incoming owner.
- Four responsibilities with mixed criticality.
- Three repositories, two Linear projects and several open issues/PRs.
- A small Notion knowledge set with one current runbook, one stale page and one conflicting procedure.
- One responsibility with no backup.
- One ambiguous identity mapping.
- One connector marked stale or partially failed.
- One source item with restricted permissions.
- One ownership-transfer case and one absence-coverage case.
- Agent runs representing completed, failed, awaiting approval and rejected outcomes.

Use synthetic data. Do not seed the demo with real employee records, private messages or customer secrets.

## Appendix C. Product launch checklist

- [ ] Customer problem and initial ICP validated.
- [ ] Responsibility and Continuity Case model reviewed.
- [ ] Workflow states and closure rules documented.
- [ ] Tenant isolation tests pass.
- [ ] Role and case permission matrix implemented.
- [ ] Connector scope and ACL behaviour verified.
- [ ] Data retention and deletion policy reviewed.
- [ ] Core case workflows pass end-to-end tests.
- [ ] Agent outputs include evidence and uncertainty.
- [ ] External writes are approval-gated and idempotent.
- [ ] Agent run history and kill switch are operational.
- [ ] Integration failures and stale state are visible.
- [ ] Backup and restore tested.
- [ ] Audit events verified.
- [ ] UI empty/error/partial states completed.
- [ ] Accessibility review completed for core flows.
- [ ] Demo uses synthetic data and demonstrates one failure path.
- [ ] Public claims match implemented and tested functionality.

---

**End of document — Relay PRD + SRS v1.0**
