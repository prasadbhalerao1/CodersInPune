# 01 - Architecture & System Topology

## 1. System Topology Overview

Relay is architected as an **Enterprise Multi-Tenant Modular Monolith** designed around strict cryptographic and database-level tenancy boundaries. It does not use distributed microservices, external queue brokers (like RabbitMQ or Redis), or external vector/graph databases. Instead, PostgreSQL 18 with Row-Level Security (RLS) is the single source of truth, queue broker, event outbox, full-text search engine, and rate-limiting store.

```mermaid
flowchart TD
    User([End User Browser]) <--> |WorkOS AuthKit Cookie| NextJS["Next.js 16 Web Frontend\n(Vercel / Node.js 22)\nServer Components & Actions"]
    GitHubWebhooks([GitHub Webhooks]) --> |HMAC-SHA256 Signed POST| NextJS
    NextJS --> |Raw Proxy| FastAPI
    NextJS --> |Server-to-Server HTTPS\nBearer JWT Token| FastAPI["FastAPI Backend (Python 3.14)\n(Render / Uvicorn)\nModular Monolith"]

    subgraph Backend_Boundary [FastAPI Internal Pipeline]
        FastAPI --> AuthMiddleware["RequestContextMiddleware\nX-Request-ID & Logging"]
        AuthMiddleware --> TokenVerifier["WorkOSTokenVerifier\n(JWKS RS256/JWT)"]
        TokenVerifier --> WorkspaceAccess["WorkspaceAccess Dependency\nVerifies Active Membership\nEstablishes Tenant Session"]
        WorkspaceAccess --> PolicyCheck["Policy Engine: authorize(access, perm)"]
        PolicyCheck --> DomainService["Domain Services (15 Modules)\ne.g. continuity, catalog, risks"]
        DomainService --> AuditLog["Audit Logger: audit.record()\nAppend-Only"]
        DomainService --> OutboxProducer["Transactional Outbox: outbox.emit()"]
    end

    subgraph Data_Storage [PostgreSQL 18 Neon Managed]
        UnitOfWork["unit_of_work(factory, tenant_id, principal)\nset_config('app.tenant_id', ...)\nset_config('app.principal', ...)"]
        TenantTables[("84+ Tenant Tables\n(ENABLE + FORCE RLS)\nrelay_app role (unprivileged)")]
        OutboxTable[("platform.outbox_event\nUUIDv7, JSONB Payload")]
        ProcrastinateSchema[("procrastinate_*\nVendored Job Queue")]
    end

    DomainService --> UnitOfWork
    AuditLog --> UnitOfWork
    OutboxProducer --> UnitOfWork
    UnitOfWork --> TenantTables
    UnitOfWork --> OutboxTable
    UnitOfWork --> ProcrastinateSchema

    subgraph Background_Workers [Procrastinate Worker]
        ProWorker["relay-worker / Embedded Worker\n(procrastinate.App)"]
        ProWorker --> |Polls outbox_event| OutboxTable
        ProWorker --> OutboxConsumer["outbox.process()\nScoped Tenant Unit of Work"]
        OutboxConsumer --> SyncGitHub["GitHub Ingestion Client"]
        OutboxConsumer --> SyncLinear["Linear Ingestion Client"]
        OutboxConsumer --> SyncNotion["Notion Ingestion Client"]
        OutboxConsumer --> AIWorker["AI Gateway (LLMPort)\nPydanticAI / Gemini / Groq"]
        OutboxConsumer --> EmailWorker["Email Dispatcher (Resend/SMTP)"]
        OutboxConsumer --> AutoCheck["Automation & Policy Service"]
    end

    ProcrastinateSchema <--> |psycopg driver connection| ProWorker
    ExternalAPIs[("Third-Party Services\nGitHub / Linear / Notion / WorkOS")] <--> SyncGitHub & SyncLinear & SyncNotion
    LLMProviders[("LLM APIs\nGemini 3.5 Flash / Groq / Ollama")] <--> AIWorker
    EmailProvider[("Email Services\nResend API / SMTP")] <--> EmailWorker
```

---

## 2. Core Design Patterns

### 2.1 The Two-Role Database Tenancy Pattern
* **`relay_owner`**: The deployment and migration role. Owns all schemas, tables, sequences, and extensions (`uuidv7`, `pgvector`). Runs `alembic upgrade head`.
* **`relay_app`**: The application connection role. Owns no tables, has no `BYPASSRLS`, cannot alter schemas, and cannot truncate or delete audit logs. Connects via connection pooling.
* **Transaction-local RLS configuration**: All database queries are guarded by `unit_of_work()`. At the start of every transaction (`after_begin` event), it issues:
  ```sql
  SELECT pg_catalog.set_config('app.tenant_id', :tenant_id, true),
         pg_catalog.set_config('app.principal', :principal, true),
         pg_catalog.set_config('app.principal_email', :principal_email, true);
  ```
  `is_local => true` guarantees these parameters never leak into pooled connections across transactions.

### 2.2 Transactional Outbox Pattern (Outbox + Queue Co-Commit)
Relay guarantees zero delivery gaps without separate message brokers:
1. When a domain service performs a mutation, it writes an `OutboxEvent` to `platform.outbox_event` inside the active transaction.
2. In the exact same transaction, it accesses the raw psycopg connection and registers a deferred Procrastinate job:
   ```python
   connection = await (await session.connection()).get_raw_connection()
   await jobs.tasks["relay.process_outbox_event"].configure(
       connection=connection.driver_connection,
       schedule_at=schedule_at
   ).defer_async(tenant_id=str(tenant_id), event_id=str(event_id))
   ```
