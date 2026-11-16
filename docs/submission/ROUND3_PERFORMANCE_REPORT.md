# Relay: performance report (Round 3)

All numbers below were measured on 16 Nov 2026 against the production deployment
(API on Render, web on Vercel, database on Neon). Nothing is estimated.

## Server latency (production, warm)

Measured with 15 sequential `curl` requests each from Pune, India:

| Endpoint | p50 | p95 | What it covers |
|---|---:|---:|---|
| `GET /health/live` (API) | 116 ms | 236 ms | Network round trip plus the framework |
| `GET /health/ready` (API) | 118 ms | 129 ms | The above plus a database round trip |
| `GET /docs` (web) | 119 ms | 349 ms | A server-rendered page from the Vercel edge |

All 100 `GET` API routes were also called signed-out. Every one answered with a clean status
(401, 403 or 404), and none returned a 5xx.

The API runs on a free instance that sleeps when idle. The first request after a quiet period
takes up to a minute while it wakes; `.github/workflows/keep-warm.yml` reduces this.

## Pages (Lighthouse, production)

| Page | Performance | Accessibility | Best practices | SEO |
|---|---:|---:|---:|---:|
| `/docs` (product guide) | 98 | 100 | 96 | 92 |
| `/` landing, desktop | 68 (LCP 0.8 s) | not run | not run | not run |
| `/` landing, mobile | 50 | not run | not run | not run |

Accessibility on `/` and `/docs` is also checked by axe-core (WCAG 2.2 AA) in
`e2e/a11y.spec.ts`, with no serious or critical issues. The landing page paints quickly; its score comes from main-thread work hydrating the
interactive 3D hero. The hero is loaded lazily and only after the browser is idle
(`components/landing/quantum-capsule-lazy.tsx`, `figures/stage.tsx`).

## What keeps the product fast

| Technique | Where |
|---|---|
| Server components with parallel data fetching (`Promise.all`) and per-section `Suspense` | `app/w/[workspaceId]/**/page.tsx` |
| Instant skeletons for every workspace route | `loading.tsx` per segment |
| Streaming AI (Server-Sent Events): the first words show while the model is still writing | Copilot, Autopilot, Ask Relay |
| Long work moved to the worker through the transactional outbox | analysis, sync, history, email |
| Cursor pagination on large lists (`X-Next-Cursor`) | `security/test_pagination.py` |
| One query per page for connector health (window function, not one query per connection) | `integrations/connectors.py: health` |
| Incremental GitHub sync from a checkpoint instead of re-reading the full window | `integrations/github/service.py: activity_window` |
| Composite indexes beginning with `tenant_id` on every tenant table | migrations; `test_schema_conventions.py` |
| Model output capped (`max_tokens=4000`) and timed out | `intelligence/llm.py` |
