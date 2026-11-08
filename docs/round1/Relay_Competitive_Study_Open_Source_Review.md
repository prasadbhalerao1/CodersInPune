# Relay — Competitive Study & Open-Source Landscape

**Document type:** Product strategy and technical research  
**Version:** 1.0  
**Research checked:** 8 November 2026  
**Companion document:** `Relay_PRD_SRS_v1.0.md`  
**Status:** Research and recommendations; validate licensing and product claims before implementation or commercial reuse.

---

## 1. Executive Summary

Relay is being designed as an **AI-powered organisational continuity platform**. It connects people, responsibilities, operational knowledge, projects, systems and the applications an organisation already uses. When someone leaves, takes leave, changes roles, transfers a project, or when an operational process changes, Relay helps the organisation understand what is affected, prepare the required work, coordinate the transfer and verify that continuity has been maintained.

The competitive landscape is not empty. There are already strong products for individual parts of this problem:

- **ServiceNow** has an AI-assisted offboarding knowledge-transfer workflow that discovers employee-authored documents, categorises them, creates knowledge-transfer tasks and asks the departing employee to review and consent before sharing.
- **SourceAnt** is a particularly close engineering-context benchmark. Its open-source core captures decisions, constraints, workarounds, conventions and relationships to code/system topology, then exposes scoped knowledge to AI tools over MCP. It also supports context-aware review and issue triage.
- **knowledge-transfer** is a small MIT-licensed project specifically focused on developer handover. It exports onboarding material and privacy-filtered AI memories, supports dry-run import, verifies claims against current code and produces import receipts.
- **Guru** focuses on trusted enterprise knowledge: verification, expert review, freshness, AI-assisted authoring and knowledge-agent workflows.
- **Glean** focuses on enterprise search, permission-aware knowledge discovery and workplace context.
- **Atlassian Rovo** and **GitLab Duo Agent Platform** demonstrate specialised agents, tools, skills and governed execution in work systems.
- **OpsLevel** and **Backstage** focus on software catalogues, ownership and engineering-system visibility.
- **OpenMetadata** provides a useful model for governed metadata, ownership, lineage and business context.

The opportunity for Relay is not to claim that no one has built AI handover, company memory, agentic actions, ownership catalogues or knowledge verification. The opportunity is to connect these capabilities into an **end-to-end continuity operating system**:

1. Maintain a useful model of responsibilities, owners, assets, knowledge and evidence.
2. Detect changes and potential continuity gaps.
3. Open a structured Continuity Case.
4. Gather evidence and identify impact.
5. Prepare and review a transition, coverage or onboarding plan.
6. Coordinate approved actions across connected systems.
7. Verify that the receiving person or team can continue the work.
8. Retain history, exceptions and audit evidence.

### Main recommendation

**Build Relay's continuity domain and workflows ourselves. Reuse mature libraries and patterns selectively. Do not embed several complete products into Relay.**

Initial technology direction remains:

- Next.js + TypeScript frontend.
- FastAPI + Python backend.
- SQLAlchemy 2.x + Alembic.
- PostgreSQL as source of truth; pgvector where semantic retrieval justifies it.
- A Python worker and queue for sync and background execution.
- One orchestrator and specialised agent capabilities, with deterministic workflows and policy gates.

For the first release, prioritise engineering-led organisations because GitHub, Linear and Notion provide concrete, demonstrable sources. Keep the domain model cross-functional so HR, operations, support, product, sales and project workflows can be added without redesigning the core.

---

## 2. What Relay Is Competing To Become

### 2.1 Product definition

Relay is an **Organisational Continuity Platform**. It helps an organisation retain the context needed to keep work moving when people, projects, teams, responsibilities, processes or systems change.

Relay is not intended to replace:

- HRMS / payroll systems;
- project-management tools;
- source-code hosting platforms;
- document repositories or wikis;
- chat and collaboration tools;
- IT service-management platforms;
- developer portals;
- general-purpose enterprise search.

Instead, Relay connects these systems and maintains the cross-system continuity record and workflow that is usually missing between them.

### 2.2 Primary domain concepts

| Concept | Meaning | Why Relay needs it |
|---|---|---|
| Organisation | A tenant/workspace and its governance boundary | Tenant isolation, policies and configuration |
| Person / Identity | A person and the identities they use in connected tools | Identity resolution across systems |
| Team / Department | Organisational grouping | Scope, accountability and dashboard filtering |
| Responsibility | A continuing duty or outcome someone is accountable for | The central unit of continuity |
| Asset | A project, service, repository, process, account, system or other operational object | Things that responsibilities operate on |
| Ownership assignment | A time-bound relationship between an owner and responsibility/asset | Preserve history rather than overwrite the current owner |
| Dependency | A relationship that may affect continuity | Impact analysis |
| Knowledge item | A procedure, decision, runbook, context record or other knowledge object | Reusable and maintainable context |
| Evidence | A source-backed observation or claim | Explainability and trust |
| Continuity Case | A managed change or continuity workflow | The primary operational workflow object |
| Case task | An action needed to complete the case | Assignment and accountability |
| Approval | An explicit human decision | Governance and controlled execution |
| Workflow playbook | Reusable case-type rules and acceptance criteria | Cross-functional extensibility |
| Integration / Sync run | A connected source and its ingestion status | Reliable data freshness |
| Agent run | An AI execution and its tools, evidence and outcomes | Observability and auditability |

### 2.3 Core operating model

`Change or event → Discover context → Assess impact → Identify gaps → Prepare plan → Human review → Coordinate transfer → Verify → Close and retain history`

This workflow must support employee offboarding, temporary absence, return from leave, internal transfer, role change, project handover, service ownership transfer, incident recovery and other continuity playbooks.

### 2.4 Product differentiators to validate

These are hypotheses, not proven market gaps:

1. **Responsibility-centred continuity:** Relay manages the operational responsibility, not merely a person record or document bundle.
2. **Cross-system continuity cases:** One case can connect work from several source systems and coordinate actions across them.
3. **Evidence-backed impact analysis:** Findings link to the sources that support them and clearly distinguish facts from inference.
4. **Verified transfer outcomes:** A transfer is not complete merely because a document was generated or a recipient clicked “accept”.
5. **Continuity debt:** Relay maintains an actionable backlog of unresolved coverage, knowledge, ownership and operational-context gaps.
6. **Recurring continuity value:** Temporary absence coverage, return briefings, knowledge freshness and change monitoring create value even when nobody leaves the organisation.

---

## 3. Competitive Landscape — Commercial and Hybrid Products

These products are competitors, substitutes or benchmarks. They are not all open-source, and their features should not be confused with permission to reuse their code or branding.

### 3.1 ServiceNow — AI-assisted offboarding knowledge transfer

