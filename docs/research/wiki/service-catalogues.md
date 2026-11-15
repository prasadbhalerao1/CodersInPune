---
title: "Service catalogues and developer portals"
type: concept
language: en
created: 2026-11-12
modified: 2026-11-12
tags: [competitor, ownership, catalog]
aliases: [Backstage, Cortex, OpsLevel, Port, Atlassian Compass]
summary: "Ownership of software entities, scorecards and dependency graphs."
confidence: medium
---

# Service catalogues and developer portals

## Definition
Products that register software components with an owning team, grade them with scorecards and model dependencies between them.

## Key Properties
- **Verified (vendor docs):** Cortex suggests owners for unowned entities from repository analysis and notifies owners when verification is needed. Its ownership page says an AI model predicts owners from commits, pull requests, on-call and identity data.
- **Verified (Atlassian docs):** Compass assigns an owner team per component and models "depends on" and "contains" relations (up to 25 outgoing, 100 incoming). Compass's scorecards and catalogue are moving to DX.
- **Vendor claim (Cortex blog, not independently verified):** Compass access ends 31 December 2027.
- **Vendor claim (Port, July 2026):** `dependsOn` relations give blast radius; an agent scores blast radius for releases.
- **Practitioner critique (DEV):** hand-maintained catalogues miss the unknown edges that cause the expensive failures.

## Where they stop
The owner is a team on a software entity. There is no person-level succession, no handover workflow, no non-software responsibilities and no absence forecast.

## Relevance to Relay
Adopted: ownership suggestions from code-host signals; dependency relations. Rejected: custom scorecard builders (configuration cost). Opportunity: Compass customers must migrate (vendor claim), a moment when ownership data is re-examined.

## Related Concepts
- [[relay]] · [[synth-2026-11-12-relay-competitive-position]]

## References
- https://www.cortex.io/products/ownership
- https://redesign-docs.cortex.io/ingesting-data-into-cortex/entities/ownership
- https://support.atlassian.com/compass/docs/add-component-dependencies/
- https://support.atlassian.com/compass/docs/what-is-compass/
- https://www.cortex.io/post/atlassian-compass-end-of-life-what-to-do-next
- https://www.port.io/blog/context-layer-for-ai-sdlc
- https://dev.to/danielwe/inferred-context-is-not-a-dependency-graph-22j2