3. If the transaction commits, both the domain mutation and the queue entry are guaranteed to exist. If it rolls back, no spurious jobs ever run.
4. The background consumer (`outbox.process()`) locks the row with `SELECT ... FOR UPDATE`, checks idempotent execution, runs the handler within tenant RLS, and marks it processed.

### 2.3 Layered Separation of Concerns
```
Next.js Server Component / Action
       │ (1) reads encrypted session cookie (WorkOS AuthKit)
       ▼
Frontend Relay API Client (src/lib/relay-api.ts)
       │ (2) attaches Authorization: Bearer <token>
       ▼
FastAPI Routers (src/relay/<module>/api.py)
       │ (3) parses input via Pydantic StrictInput subclasses
       │ (4) validates WorkOS JWT via Identity dependency
       │ (5) resolves workspace membership & binds RLS via CurrentWorkspace
       ▼
Domain Service Layer (src/relay/<module>/service.py)
       │ (6) enforces access control via authorize(access, Permission)
       │ (7) writes audit event via audit.record()
       │ (8) executes business logic & SQL mutations via SQLAlchemy expressions
       │ (9) emits domain events via outbox.emit()
       ▼
PostgreSQL Database
```

---

## 3. High-Level Data Flow Diagrams

### 3.1 Handover Case Lifecycle & Execution Flow

```mermaid
sequenceDiagram
    autonumber
    actor Manager as Continuity Manager
    participant UI as Next.js Web App
    participant API as FastAPI Backend
    participant Auth as Identity & Policy
    participant DB as Postgres (RLS)
    participant Outbox as Outbox & Worker
    participant LLM as AI Engine (LLMPort)
    actor Recipient as Incoming Owner

    Manager->>UI: Create Handover Case (e.g. Departure for Arjun)
    UI->>API: POST /workspaces/{ws}/cases
    API->>Auth: Verify JWT & Active Membership
    API->>Auth: authorize(access, Permission.CASE_MANAGE)
    API->>DB: Insert ContinuityCase, ScopeItems, Auto-Tasks (status: 'draft')
    API->>DB: audit.record('case.created')
    API-->>UI: Return CaseDetail (plan_version: 1)

    Manager->>UI: Request AI Analysis
    UI->>API: POST /workspaces/{ws}/cases/{id}/analysis
    API->>DB: Build Evidence Pool (scoped to caller's visibility)
    API->>Outbox: outbox.emit('ai.step_requested')
    Outbox->>LLM: Run Deterministic Rules + PydanticAI Steps
    LLM-->>Outbox: Claims & Proposals with mandatory citations
    Outbox->>DB: Validate Citations & Store Checkpointed Claims

    Manager->>UI: Approve Handover Plan
    UI->>API: POST /workspaces/{ws}/cases/{id}/approve
    API->>Auth: Check Separation of Duties (Approver != Initiator)
    API->>DB: Insert CaseApproval, move status to 'ready_for_transfer'

    Manager->>UI: Execute Case
    UI->>API: POST /workspaces/{ws}/cases/{id}/execute
    API->>DB: Apply catalog.assign_ownership() (Valid-time temporal assignment)
    API->>DB: Update Case status to 'executing'
    API->>Outbox: outbox.emit('capsule.generated')
    Outbox->>DB: Generate Handover Capsule for Recipient

    Recipient->>UI: Open Handover Brief & Ask Copilot
    UI->>API: POST /workspaces/{ws}/ai/capsules/{capsuleId}/questions
    API->>LLM: Instant grounded RAG over capsule evidence only
    LLM-->>API: Grounded Answer with [E#] citations
    API-->>UI: AnswerView
    Recipient->>UI: Acknowledge Handover
    UI->>API: POST /workspaces/{ws}/ai/capsules/{capsuleId}/ack
    API->>DB: Insert CapsuleAck
```

### 3.2 Ingestion & Evidence Reconciliation Flow

```mermaid
sequenceDiagram
    autonumber
    participant GitHub as GitHub App / Webhooks
    participant Proxy as Next.js Webhook Proxy
    participant API as FastAPI /api/v1/integrations/github
    participant Outbox as PostgreSQL Outbox
    participant Worker as Procrastinate Background Worker
    participant DB as Postgres Database

    GitHub->>Proxy: Webhook POST (push, pull_request, issues)
    Proxy->>API: Forward raw payload + X-Hub-Signature-256
    API->>API: Verify HMAC-SHA256 signature
    API->>DB: Deduplicate webhook event by delivery_id
    API->>Outbox: outbox.emit('github.webhook_received')
    API-->>GitHub: HTTP 202 Accepted

    Worker->>Outbox: Dequeue 'github.webhook_received'
    Worker->>DB: Open tenant unit_of_work as relay_app
    Worker->>DB: Ingest repository metadata, CODEOWNERS, Backstage catalog-info.yaml
    Worker->>DB: Store GitHubWorkItem (PRs/issues metadata only, NO code)
    Worker->>DB: Generate OwnershipSuggestion (if Backstage or CODEOWNERS specified)
    Note over Worker,DB: Suggestions NEVER overwrite primary ownership without human review
```
