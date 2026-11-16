# Relay: scope and next steps

What Relay covers today, what it deliberately leaves to the next release, and why. Each next
step has a trigger: the point at which building it becomes worth it.

## Covered in this release

- The full continuity lifecycle: discover → assess → prepare → transfer → accept → verify →
  monitor, enforced server-side.
- GitHub (App, with webhooks), Linear and Notion (read-only), Slack (outgoing), CSV import.
- AI that proposes and cites; people decide. Deterministic scoring everywhere a number is shown.
- Multi-tenant isolation with forced row-level security, audit, export and deletion.

## Next steps

| Area | Today | Next | Trigger |
|---|---|---|---|
| Linear and Notion freshness | Scheduled and on-demand sync | Webhooks, as GitHub already has | When a workspace needs updates within minutes rather than hours |
| Incremental sync | GitHub and Linear resume from a checkpoint with a daily full reconcile | The same checkpoint for Notion | When Notion fetch windows grow beyond a few seconds |
| Retrieval for Ask Relay | Keyword and full-text retrieval with owners and meetings ([ADR 0003](../3-architecture/decisions/0003-ask-relay-retrieval.md)) | pgvector embeddings in the same database | When workspaces hold tens of thousands of documents |
| Simulator scenarios | One person at a time; candidates compared side by side; up to three scenarios pinned and compared | Saved multi-person scenarios | When teams plan reorganisations, not single absences |
| Copilot scope | One conversation per handover brief | One conversation across a whole case | When cases routinely carry several recipients |
| Identity | WorkOS AuthKit: email codes, passwords, SSO | SCIM provisioning | When customers manage members from their identity provider |
| Landing page | LCP 0.8 s on desktop; interactive 3D hero | Lighter hero on phones | Before a marketing launch |
| Operations | Health checks, structured logs, job correlation ids | Hosted error tracking and uptime paging | When there are paying customers |

The public roadmap with dates is in the [README](../../README.md#roadmap).
