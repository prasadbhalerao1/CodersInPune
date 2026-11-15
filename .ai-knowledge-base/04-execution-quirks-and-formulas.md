# 04 - Execution Quirks, Algorithms & Mathematical Formulas

## 1. Mathematical Formulas & Scoring Engines

### 1.1 The "What If?" Continuity Simulator Readiness Score
**File**: [`backend/src/relay/continuity/simulation.py`](file:///d:/Code/Relay/backend/src/relay/continuity/simulation.py#L39-L165)

The continuity readiness score evaluates how vulnerable an organization is when a specific person is simulated as absent. The score is strictly deterministic, ranging from $0$ to $100$.

#### 1. Criticality Weights ($W_r$)
Each affected responsibility $r \in R$ is assigned an integer weight based on its declared criticality:
$$W_r = \begin{cases} 
4 & \text{if criticality} = \text{'critical'} \\ 
3 & \text{if criticality} = \text{'high'} \\ 
2 & \text{if criticality} = \text{'standard'} \\ 
1 & \text{if criticality} = \text{'low'} 
\end{cases}$$

#### 2. Responsibility Score Components ($S_r$)
For each affected responsibility $r$, three distinct factors are evaluated:
1. **Coverage ($C_r \in \{0.0, 1.0\}$)**:
   - $1.0$ if someone else currently holds the role or if the simulated backup steps in to cover it.
   - $0.0$ if left completely uncovered.
   - **Weight**: $60\%$ ($0.60$).
2. **Knowledge Freshness ($K_r \in [0.0, 1.0]$)**:
   - Measures the ratio of non-stale knowledge items attached to responsibility $r$:
     $$K_r = \begin{cases} 
     0.0 & \text{if total knowledge items } = 0 \\ 
     \frac{\text{total} - \text{stale}}{\text{total}} & \text{otherwise} 
     \end{cases}$$
   - Overdue items are defined by `catalog.knowledge.review_cutoff`.
   - **Weight**: $25\%$ ($0.25$).
3. **Redundancy / Second Holder ($H_r \in \{0.0, 1.0\}$)**:
   - $1.0$ if $>1$ holder remains after the person's absence is simulated.
   - $0.0$ if only 1 or 0 holders remain (single point of failure).
   - **Weight**: $15\%$ ($0.15$).

#### 3. Total Weighted Readiness Score Formula
$$S_r = 0.60 \cdot C_r + 0.25 \cdot K_r + 0.15 \cdot H_r$$
$$\text{Readiness Score} = \text{round}\left( 100 \cdot \frac{\sum_{r \in R} W_r \cdot S_r}{\sum_{r \in R} W_r} \right)$$
If the person holds zero responsibilities ($|R| = 0$), the readiness score defaults to $100$.

---

### 1.2 Candidate Backup Overload Detection Formula
**File**: [`backend/src/relay/continuity/simulation.py`](file:///d:/Code/Relay/backend/src/relay/continuity/simulation.py#L420-L460)

When suggesting team members who could step in for an absent person:
1. The candidate's current primary responsibility count is evaluated ($N_{curr}$).
2. The number of responsibilities they would inherit is computed ($N_{add}$).
3. The team's average workload ($N_{avg}$) is determined.
4. **Overload Condition**:
   $$\text{Would Be Overloaded} \iff (N_{curr} + N_{add}) \ge 2 \cdot N_{avg} \quad \text{and} \quad (N_{curr} + N_{add}) \ge 4$$
   Candidates meeting this condition are visibly flagged with `would_be_overloaded = true` to prevent burnout cascades.

---

### 1.3 LLM Token Budgeting & Cost Computation
**File**: [`backend/src/relay/intelligence/llm.py`](file:///d:/Code/Relay/backend/src/relay/intelligence/llm.py#L41-L50)

Model costs are calculated dynamically in USD per million tokens:
$$\text{Cost} = \left( \frac{\text{Input Tokens}}{10^6} \cdot P_{in} \right) + \left( \frac{\text{Output Tokens}}{10^6} \cdot P_{out} \right)$$

| Model | $P_{in}$ (USD / 1M) | $P_{out}$ (USD / 1M) |
|---|---|---|
| `gemini-2.5-flash-lite` | \$0.10 | \$0.40 |
| `gemini-2.5-flash` | \$0.30 | \$2.50 |
| `gemini-2.5-pro` | \$1.25 | \$10.00 |
| `llama-3.3-70b-versatile` | \$0.59 | \$0.79 |

* **Workspace Hard Budget**: Monitored via `relay.intelligence.runs.monthly_tokens_left()`. If remaining monthly tokens $< \text{capability token budget}$, execution stops immediately with `monthly_budget_exhausted` before invoking third-party providers.

---

## 2. Custom Algorithms & Heuristics

### 2.1 Timeline Event Categorization & Cross-Referencing
**File**: [`backend/src/relay/catalog/timeline.py`](file:///d:/Code/Relay/backend/src/relay/catalog/timeline.py#L55-L125)

The Project Memory Replay engine classifies raw work items into historical categories via sequential deterministic regex matching:
1. **Incident**: `\b(incident|outage|sev[ -]?[0-4]|postmortem|post-mortem|p0)\b`
2. **Bug Fix**: `\b(bug|fix|fixes|fixed|hotfix|regression|crash|broken)\b`
3. **Documentation**: `\b(docs?|documentation|readme|runbook|guide)\b`
4. **Technical Change**: `\b(refactor|upgrade|bump|migrat\w*|deps?|dependenc\w*|chore|ci|infra|perf|performance|cleanup|deprecat\w*|security)\b`
5. **Default**: `implementation`

* **Automatic Event Linking**:
  - Pull requests containing `fixes #12` or `closes #45` extract issue numbers (`(?:^|[\s(])#(\d+)\b`) and link to the corresponding GitHub Issue event.
  - Linear issue keys matching `\b([A-Z][A-Z0-9]{1,9}-\d+)\b` link pull requests and commits to Linear issues.

### 2.2 Untrusted Content Envelope & Prompt Injection Defense
**File**: [`backend/src/relay/intelligence/evidence.py`](file:///d:/Code/Relay/backend/src/relay/intelligence/evidence.py#L1-L40)

To eliminate indirect prompt injections from third-party issue bodies, PR comments, and Notion documents:
1. All evidence text is sanitized to remove closing XML tags (`</evidence>`).
2. Evidence is packaged inside strict XML delimiters:
   ```xml
   <evidence ref="E3" source="github" title="Issue #42">
   [Sanitized text excerpt strictly limited to 1200 characters]
   </evidence>
   ```
3. System instructions enforce that `<evidence>` tags contain untrusted data. Any instructions inside evidence attempting to override system behavior are ignored and treated as findings.

---

## 3. Platform Quirks, Traps & Technical Debt

### 3.1 Windows Async Event Loop Selector Trait
* **Problem**: Psycopg 3 async requires a Windows `SelectorEventLoop`. The default Windows event loop (`ProactorEventLoop`) raises `NotImplementedError` or causes socket deadlocks when Psycopg creates async connections.
* **Solution**: In [`backend/src/relay/__main__.py`](file:///d:/Code/Relay/backend/src/relay/__main__.py#L14-L18), [`backend/migrations/env.py`](file:///d:/Code/Relay/backend/migrations/env.py#L22-L26), and [`backend/tests/conftest.py`](file:///d:/Code/Relay/backend/tests/conftest.py):
  ```python
  if sys.platform == "win32":
      asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
  ```
* **Gotcha**: Always start the backend with `uv run relay-api`, never bare `uvicorn relay.app:create_app`.

### 3.2 Forced RLS & Nightly Backup Role Quirk
* **Problem**: Every tenant table has `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY`. In PostgreSQL, `FORCE ROW LEVEL SECURITY` causes RLS policies to apply even to the table owner (`relay_owner`). When running `pg_dump` under `relay_owner`, tables with `app.tenant_id = ''` produce 0 rows, making standard nightly database dumps empty!
* **Status**: Neon's Point-in-Time Recovery (PITR) protects production data. However, the standalone nightly pg_dump action in GitHub Actions currently requires a dedicated superuser or a backup role with `BYPASSRLS`.

### 3.3 Free-Tier Web Service Sleep (Cold Starts)
* **Behavior**: On Render free tiers, inactive web services spin down after 15 minutes of inactivity. The initial HTTP request after idle takes up to 60 seconds to boot.
* **Mitigation**: A GitHub Actions workflow ([`workflows/keep-warm.yml`](file:///d:/Code/Relay/workflows/keep-warm.yml)) pings `/health/live` periodically during evaluation windows.

### 3.4 Next.js 16 App Router Proxy Constraints
* **Behavior**: Authentication is handled by `@workos-inc/authkit-nextjs` via [`frontend/src/proxy.ts`](file:///d:/Code/Relay/frontend/src/proxy.ts). In Next.js 16, route handling and server actions must not expose the raw WorkOS session cookies to the client.
* **Rule**: All API communication occurs server-to-server via `src/lib/relay-api.ts`. Client components never call FastAPI directly.