**Category:** Enterprise workflow / HR service delivery  
**Reference:** [ServiceNow offboarding knowledge-transfer workflow](https://www.servicenow.com/docs/r/employee-service-management/now-assist-for-hrsd/offboarding-knowledge-x-agentic-wf.html)

**Documented capabilities**

- Workflow starts when an employee offboarding journey begins.
- A manager-facing agent collects whether knowledge transfer is required and the time range for discovery.
- The system searches multiple document sources for documents authored by the departing employee.
- AI categorises the discovered content.
- Knowledge-transfer records and tasks are created in the employee journey.
- A second agent presents the proposed knowledge resources to the departing employee.
- The departing employee reviews and consents before the material is shared back with the manager.
- The manager can track transfer tasks through the journey.

**Overlap with Relay**

High overlap with employee offboarding, AI-assisted knowledge discovery, document categorisation, approval and structured handover tasks.

**What Relay should learn**

- Separate manager initiation from employee review.
- Make the purpose, time range and scope of discovery explicit.
- Use employee review and consent before sharing appropriate personal/work-context material.
- Make handover tasks part of a tracked workflow rather than a one-off AI response.
- Give managers visibility into incomplete tasks.

**Where Relay may go further**

Relay's hypothesis is to operate across different continuity events and departments, maintain responsibility and ownership history, analyse operational impact across connected systems, manage knowledge quality over time and verify transfer readiness. ServiceNow's documented workflow already covers a meaningful part of the offboarding use case; Relay must not claim that AI-assisted offboarding handover is new.

### 3.2 Guru — trusted knowledge and knowledge operations

**Category:** Enterprise knowledge platform  
**Reference:** [Guru features](https://www.getguru.com/features)

**Documented capabilities include**

- AI-assisted knowledge authoring and updates.
- Collaborative editing and expert review/approval.
- Structured collections and knowledge organisation.
- Automated verification and maintenance.
- Scheduled expert review cycles.
- Stale or superseded knowledge flagging and archival with human safeguards.
- Knowledge-agent workflows and improvement loops.
- Correction propagation to connected surfaces.

**What Relay should learn**

- Knowledge must have owners and verification status.
- Important knowledge should have review cycles and a record of who verified it.
- Source changes and usage signals can trigger review rather than treating documents as permanently true.
- Human review should be routed to the right SME.
- Corrections should update the canonical record and connected references, not create competing copies.

**What not to claim as unique**

Knowledge verification, freshness checks, expert approval, AI authoring and knowledge agents are already established capabilities.

### 3.3 Glean — enterprise search and people/context discovery

**Category:** Enterprise AI search and workplace assistant  
**Reference:** [Glean](https://www.glean.com/)

**Relevant product ideas**

- Search across connected workplace applications.
- Context-aware answers grounded in enterprise content.
- Permission-aware retrieval.
- People and expertise discovery.
- Assistants and agentic workflows using workplace context.

**What Relay should learn**

- Search must respect source permissions.
- Users need to find both information and the people who can explain it.
- Answers should link to original sources.
- Cross-system retrieval should be useful without requiring users to know where information lives.

**Relay distinction**

Glean is primarily an enterprise search and knowledge assistant. Relay should use retrieval as an input to continuity cases and operational actions, not make a general-purpose company chatbot its primary product.

### 3.4 Atlassian Rovo — agents, skills and tools

**Category:** Enterprise search and AI agents  
**References:** [Rovo agents](https://support.atlassian.com/rovo/docs/agents/), [Rovo skills](https://support.atlassian.com/rovo/docs/add-skills-to-rovo-agents/), [Rovo tools](https://support.atlassian.com/rovo/docs/agent-actions/)

**Documented capabilities**

- Configurable specialised agents.
- Reusable skills that describe multi-step approaches.
- Individual tools that perform discrete actions.
- Connected knowledge sources.
- Agents that create, organise or edit work items and pages.
- Tool execution with user confirmation for consequential actions.
- Agent actions respect the permissions of the user on whose behalf the agent acts.

**What Relay should learn**

- Separate **agent instructions/skills** from **tools**.
- A skill is a repeatable plan; a tool is a narrow action with a defined schema.
- Agents should inherit or be constrained by the initiating user's permissions.
- Consequential mutations should require confirmation or an explicit authorised policy.
- Tool limitations and required fields must be surfaced to the user.

**Relay implementation implication**

Do not give an LLM unrestricted database or connector access. Expose typed, scoped tools such as `find_responsibilities`, `get_case_context`, `draft_handover_plan`, `create_task_after_approval` and `request_knowledge_review`.

### 3.5 OpsLevel — engineering ownership and service health

**Category:** Internal developer portal / engineering operations  
**Reference:** [OpsLevel](https://www.opslevel.com/)

**Relevant capabilities to benchmark**

- Software catalogue and ownership metadata.
- Service and dependency visibility.
- Ownership discovery and coverage.
- Scorecards and operational standards.
- Actionable findings and notifications.

**What Relay should learn**

- Ownership information must be operationally useful, searchable and actionable.
- Scorecards should lead to remediation tasks.
- A catalogue should expose owner, status, documentation, dependencies and criticality.
- Ownership coverage is a concrete engineering-management problem.

**Relay distinction**

Relay is not another service catalogue. It needs to connect ownership information to cases, knowledge capture, transfer tasks and readiness verification.

### 3.6 GitLab Duo Agent Platform — governed developer agents

**Category:** Software-development agent platform  
**Reference:** [GitLab Duo Agent Platform documentation](https://docs.gitlab.com/user/duo_agent_platform/)

**What to study**

- Specialised agents and orchestrated agent workflows.
- Tool and data access boundaries.
- Planner and data-analysis capabilities.
- Human oversight and governance.
- Agent observability and execution outcomes.

**Relay lesson**

Agent capability should be integrated into existing work rather than exposed as an unrelated chatbot. The platform must show what an agent planned, what it read, what it changed and what remains pending.

### 3.7 Backstage — open-source developer portal benchmark

Backstage is covered in depth in Section 4 because it is open source. As a competitive product, its central lesson is that engineering teams need discoverable ownership, software catalogues, documentation and extensible integrations.

---

## 4. Open-Source Projects — Detailed Study

This section covers the open-source projects and source-available tools identified during Relay research. The license labels are a point-in-time summary based on repository or official documentation available on 8 November 2026. Always inspect the exact version, subdirectory and dependency licenses before incorporating code.

### 4.1 Directly relevant projects — study first

#### 4.1.1 SourceAnt

**Repository:** [github.com/sourceant/sourceant](https://github.com/sourceant/sourceant)  
**Documentation:** [Knowledge management](https://sourceant.ai/docs/knowledge-management/)  
**License:** Repository identifies an MIT-licensed core; verify the current `LICENSE.md` and any separately licensed hosted/enterprise components before reuse.  
**Relevance:** Very high — one of the closest engineering-context overlaps with Relay.

**What it does**

SourceAnt provides persistent engineering knowledge and context for humans and AI coding agents. It models code structure, system topology, decisions, constraints, workarounds, conventions, discussions, reviews and plans. Its open core exposes knowledge management through MCP. It supports knowledge creation, updates, search, relationships and scoped context retrieval. The product also describes context-aware code review, issue triage and architecture exploration.

Its documentation emphasises:

- Typed knowledge objects instead of undifferentiated prose.
- Durable knowledge stored in a SQL-backed repository.
- Relationships such as `depends_on`, `supports` and `contradicts`.
- Scope boundaries for knowledge.
- Status/governance so teams can distinguish approved knowledge from proposals.
- MCP access to knowledge for compatible tools.
- Context composition from code, topology, contracts and review findings.
- Human review of proposed captured knowledge.

**What Relay should study/take conceptually**

1. **Typed knowledge model:** decisions, constraints, conventions, workarounds, plans, reviews and discussions should be distinct types.
2. **Knowledge status:** proposed, reviewed, approved, rejected, superseded and stale should be explicit states.
3. **Scoped knowledge:** every item should be tied to organisation, team, project, asset or responsibility boundaries.
4. **Relationship semantics:** use typed links rather than generic graph edges.
5. **MCP boundary:** expose safe, permission-filtered Relay context to external AI clients in a later phase.
6. **Context packs:** retrieve a bounded, relevant package rather than dumping every connected document into an LLM prompt.
7. **Evidence on claims:** important statements should link to the source files or records that support them.
8. **Staleness detection:** when code or source assets change, mark dependent knowledge as needing review rather than silently trusting it.

**What Relay should not copy**

- Do not turn Relay into a code-review product.
- Do not make a code graph the core user-facing experience.
- Do not assume repository structure alone explains organisational responsibilities.
- Do not ingest private developer memory or personal context without explicit scope, purpose and consent.

**Related project to inspect: codebase-memory-mcp**

SourceAnt's product site states that the code graph underneath its engineering-context product is built on [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp). This separate MIT-licensed project indexes code, documentation, configuration and infrastructure into a local persistent graph and exposes structural queries to agents through MCP. Its repository describes tree-sitter parsing, symbol/call relationships, cross-service links and change-impact queries.

Relay should inspect it for the engineering-specific slice of context discovery: repository structure, symbol relationships, call paths and code impact. It is not a replacement for Relay's organisation-wide responsibility, people, process and case model. Keep it as an optional GitHub/repository intelligence adapter; do not make the whole Relay domain depend on its graph schema.

**Why this project changes our competitive assessment**

SourceAnt already operates in the space of durable engineering context, knowledge graph relationships and agent context. Relay must differentiate through cross-functional responsibilities, continuity cases, coverage/absence/offboarding workflows, cross-system task coordination and verified operational handover—not merely by saying it has an engineering knowledge graph.

#### 4.1.2 knowledge-transfer

**Repository:** [github.com/ferdinandobons/knowledge-transfer](https://github.com/ferdinandobons/knowledge-transfer)  
**License:** MIT (repository license link).  
**Relevance:** Very high — direct small-scale project handover reference.

**What it does**

A developer handover skill for Claude Code and Codex. It exports a project onboarding guide and privacy-filtered AI memories to a ZIP package. The receiving developer can dry-run an import, inspect candidate memories, verify claims against current code and explicitly confirm what to import.

The package described in its README includes:

- `ONBOARDING.md` — short project map, key flows, architecture and gotchas.
- `memories/` — transferable project facts, conventions, decisions and fragile flows.
- `omissions.json` — privacy-safe information about omitted categories/counts.
- `manifest.json` — export metadata and source commit information.
- `handover.zip` — portable package.
- `import-plan.json`, `import-report.json` and per-item import receipts on the receiving side.

**What Relay should study/take**

1. **Portable context package:** a handover should be exportable and readable without Relay.
2. **Human-readable onboarding summary:** provide a short first-read document, not only a large dump of records.
3. **Privacy filtering and omissions report:** show what was deliberately excluded without revealing private content.
4. **Dry-run before import:** preview what will be added or changed.
5. **Verification against current sources:** do not blindly import stale statements.
6. **Per-item receipts:** record accepted, rewritten, rejected and blocked items.
7. **No silent overwrite:** make conflicts explicit.
8. **Version and source commit metadata:** preserve where the handover package came from.

**What Relay should add**

- A case workflow with assigned owners, tasks, approvals and dates.
- Connected source integrations beyond a local repository.
- Responsibility, project, service and stakeholder coverage.
- Team/manager oversight and incoming-owner readiness.
- Access checks for each destination recipient.
- A live case that can be updated after export.

**Caution**

The project is small and focused on AI coding-agent memories, not a full organisation platform. Treat it as a useful design pattern and implementation reference, not evidence of a large production enterprise system.

#### 4.1.3 Backstage

**Repository:** [github.com/backstage/backstage](https://github.com/backstage/backstage)  
**Docs:** [Software Catalog](https://backstage.io/docs/features/software-catalog/) · [Technical overview](https://backstage.io/docs/overview/technical-overview/)  
**License:** Apache-2.0.  
**Relevance:** High — engineering service catalogue, ownership and plugin architecture.

**What it does**

Backstage is an open framework for developer portals. Its central software catalogue tracks services, websites, libraries, data pipelines, ML models and other software entities, including ownership and metadata. Its plugin architecture brings varied tooling into a consistent UI.

**What Relay should study/take**

1. Entity and relationship modelling for systems, components, resources and teams.
2. Catalogue patterns: searchable, filterable records with owner, lifecycle, domain and metadata.
3. A source-of-truth descriptor approach where appropriate (for example, metadata stored close to code and synced into Relay).
4. Plugin and connector architecture.
5. Entity detail pages with ownership, documentation and relationships.
6. Lifecycle states such as experimental, production and deprecated.
7. Plugin boundaries and extension points.

**Important design warning**

Backstage's documentation explicitly distinguishes an owner field used for display/discovery from an authorization mechanism. Relay must not use a visible ownership field as a substitute for access-control policy. Ownership, approval authority and data permission are separate concepts.

**What Relay should not copy**

Do not deploy an entire Backstage portal as a hidden dependency unless we have a concrete need. Relay is not primarily a developer portal, template scaffolder or service catalogue. Borrow the catalogue patterns and connector ideas.

#### 4.1.4 Graphiti

**Repository:** [github.com/getzep/graphiti](https://github.com/getzep/graphiti)  
**Docs:** [Graphiti overview](https://help.getzep.com/graphiti/graphiti/overview)  
**License:** Apache-2.0 in the current Python package metadata.  
**Relevance:** High — temporal relationships and historical context.

**What it does**

Graphiti is a temporal graph-building library that turns conversations, business data and documents into entities and relationships that evolve over time. It can represent when a fact became valid, when it stopped being valid, when it was learned and when it was invalidated. Its retrieval can combine graph traversal, vector and full-text search.

**What Relay should study/take**

1. **Valid time vs. transaction/observation time:** distinguish when a relationship was true in the organisation from when Relay learned it.
2. Historical ownership and responsibility assignments.
3. Superseding or invalidating facts instead of destructive overwrites.
4. Temporal query semantics, such as “Who owned this service on 1 June?”
5. Combining structured relationship traversal with semantic and text retrieval.
6. Incremental graph update patterns.

**Architecture caution**

Graphiti's Python package lists Neo4j as a core dependency in its current metadata, with some alternative graph backends exposed as extras. That may add operational complexity. Relay should implement basic temporal relationships in PostgreSQL first and evaluate Graphiti only after its temporal reasoning requirements exceed the in-house model.

**What Relay should not copy**

Do not introduce a graph database merely to visualise connections. The graph is an internal reasoning/indexing capability where useful; the user outcome is a correct answer or completed workflow.

#### 4.1.5 Cognee

**Repository:** [github.com/topoteretes/cognee](https://github.com/topoteretes/cognee)  
**Docs:** [Cognee documentation](https://docs.cognee.ai/)  
**License:** Apache-2.0 in the repository.  
**Relevance:** High — AI memory and knowledge extraction.

**What it does**

Cognee is an open-source AI memory platform. It converts documents, code and conversations into entities, relationships and searchable chunks, and supports persistent memory across agent sessions. It describes operations such as `remember`, `recall`, `improve` and `forget`, supports knowledge graph retrieval and exposes integrations for agents and MCP clients.

**What Relay should study/take**

1. An ingestion pipeline separated into add/ingest, deduplicate, enrich/extract, index and retrieve stages.
2. Extraction of entities and relationships from unstructured information.
3. Session memory vs. durable organisational memory.
4. Feedback and improvement loops.
5. Hybrid graph/vector retrieval.
6. Source metadata and provenance carried through chunks and derived facts.
7. Deletion/forgetting semantics and dataset boundaries.
8. Local-model and provider abstraction patterns where useful.

**What Relay should not copy**

Do not let an AI memory framework define Relay's domain model. Cognee can help with extraction/retrieval, but Relay must own the responsibility, case, approval, permission, evidence and workflow models. Do not use Cognee and Graphiti together by default; evaluate them against a single concrete requirement and choose one only if it adds value over PostgreSQL + pgvector.

#### 4.1.6 Onyx

**Repository:** [github.com/onyx-dot-app/onyx](https://github.com/onyx-dot-app/onyx)  
**License:** MIT for Community Edition core; enterprise code in `ee` directories is under a separate Onyx Enterprise License.  
**Relevance:** High — connector, retrieval and AI agent platform.

**What it does**

Onyx describes an open-source AI platform with hybrid/agentic RAG, deep research, custom agents, web search, 50+ indexing connectors, MCP support, RBAC for agents/actions, usage analytics, query history and custom code hooks. Its README distinguishes Community Edition and Enterprise Edition.

**What Relay should study/take**

1. Connector/indexing architecture.
2. Full and incremental sync patterns.
3. Hybrid search and retrieval evaluation.
4. Permission-aware search and access control.
5. Agent/action access controls.
6. Query/run history and analytics.
7. Connector health, error handling and reindex workflows.
8. Data transformation hooks for PII filtering or domain-specific processing.

**What Relay should not copy**

Do not make Onyx a second product embedded behind Relay. Do not assume every feature in the repo is MIT; inspect the EE directories and feature boundaries. Onyx is a useful architecture reference if Relay later needs broad enterprise search connectors, but initial connectors can be purpose-built and narrow.

#### 4.1.7 OpenMetadata

**Repository:** [github.com/open-metadata/OpenMetadata](https://github.com/open-metadata/OpenMetadata)  
**License:** Apache-2.0.  
**Relevance:** Medium-high — metadata, ownership, lineage, governance and provenance.

**What it does**

OpenMetadata is a metadata platform that connects technical metadata, ownership, lineage, data quality, usage, policies, classifications, glossaries, domains, data contracts, semantic search and connectors. It also exposes APIs, SDKs and MCP capabilities.

**What Relay should study/take**

1. Metadata schemas and extensible entity types.
2. Ownership and domain attributes.
3. Lineage and provenance concepts.
4. Classification and policy metadata.
5. Connector and ingestion framework patterns.
6. Search over typed metadata.
7. Change events and versioning.

**What Relay should not copy**

OpenMetadata is designed primarily around data assets and metadata governance. Relay's general responsibility/case model should remain distinct. Use it as a reference for lineage and governance, not as the base application.

---

### 4.2 Workflow orchestration and durable execution

#### 4.2.1 Temporal

**Repository:** [github.com/temporalio/temporal](https://github.com/temporalio/temporal)  
**Docs:** [Temporal documentation](https://docs.temporal.io/) · [Python SDK](https://docs.temporal.io/develop/python)  
**License:** MIT for the Temporal server repository. Review SDK and ancillary component licenses separately.  
**Relevance:** High when Relay has long-running multi-day or multi-week cases.

**What it does**

Temporal is a durable execution platform. Workflows persist state and recover from intermittent failures, retries and service outages rather than relying on one in-memory process to remain alive.

**What Relay should study/take**

- Durable workflow state.
- Activities separated from orchestration logic.
- Retry policies and timeouts.
- Signals and external events.
- Human approval waits.
- Workflow history and replay/debugging.
- Idempotent external side effects.
- Long-running workflow observability.

**When Relay should consider it**

If a transition can wait days for employee input, approvals, a successor assignment or a readiness exercise, and the workflow must survive deploys, crashes and worker restarts, Temporal may become worthwhile.

**Why not necessarily in the MVP**

A well-designed PostgreSQL-backed state machine plus a worker/queue is simpler for the first release. Adopt Temporal when durable orchestration requirements justify running and operating another platform.

#### 4.2.2 Kestra

**Repository:** [github.com/kestra-io/kestra](https://github.com/kestra-io/kestra)  
**License:** Apache-2.0.  
**Relevance:** Medium — declarative/event-driven workflow orchestration.

**What it does**

Kestra is an event-driven orchestration platform for data, infrastructure, business processes and AI workflows. It supports declarative YAML, schedules, events, plugins, retries, timeouts, error handling, execution UI and AI-oriented workflow tasks.

**What Relay should study/take**

- Event and schedule triggers.
- Explicit workflow definitions.
- Retries, timeouts and error handling.
- Execution history and logs.
- Draft/version semantics for workflows.
- Clear preconditions, branching and task outputs.

**Decision**

Do not introduce both Temporal and Kestra into Relay at the start. They solve overlapping orchestration needs with different models. Prefer Relay's own typed workflow state machine initially; evaluate Temporal for durable business cases. Consider Kestra only if the product needs a user-facing general automation builder or cross-system pipeline authoring.

---

### 4.3 Knowledge base, RAG and agent memory projects

#### 4.3.1 Mem0

**Repository:** [github.com/mem0ai/mem0](https://github.com/mem0ai/mem0)  
**License:** Apache-2.0 shown by the repository at research time.  
**Relevance:** Medium — memory management for agents.

**What it does**

Mem0 provides memory infrastructure for AI applications and agents, intended to preserve useful context across sessions and retrieve it later.

**What Relay should study/take**

- Memory extraction and update patterns.
- Deduplication and consolidation.
- User/session/agent memory scopes.
- Memory lifecycle and deletion.
- Provider/vector-store abstraction.
- Evaluation of retrieval quality.

**Relay caution**

Organisational memory must not become a user-personal-memory store by accident. Relay needs organisation-, team-, responsibility-, case- and source-specific access controls, retention rules and provenance. Mem0 is an implementation reference, not a replacement for the Relay knowledge domain.

#### 4.3.2 AnythingLLM

**Repository:** [github.com/Mintplex-Labs/anything-llm](https://github.com/Mintplex-Labs/anything-llm)  
**License:** MIT shown by the repository.  
**Relevance:** Medium — self-hosted RAG, multi-provider support and agent UX.

**What it does**

AnythingLLM is an all-in-one AI application for chatting with documents, using AI agents, selecting LLM providers, embedding models and vector databases, and running local-first/self-hosted workflows.

**What Relay should study/take**

- Provider abstraction.
- Workspace/data-source separation.
- Ingestion and document-processing UX.
- Self-hosted deployment options.
- Model, embedding and vector-store configuration patterns.
- Useful user-facing details for source-aware retrieval.

**What Relay should not copy**

Do not turn Relay into a document-chat workspace. A continuity case must drive the experience. Avoid a large model/provider settings surface for ordinary users.

#### 4.3.3 RAGFlow

**Repository:** [github.com/infiniflow/ragflow](https://github.com/infiniflow/ragflow)  
**License:** Repository currently labels the project Apache-2.0; verify per-directory and third-party component licensing before using code.  
**Relevance:** Medium-high — document intelligence and advanced retrieval.

**What it does**

RAGFlow is an open-source RAG/context platform focused on understanding complex documents, template-based chunking, knowledge extraction and agentic retrieval. Recent project material describes document-level knowledge compilation including wikis, graphs, trees, timelines and mind maps.

**What Relay should study/take**

- Document parsing and layout-aware extraction.
- Table and structured document handling.
- Explainable chunking strategies.
- Dataset/source management.
- Retrieval evaluation and citation grounding.
- Knowledge compilation from source documents.
- Incremental sync and ingestion failure handling.

**What Relay should not copy**

Do not add RAGFlow merely because Relay needs RAG. First test simpler ingestion plus PostgreSQL full-text search and pgvector. If complex PDFs, tables and enterprise document formats become a major pain point, run a focused evaluation against RAGFlow.

#### 4.3.4 Docmost

**Repository:** [github.com/Docmost/docmost](https://github.com/Docmost/docmost)  
**License:** AGPL-3.0 for core; enterprise directories are under a separate enterprise license.  
**Relevance:** Medium — collaborative knowledge UX.

**What it does**

An open-source collaborative wiki and documentation tool with real-time collaboration, spaces, permissions, groups, comments, page history, search, attachments, diagrams and embeds.

**What Relay should study/take**

- Page hierarchy and navigation.
- Collaborative editing and comments.
- Page version history.
- Knowledge spaces and grouping.
- Permission UX.
- Diagrams and embeds.

**What Relay should not copy**

Relay should not recreate a complete wiki. Store knowledge metadata and evidence, link to authoritative source documents, and create a lightweight verified knowledge record only where Relay needs one. AGPL obligations require legal review before incorporating code or creating derivative works.

#### 4.3.5 Outline

**Repository:** [github.com/outline/outline](https://github.com/outline/outline)  
**License:** Current repository license is Business Source License 1.1 (BSL), not an OSI-approved open-source license at the research date. The current file specifies a future change date and Apache 2.0 change license; the exact grant also restricts commercial use as a document service.  
**Relevance:** Medium — polished knowledge-base UX reference, not a default code-reuse candidate.

**What Relay should study**

- Clean document navigation.
- Collections and permissions.
- Search and editor ergonomics.
- Page activity and history.
- Simple collaboration patterns.

**What not to do**

Do not label Outline as OSI open source at this version or assume the BSL permits Relay to embed it as a commercial multi-tenant document service. The current license text explicitly says BSL is not an open-source license and includes a document-service restriction. Use it as a product/UX reference unless counsel confirms a suitable licensing arrangement.

---

### 4.4 HR and organisational workflow systems

#### 4.4.1 Frappe HR

**Repository:** [github.com/frappe/hrms](https://github.com/frappe/hrms)  
**Docs:** [Frappe HR documentation](https://docs.frappe.io/hr/introduction)  
**License:** GPL-3.0 in the repository.  
**Relevance:** Medium — HR lifecycle and leave workflow benchmark.

**What it does**

Frappe HR is an HRMS covering employee management, onboarding, promotions and transfers, exit interviews, leave and attendance, expenses, performance, training, payroll and other HR processes.

**What Relay should study/take**

- Employee lifecycle events and their sequencing.
- Leave approval and coverage triggers.
- Employee/manager relationship patterns.
- Transfer and offboarding checklists.
- Configurable approval paths.
- HR data model conventions and lifecycle status handling.

**What Relay should not copy**

Do not become a payroll, attendance or HRMS product. Connect to HR systems and use a minimum necessary set of lifecycle events. Treat employee data as sensitive and apply explicit purpose/permission controls. GPL-3.0 is copyleft; review the consequences before copying or linking code in a way that may create derivative-work obligations.

---

### 4.5 Automation and integration systems

#### 4.5.1 n8n

**Repository:** [github.com/n8n-io/n8n](https://github.com/n8n-io/n8n)  
**License:** Sustainable Use License / fair-code for most source, with separate Enterprise License areas; not OSI-approved open source.  
**Relevance:** Medium — automation UX and connector patterns.

**What it does**

A visual automation platform with nodes and integrations to connect applications and automate workflows.

**What Relay should study/take**

- Visual workflow builder interaction patterns.
- Trigger/action vocabulary.
- Connector configuration UX.
- Credential management patterns.
- Execution logs, retries and debugging.
- Human-in-the-loop nodes and branching concepts.

**What Relay should not copy**

Do not assume n8n's Sustainable Use License permits Relay to embed or resell it as a commercial multi-tenant automation service. The license is fair-code/source-available and commercially restricted; read the current terms. Relay's first workflow engine should be purpose-built and narrow.

---

## 5. Open-Source License and Reuse Matrix

This is a planning aid, not legal advice.

| Project | Observed license / boundary | Practical classification for Relay | Default recommendation |
|---|---|---|---|
| Backstage | Apache-2.0 | Permissive OSS | Study freely; reuse code only with notices and dependency review |
| SourceAnt | MIT core (verify version and files) | Permissive OSS core | Study deeply; inspect repository license and product boundaries |
| knowledge-transfer | MIT | Permissive OSS | Study deeply; reusable implementation candidate after code/security review |
| Graphiti | Apache-2.0 package metadata | Permissive OSS | Evaluate as optional dependency; inspect required graph backend |
| Cognee | Apache-2.0 | Permissive OSS | Evaluate pipeline/library components, not whole product by default |
| Onyx | MIT CE; EE directories separately licensed | Mixed-license repository | Use CE only after verifying exact files and edition boundaries |
| OpenMetadata | Apache-2.0 | Permissive OSS | Study schemas, lineage and connector patterns |
| Temporal | MIT server repository | Permissive OSS | Optional durable workflow dependency; check SDK/components |
| Kestra | Apache-2.0 | Permissive OSS | Evaluate only if a general workflow engine is justified |
| Mem0 | Apache-2.0 repository listing | Permissive OSS | Optional agent memory component; validate data boundaries |
| AnythingLLM | MIT | Permissive OSS | Study UX/provider abstractions; do not embed whole app by default |
| RAGFlow | Apache-2.0 repository label; verify all components | Permissive OSS subject to component review | Evaluate for advanced document parsing |
| Docmost | AGPL-3.0 core; EE paths separately licensed | Copyleft / mixed | UX reference; do not copy code without legal review |
| Frappe HR | GPL-3.0 | Copyleft | Workflow reference; avoid code reuse unless obligations accepted |
| Outline | BSL 1.1 at current version; future change to Apache 2.0 stated | Source available, not OSI OSS at current version | UX reference only unless separately licensed |
| n8n | Sustainable Use License and EE License | Fair-code / source available, not OSI OSS | Learn workflow UX; do not embed commercially without permission |

### 5.1 License implications in practice

- **MIT:** generally allows commercial use, modification, distribution and sublicensing subject to preserving notices and disclaimers.
- **Apache-2.0:** permissive; includes explicit patent terms and notice requirements. Preserve license and NOTICE obligations where applicable.
- **GPL-3.0:** copyleft. Distribution and derivative-work scenarios can trigger source-sharing obligations. Understand the architecture and linking facts before reuse.
- **AGPL-3.0:** adds network-use provisions that can be relevant to hosted services. Do not assume a SaaS deployment avoids obligations.
- **BSL 1.1:** not an OSI open-source license. Rights depend on the exact Additional Use Grant and change date.
- **Sustainable Use License:** fair-code/source-available with commercial restrictions; not equivalent to MIT or Apache.
- **Mixed-license repositories:** repository-level badges may not apply to every directory, enterprise module or bundled dependency.

Before adopting any library, record:

1. Exact repository URL and commit/tag.
2. License for the exact files used.
3. Transitive dependency licenses.
4. Whether the code is modified.
5. Whether it is linked, copied, embedded, deployed as a service or distributed.
6. Required attribution and notices.
7. Whether a commercial/enterprise directory is excluded.
8. Whether the planned usage requires separate permission.

---

## 6. Feature-by-Feature Competitive Coverage

Legend: **Strong** = a clearly documented capability; **Partial** = adjacent or more limited; **Not core** = not a primary product focus; **Unverified** = do not assume support without further validation.

| Capability | ServiceNow offboarding | Guru | Glean | Rovo | OpsLevel | SourceAnt | Backstage | Relay target |
|---|---|---|---|---|---|---|---|---|
| Employee offboarding knowledge transfer | Strong | Partial | Not core | Possible via workflows | Not core | Not core | Not core | Strong |
| Temporary absence coverage | Unverified | Not core | Not core | Workflow-dependent | Not core | Not core | Not core | Strong |
| Cross-system enterprise search | Connected document discovery | Strong | Strong | Strong in connected ecosystem | Engineering context | Engineering context | Plugin-dependent | Strong, permission-aware |
| Knowledge verification/freshness | Workflow review | Strong | Adjacent | Agent/workflow-dependent | Scorecards/ownership signals | Knowledge governance | Docs/catalog lifecycle | Strong |
| Engineering software catalogue | Not core | Not core | Search/discovery | Atlassian context | Strong | Strong engineering context | Strong | Supported, not sole focus |
| Technical decision/context memory | Partial | Knowledge cards | Search | Connected context | Service context | Strong | ADR/docs integrations | Strong |
| Time-aware ownership history | Workflow records may exist | Not core | Not core | Not core | Ownership metadata | Knowledge/context evolution | Catalogue metadata | Strong |
| Cross-functional responsibility model | HR lifecycle focus | Knowledge focus | People/content focus | Work-item focus | Engineering focus | Engineering focus | Engineering focus | Strong |
| Continuity case lifecycle | Strong for offboarding journey | Knowledge review workflow | Not core | Automation/agents | Scorecard remediation | Review/triage workflows | Not core | Central concept |
| Impact analysis on responsibility change | Partial | Knowledge relation | Search context | Task/agent context | Service/dependency context | Change/repo context | Entity relations | Strong |
| Incoming owner readiness verification | Not established in cited workflow | Knowledge verification | Not core | Workflow-dependent | Not core | Code-context use cases | Not core | Strong |
| Continuity debt backlog | Not core | Not core | Not core | Not core | Adjacent scorecards | Adjacent risk/coverage | Not core | Strong |
| Portable context package | Not established | Knowledge export possible | Not core | Not core | Not core | Context packs | TechDocs | Strong |

**Interpretation:** the table compares documented product emphasis, not every capability a vendor might implement privately or through custom configuration. It is not a definitive procurement comparison.

---

## 7. What Relay Should Build, Borrow, Integrate or Avoid

### 7.1 Build in Relay (core proprietary domain)

These are the elements that define Relay and should not be delegated to an external product abstraction:

1. Universal responsibility model: primary owner, backup, scope, criticality, associated assets, procedures, evidence, history and acceptance criteria.
2. Continuity Case domain and lifecycle.
3. Cross-functional playbooks: offboarding, temporary absence, return briefing, transfer, project handover, onboarding, emergency continuity.
4. Impact analysis that connects evidence to affected responsibilities and work.
5. Continuity Debt backlog and remediation workflow.
6. Handover plan and Context Capsule object model.
7. Knowledge capture interview and question-planning logic.
8. Human review, consent, approval and readiness verification.
9. Case-level and organisation-level policy engine.
10. Cross-source audit trail and action receipts.
11. Role-aware user experience and My Work task aggregation.
12. Metrics that measure actual continuity outcomes.

### 7.2 Borrow as design/engineering patterns

| Source | Borrow this pattern | Relay implementation |
|---|---|---|
| SourceAnt | Typed, governed engineering knowledge and MCP context | Relay KnowledgeItem types, status model, scoped retrieval, later MCP API |
| knowledge-transfer | Export, dry-run, claim verification and receipts | Context Capsule export/import and transfer verification |
| Backstage | Entity catalogue and owner discovery | Responsibility/asset catalogues, metadata and relationship pages |
| Graphiti | Temporal fact semantics | Effective-dated ownership and relationship history in PostgreSQL first |
| Cognee | Ingest/enrich/retrieve pipeline | Worker pipeline and evidence-preserving extraction |
| Onyx | Connectors, RBAC-aware retrieval, query history | Connector contracts, sync health, retrieval audit |
| OpenMetadata | Lineage and governed metadata | Source provenance and dependency records |
| Temporal | Durable state, signals, retries and human wait states | Consider only when case duration/reliability requires it |
| Kestra | Event/schedule and execution observability | Study UI/flow patterns; do not add another engine by default |
| Guru | Review cadence and correction propagation | Knowledge review requests, verified version and stale state |
| Rovo | Skill/tool separation and confirmation | Specialised capabilities + typed tools + approval gates |
| OpsLevel | Scorecards and actionable ownership coverage | Continuity Debt and responsibility coverage checks |
| Frappe HR | Lifecycle event and leave workflow patterns | HR connector and employee lifecycle playbooks, not HRMS features |
| Docmost / Outline | Navigation, comments, history and editor UX | Knowledge UI patterns; link to canonical documents |
| AnythingLLM / RAGFlow | Ingestion and retrieval UX/quality | Evaluate document parsing only if initial pipeline is insufficient |
| Mem0 | Agent memory extraction and lifecycle | Scoped durable agent context with explicit retention/deletion |
| n8n / Kestra | Workflow builder and run debugging UX | Possible future playbook builder; not an MVP dependency |

### 7.3 Integrate rather than rebuild

Relay should integrate with:

- HRIS/HRMS for employee lifecycle events and authoritative employee records.
- GitHub/GitLab for repository, PR, issue, team and CODEOWNERS context.
- Linear/Jira for projects, issues, assignments and workflow status.
- Notion/Confluence/Google Drive for documentation and decisions.
- Slack/Teams for authorised event/context capture where approved and technically feasible.
- Identity providers for login and group/role mapping.
- ITSM platforms for incidents, service requests and change events.

Do not attempt to replace payroll, leave calculation, source control, issue tracking, chat or document collaboration.

### 7.4 Avoid in the first release

- Deploying Backstage, Onyx, Cognee, Graphiti, RAGFlow and Temporal all together.
- Building a generic no-code workflow designer before the core playbooks work.
- Building a universal company chatbot as the main UX.
- Creating an autonomous employee scoring or performance-ranking system.
- Automatically changing owners or revoking access without approval.
- Treating GitHub commit counts as authoritative evidence of responsibility.
- Generating risk scores without transparent factors and source evidence.
- Copying whole wiki/HRMS products into Relay.
- Storing every source document as a duplicate when a canonical link and permission-aware retrieval will suffice.

---

## 8. Recommended Technical Evaluation Plan

The goal is to decide which libraries or systems materially improve Relay, not to accumulate technologies.

### 8.1 Baseline architecture first

Start with:

- PostgreSQL for relational domain records and history.
- SQLAlchemy 2.x for ORM and query access.
- Alembic for migrations.
- pgvector only where semantic retrieval is needed.
- PostgreSQL full-text search for lexical search.
- Python workers and a queue for connector sync and long-running background tasks.
- A typed workflow state machine stored in PostgreSQL.
- A provider-abstracted LLM client and structured output validation.
- Narrow connector adapters with explicit scopes and permissions.

This gives Relay a coherent baseline against which other products can be evaluated.

### 8.2 Focused evaluations

| Evaluation | Compare | Test dataset / scenario | Success criteria |
|---|---|---|---|
| Engineering knowledge extraction | Custom pipeline vs Cognee vs SourceAnt patterns | 3 repositories, ADRs, PRs and issue history | Correct entity/decision extraction, provenance, reviewability, latency and cost |
| Temporal ownership | PostgreSQL model vs Graphiti | Owner changes, backdated corrections and disputed dates | Correct “as of” answers, auditability, query complexity and operating cost |
| Retrieval | PostgreSQL FTS + pgvector vs Onyx/Cognee/RAGFlow | 100–300 docs, tickets, ADRs and runbooks | Recall@k, citation precision, permission isolation, response time and cost |
| Handover package | Relay Context Capsule vs knowledge-transfer ZIP approach | One developer leaves and one joins | Correct evidence, privacy filtering, import preview, conflict handling and readiness |
| Workflow reliability | PostgreSQL state machine vs Temporal | Multi-day approvals, retries, duplicate webhooks and worker crashes | No lost state, no duplicate side effects, understandable history, operational burden |
| Connector reliability | Custom GitHub/Linear/Notion adapters | Token expiry, rate limit, permission revocation, rename and duplicate events | Idempotence, sync freshness, partial-failure visibility and retry correctness |

### 8.3 Architecture decision rules

Adopt a third-party platform only when all of these are true:

1. A named Relay requirement is not adequately met by the current baseline.
2. The project is maintained and its deployment model fits Relay.
3. License terms are compatible with intended commercial use.
4. Security and permission behaviour can be understood and tested.
5. Data can be exported and Relay retains domain ownership.
6. Operational cost and failure modes are acceptable.
7. A prototype beats the simpler implementation on measured criteria.

---

## 9. Product Opportunities That Relay Can Own

The following ideas are Relay product opportunities. They are not claims that every competitor lacks them; they are combinations and workflow outcomes Relay should test with customers.

### 9.1 Continuity Case

A single operational record for a change event. It includes scope, trigger, impacted responsibilities, evidence, participants, tasks, approvals, deadlines, exceptions and verification criteria.

### 9.2 Continuity Debt

A prioritised queue of unresolved continuity weaknesses:

- no backup for a critical responsibility;
- no validated procedure;
- critical knowledge with no accountable steward;
- outdated or conflicting operational instructions;
- unowned asset or process;
- unresolved transfer or incomplete readiness;
- undocumented dependency on one individual.

Each item must show the evidence, impact rationale, owner, due date and suggested remediation.

### 9.3 Temporary Absence Mode

Before an absence:

- capture active responsibilities and open commitments;
- identify deadlines, approvals and escalations;
- suggest backup coverage;
- build a Context Capsule;
- request manager and owner approval.

During absence:

- surface relevant case tasks to backups;
- track unresolved issues;
- keep the original owner unavailable status explicit;
- avoid sending unnecessary notifications.

On return:

- provide a concise activity/change briefing;
- list decisions, incidents, completed work and remaining actions;
- identify responsibilities that should return to the original owner;
- record any permanent ownership changes separately.

### 9.4 Context Capsules

A permission-aware, portable package for a responsibility, project or system. It can include:

- short first-read overview;
- responsibilities and contacts;
- current status and outstanding work;
- key decisions and rationale;
- procedures and runbooks;
- relevant documents and links;
- known risks and unresolved questions;
- evidence references and source timestamps;
- privacy omissions report;
- package version and source snapshot metadata.

A capsule should not silently duplicate restricted information. It must be generated separately for each intended recipient scope where necessary.

### 9.5 Knowledge Capture Interview

A guided interview that asks targeted questions based on missing context. It should avoid asking for facts already verified and should identify:

- undocumented process steps;
- exception paths;
- rationale behind decisions;
- escalation contacts;
- recurring failure modes;
- operational gotchas;
- conditions under which a procedure is unsafe or inapplicable.

The person reviews the generated knowledge before it is approved or shared.

### 9.6 Handover Rehearsal / Readiness Verification

Use role-appropriate acceptance criteria. A new owner may need to locate a runbook, explain a process, complete a safe task or identify an escalation path. For sensitive operational tasks, use a sandbox or human-supervised exercise. Do not let a general-purpose agent execute production operations merely to prove readiness.

### 9.7 Incident-to-Knowledge Loop

Connect incident records, postmortems, root causes, remediation tasks and runbooks. After an incident:

- identify affected responsibilities and assets;
- connect the postmortem to existing knowledge;
- identify missing or contradictory procedures;
- create remediation and review tasks;
- record whether the lessons were incorporated.

### 9.8 Decision Lineage

Track a decision with its rationale, evidence, approver, affected assets, constraints, superseding decisions and current status. A future answer should show whether the decision is still current or has been superseded.

---

## 10. Agentic Layer — Competitive Lessons and Relay Design

### 10.1 Design principles

Relay agents should be specialised capabilities coordinated by a central orchestrator. They do not need to be independent autonomous services or a swarm of agents conversing freely.

Use deterministic code for:

- event validation;
- permission checks;
- state transitions;
- deadline calculations;
- approval requirements;
- duplicate prevention;
- external mutation execution;
- audit persistence.

Use LLM reasoning for:

- ambiguous context synthesis;
- document/decision extraction;
- question generation;
- impact hypotheses;
- handover drafting;
- evidence comparison;
- natural-language explanation.

### 10.2 Proposed Relay agent capabilities

| Capability | Responsibility | Typical inputs | Outputs | Autonomy |
|---|---|---|---|---|
| Continuity Monitor | Detect changes and possible continuity issues | Webhooks, sync changes, schedules, case events | Finding or suggested case | Read/observe; create proposal only |
| Discovery | Find relevant people, assets, responsibilities and knowledge | Case scope, identities, query | Evidence-linked context set | Read-only |
| Impact Analyst | Determine affected work and relationships | Context set, change event | Impact report with confidence and evidence | Draft/recommend |
| Knowledge Steward | Detect gaps, stale/contradictory information and propose updates | Knowledge, source changes, policies | Review request or draft correction | Draft/recommend |
| Handover Planner | Prepare a case-specific transfer plan | Impact report, playbook, due dates | Tasks, acceptance criteria and capsule draft | Draft only until review |
| Knowledge Interviewer | Ask targeted questions and capture context | Gaps, existing knowledge, interviewee scope | Structured answers and draft knowledge | Conduct interview; no silent publication |
| Onboarding Guide | Provide recipient-specific context and tasks | Approved capsule, role and responsibility scope | Learning path and answers | Read-only + task guidance |
| Readiness Verifier | Evaluate whether acceptance criteria have evidence | Checklist, task receipts, exercise evidence | Pass/fail/needs-review recommendations | Recommend; authorised human closes |
| Return Briefing | Summarise events during absence | Case dates, work/activity changes | Personalised return briefing | Read-only/draft |
| Incident Knowledge Assistant | Link incident, postmortem and operational knowledge | Incident records and related assets | Knowledge updates and remediation tasks | Draft; approval before writes |

### 10.3 Agent architecture

```text
Trigger / User Request
        |
        v
Relay Orchestrator
        |
        +--> Validate identity, tenant and permissions (deterministic)
        |
        +--> Load case, playbook, policies and evidence context
        |
        +--> Select capability / workflow step
        |        |
        |        +--> Discovery
        |        +--> Impact Analyst
        |        +--> Knowledge Steward
        |        +--> Handover Planner
        |        +--> Knowledge Interviewer
        |        +--> Readiness Verifier
        |
        +--> Validate structured result and citations
        |
        +--> Policy / approval gate
        |
        +--> Typed tool execution (if authorised)
        |
        +--> Persist result, evidence, action receipt and audit event
        |
        +--> Notify user / continue workflow
```

### 10.4 Tool design

Tools should be narrow, typed and permission-aware. Example names:

**Read tools**

- `list_responsibilities(scope, filters)`
- `get_responsibility(responsibility_id)`
- `get_ownership_history(responsibility_id, as_of)`
- `search_knowledge(query, scope)`
- `get_evidence(source_ref)`
- `list_related_assets(asset_id)`
- `get_case_context(case_id)`
- `get_open_work(owner_or_asset)`

**Draft tools**

- `draft_impact_report(case_id)`
- `draft_handover_plan(case_id)`
- `draft_context_capsule(case_id, recipient_scope)`
- `draft_knowledge_item(source_refs, type)`
- `propose_backup_coverage(responsibility_ids)`
- `draft_return_briefing(absence_case_id)`

**Mutation tools**

- `create_external_task(approved_payload)`
- `request_knowledge_review(knowledge_item_id)`
- `update_approved_responsibility(approved_change)`
- `send_case_notification(approved_message)`

Mutation tools must not accept arbitrary SQL, raw API URLs or unbounded free-form payloads. They must re-check permissions and approval at execution time, not only when the agent drafts the action.

### 10.5 Autonomy levels

| Level | Capability | Policy |
|---|---|---|
| L0 — Observe | Read permitted sources and analyse | May run autonomously within scope |
| L1 — Prepare | Draft reports, plans, documents and proposed tasks | May draft; must label as draft |
| L2 — Execute after approval | Create tickets, send notifications or update approved records | Requires explicit approval by authorised person or pre-approved policy |
| L3 — Restricted | Change access, revoke accounts, share sensitive data, perform irreversible or high-impact operations | Explicit authorised human approval; many actions remain outside Relay's scope |

### 10.6 Agent run observability

Each agent run should retain:

- unique run ID and parent workflow/case ID;
- triggering event and initiating user/system identity;
- agent/capability name and version;
- model/provider and prompt/config version;
- input references and scope;
- tools invoked and tool arguments (redacted where sensitive);
- retrieved evidence references;
- structured output and validation errors;
- confidence/uncertainty where meaningful;
- approval decision and approver;
- external side effects and idempotency keys;
- retry/error/timeout history;
- token, latency and cost telemetry where available.

Do not store unnecessary chain-of-thought or hidden internal reasoning. Store concise rationale, source evidence, structured decisions and action receipts.

### 10.7 Agent safety requirements

- Never bypass tenant or source permissions.
- Treat connected source content as untrusted input, not agent instructions.
- Protect against prompt injection in documents, issues, PRs, tickets and web pages.
- Re-check permissions immediately before a tool mutation.
- Use idempotency keys for external writes.
- Require approval for consequential changes.
- Show what will change before execution.
- Provide cancellation and retry controls where safe.
- Preserve an audit record for both successful and rejected actions.
- Distinguish verified fact, source observation, inference and recommendation.
- Do not infer employee performance, intent, health, protected attributes or suitability from operational telemetry.
- Do not create employee rankings or covert surveillance features.

---

## 11. UX Lessons From the Competitive Set

The product should be action-oriented, not graph-oriented or chatbot-first.

### 11.1 Navigation benchmark

Recommended primary navigation:

- Overview
- My Work
- Continuity Cases
- Responsibilities
- People & Teams
- Knowledge
- Insights

Administration:

- Integrations
- Agents & Automations
- Roles & Permissions
- Audit Log
- Settings

### 11.2 UI patterns to study

| Reference | UX lesson |
|---|---|
| Linear | Dense but clean work lists, keyboard efficiency, filters and predictable detail views |
| Guru | Knowledge verification status, review ownership and knowledge maintenance workflows |
| Glean | Search as a cross-application entry point and source-aware answers |
| OpsLevel | Catalogue, ownership and scorecard-to-remediation flow |
| Backstage | Extensible entity pages and plugin-driven information panels |
| Docmost | Page history, comments, spaces and collaborative documentation |
| Outline | Minimal navigation and document discovery; license restricts code reuse at current version |
| Rovo | Agent discovery, reusable skills, action confirmation and permission-aware tool UX |
| Temporal | Workflow execution history and visibility into long-running processes |
| Kestra | Execution logs, retries, branching and workflow debugging |

### 11.3 Key UX principles

1. **My Work is the employee entry point.** Employees should not need to understand the entire platform to complete a task.
2. **Cases are the manager entry point.** Managers should see status, blockers, due dates and next actions.
3. **Responsibilities are the operational catalogue.** Users find and maintain who is accountable for what.
4. **Knowledge is linked to sources.** Relay should not become a disconnected document dump.
5. **Agents are contextual.** They should work inside cases, responsibilities and knowledge screens.
6. **Graph is optional.** Keep visual relationship exploration secondary to actionable lists and record pages.
7. **Evidence is inspectable.** Every important AI finding should expose its supporting source(s).
8. **Status is honest.** Partial sync, stale source, unverified AI inference and failed action must be visible.
9. **The UI is role-aware.** Do not overwhelm regular members with admin and workflow-engine controls.
10. **Progressive disclosure.** Basic workflows stay simple; advanced provenance, policy and execution information remains one click away.

---

## 12. Research and Build Priority

### Priority 0 — Read and prototype immediately

| Rank | Project | Why | Concrete output from study |
|---:|---|---|---|
| 1 | SourceAnt | Closest engineering-context overlap | Typed engineering knowledge schema and context pack prototype |
| 2 | knowledge-transfer | Direct handover implementation | Context Capsule format, privacy omission report and dry-run import design |
| 3 | Backstage | Ownership/catalogue fundamentals | Asset and responsibility catalogue schema |
| 4 | ServiceNow offboarding workflow | Direct offboarding competitor | Manager initiation + employee review journey |
| 5 | Guru | Knowledge verification and freshness | Knowledge lifecycle and review queue design |
| 6 | Rovo | Agent skills/tools and permission design | Tool schema and approval architecture |

### Priority 1 — Evaluate after first end-to-end workflow

| Rank | Project | Why | Decision to make |
|---:|---|---|---|
| 7 | Graphiti | Temporal relationships | Is PostgreSQL temporal history sufficient? |
| 8 | Cognee | Knowledge extraction/retrieval | Does it outperform a simple typed pipeline? |
| 9 | Onyx | Connectors and retrieval | Do we need a mature indexing/search platform? |
| 10 | Temporal | Durable workflows | Is our PostgreSQL state machine no longer sufficient? |
| 11 | OpenMetadata | Metadata/provenance patterns | Which lineage/governance concepts belong in Relay? |
| 12 | RAGFlow | Complex document parsing | Do real customer docs require advanced parsing? |

### Priority 2 — Reference only until a matching requirement appears

- Frappe HR — HR lifecycle and leave workflow references.
- Docmost — collaboration, wiki and page-history UX.
- Outline — knowledge UX reference only; current BSL restriction.
- Mem0 — agent memory patterns.
- AnythingLLM — provider and RAG product UX.
- n8n — automation UX and connector behaviour; licensing restricts embedding assumptions.
- Kestra — general workflow engine and workflow builder.

---

## 13. Competitive Validation Questions for Customer Discovery

Do not validate Relay only by asking whether people like the idea. Ask about real, recent incidents and workflows.

### 13.1 Problem validation

1. When someone leaves or takes leave, what exact steps happen today?
2. Who is responsible for preparing and approving a handover?
3. How do you know which responsibilities the person actually owns?
4. Where is the knowledge stored, and which sources are authoritative?
5. What has been missed in the last three handovers?
6. How long does a new owner take to become independently productive?
7. What happens when the original owner is suddenly unavailable?
8. How are backups assigned and verified?
9. Which tasks still depend on one person?
10. What is the operational or financial consequence of a failed transfer?

### 13.2 Existing-tool validation

1. Do you already use ServiceNow, Workday, BambooHR, Guru, Glean, Confluence, Backstage, OpsLevel or an equivalent?
2. Which tool creates the employee lifecycle event?
3. Which system is authoritative for people and teams?
4. Where are project and operational responsibilities stored?
5. What data can Relay access through supported APIs?
6. Are connector permissions delegated per user, by administrator or through service accounts?
7. Would you permit AI to draft knowledge? Which actions require approval?
8. What content must never be indexed or transferred?

### 13.3 Differentiation validation

1. Would a Continuity Case reduce actual work, or just add another admin system?
2. Would managers use Continuity Debt as a remediation queue?
3. Is Temporary Absence Mode frequent and painful enough to justify ongoing usage?
4. Is readiness verification acceptable, and what evidence is fair for each role?
5. Would teams pay for cross-system continuity coordination if existing tools already manage documents and tasks?

---

## 14. Risks and Open Questions

| Risk / question | Why it matters | Proposed response |
|---|---|---|
| Product scope too broad | HR, engineering and operations have different data and compliance needs | Universal domain model; narrow initial playbooks |
| Direct overlap with ServiceNow | Offboarding handover is not novel | Differentiate on cross-event, cross-functional continuity and readiness |
| Direct overlap with SourceAnt | Engineering context/knowledge graph is already addressed | Focus on responsibility lifecycle and continuity workflows; benchmark SourceAnt closely |
| Connector permissions are complex | A source permission change can make indexed content unsafe | Permission-aware retrieval and regular permission reconciliation |
| AI overstates inferred relationships | Bad impact analysis can create false work or risk | Evidence, confidence, review and explicit unknown states |
| Knowledge becomes stale | Old information may be worse than no information | Version, review state, effective date, source freshness and stale flag |
| Duplicate source of truth | Relay could contradict HRIS/Jira/Notion | Clearly designate authoritative fields and preserve source links |
| Agent writes wrong data | External systems may be mutated | Draft-first, approval gates, idempotency and action receipts |
| Cost of indexing all sources | LLM and embedding spend can grow quickly | Incremental sync, selective extraction, caching and budgets |
| Employee privacy/trust | Workplace content can include sensitive information | Purpose limitation, consent, minimisation and auditability |
| Over-engineered agent architecture | Too many agents add latency and failure modes | One orchestrator, specialised capabilities, deterministic workflow engine |
| License risk | Some attractive projects are copyleft or source-available | Maintain an SBOM and perform legal review before code reuse |
| Enterprise deployment burden | Self-hosting and connector operations can be expensive | Start with hosted MVP; design data export and later deployment options |

### Open decisions before large-scale implementation

- What is the canonical identity provider and identity resolution strategy?
- Which HRIS integration, if any, is needed for phase 1?
- Is Relay initially single-tenant or multi-tenant hosted?
- What are the minimum supported connector permissions?
- Which record types must be retained if source content is deleted?
- How will the organisation configure criticality and risk policies?
- What constitutes “ready” for each case type?
- Which LLM providers and data residency constraints are required?
- Is external MCP exposure part of the first release or a later extension?
- What retention and deletion policies apply to agent traces, source content and generated context packs?

---

## 15. Recommended Build-vs-Borrow Decisions

| Layer | Decision | Rationale |
|---|---|---|
| Responsibility and ownership domain | Build | Core Relay abstraction and differentiation |
| Continuity Case engine | Build | Core product workflow |
| Cross-functional playbooks | Build | Product-specific operational logic |
| Connector framework | Build a narrow standard; reuse SDKs | Need common sync contracts without adopting a full platform too early |
| GitHub/Linear/Notion connectors | Build or use official SDKs | Initial workflow needs predictable source semantics and permissions |
| Knowledge extraction | Build a small typed pipeline; evaluate Cognee | Avoid framework lock-in until extraction tests justify it |
| Temporal graph | PostgreSQL first; evaluate Graphiti | Simpler operational baseline |
| Full enterprise search | Build targeted search first; evaluate Onyx later | Avoid a second platform unless breadth is required |
| Document parsing | Use existing parsers; evaluate RAGFlow for complex docs | Keep ingestion cost and infrastructure modest |
| Agent orchestration | One orchestrator and typed capabilities | Easier reliability, debugging and permissions |
| Workflow durability | PostgreSQL state machine first; evaluate Temporal | Avoid premature infrastructure |
| Knowledge lifecycle | Build Relay states; study Guru/SourceAnt | Knowledge approval and freshness are central but need Relay-specific semantics |
| Developer catalogue | Build minimal Relay catalogue; study Backstage/OpsLevel | Avoid recreating a full portal |
| HR lifecycle | Integrate HRIS; study Frappe HR/ServiceNow | Do not become an HRMS |
| Wiki/editor | Link canonical sources; do not build a full wiki | Avoid duplicating Notion/Confluence/Docmost |
| Automation builder | Defer; study n8n/Kestra | Core playbooks should work before generic workflow authoring |

---

## 16. Reference Links

### Commercial and hybrid products

- [ServiceNow — Offboarding knowledge transfer agentic workflow](https://www.servicenow.com/docs/r/employee-service-management/now-assist-for-hrsd/offboarding-knowledge-x-agentic-wf.html)
- [Guru — Product features](https://www.getguru.com/features)
- [Glean](https://www.glean.com/)
- [Atlassian Rovo — Agents](https://support.atlassian.com/rovo/docs/agents/)
- [Atlassian Rovo — Skills](https://support.atlassian.com/rovo/docs/add-skills-to-rovo-agents/)
- [Atlassian Rovo — Tools/actions](https://support.atlassian.com/rovo/docs/agent-actions/)
- [OpsLevel](https://www.opslevel.com/)
- [GitLab Duo Agent Platform](https://docs.gitlab.com/user/duo_agent_platform/)

### Open-source repositories and documentation

- [SourceAnt](https://github.com/sourceant/sourceant)
- [SourceAnt knowledge management docs](https://sourceant.ai/docs/knowledge-management/)
- [codebase-memory-mcp](https://github.com/DeusData/codebase-memory-mcp)
- [knowledge-transfer](https://github.com/ferdinandobons/knowledge-transfer)
- [Backstage](https://github.com/backstage/backstage)
- [Backstage software catalogue docs](https://backstage.io/docs/features/software-catalog/)
- [Graphiti](https://github.com/getzep/graphiti)
- [Graphiti docs](https://help.getzep.com/graphiti/graphiti/overview)
- [Cognee](https://github.com/topoteretes/cognee)
- [Cognee docs](https://docs.cognee.ai/)
- [Onyx](https://github.com/onyx-dot-app/onyx)
- [Onyx license](https://github.com/onyx-dot-app/onyx/blob/main/LICENSE)
- [OpenMetadata](https://github.com/open-metadata/OpenMetadata)
- [Temporal](https://github.com/temporalio/temporal)
- [Temporal Python SDK docs](https://docs.temporal.io/develop/python)
- [Kestra](https://github.com/kestra-io/kestra)
- [Mem0](https://github.com/mem0ai/mem0)
- [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm)
- [RAGFlow](https://github.com/infiniflow/ragflow)
- [Docmost](https://github.com/Docmost/docmost)
- [Frappe HR](https://github.com/frappe/hrms)
- [Frappe HR docs](https://docs.frappe.io/hr/introduction)
- [Outline](https://github.com/outline/outline)
- [Outline current license](https://github.com/outline/outline/blob/main/LICENSE)
- [n8n](https://github.com/n8n-io/n8n)
- [n8n community license explanation](https://github.com/n8n-io/n8n-docs/blob/main/docs/n8n-community-license/README.md)

---

## 17. Final Strategic Conclusion

Relay is entering a space where many underlying capabilities already exist. ServiceNow has a direct AI-assisted offboarding handover workflow. SourceAnt has a focused engineering knowledge/context product. `knowledge-transfer` demonstrates portable, privacy-filtered and verified developer handover. Guru and Glean demonstrate trusted knowledge and search. Rovo and GitLab demonstrate agentic work execution. OpsLevel and Backstage demonstrate engineering ownership catalogues. OpenMetadata demonstrates governed metadata and lineage.

That does not mean Relay has no opportunity. It means Relay must be specific about the outcome it owns.

**Relay should own the continuity lifecycle around responsibilities.**

It should know what responsibilities exist, where their context comes from, what depends on them, what changes when an owner or process changes, what actions are required, who must approve them, and what evidence shows that the organisation can continue.

The graph is not the product. The chatbot is not the product. The agent swarm is not the product. They are implementation techniques.

The product is the reliable coordination of organisational continuity — with evidence, permissions, human accountability and measurable outcomes.

**Recommended immediate action:** Study SourceAnt, knowledge-transfer, Backstage, Guru and the ServiceNow offboarding workflow first. Then prototype one complete Relay Continuity Case end-to-end before selecting Cognee, Graphiti, Onyx, Temporal, RAGFlow or any other substantial infrastructure dependency.

---

*Research note: Product features and repository license labels can change. The links above point to official product documentation or repositories where available. Re-check the exact release/commit and all nested licenses before using code in a commercial product.*
