---
title: "Incident, on-call and project management"
type: concept
language: en
created: 2026-11-12
modified: 2026-11-12
tags: [competitor, incident, project-management]
aliases: [incident.io, Rootly, Linear, Jira, Asana]
summary: "Who responds right now, and per-issue history."
confidence: medium
---

# Incident, on-call and project management

## Key Properties
- **Verified (Rootly changelog, 2024):** Gap Finder assigns uncovered 24/7 on-call slots to the schedule owner.
- **Vendor claims:** Rootly incidents inherit catalogue context (owning teams, runbooks, dependencies); incident.io offers a catalogue and Slack-first response.
- **Assumption (not re-verified):** Linear, Jira and Asana keep per-issue history and assignees, with no cross-tool view of one person's accountability.

## Where they stop
They cover a rota or a ticket, not the long tail of responsibilities nobody is paged for.

## Relevance to Relay
Relay reads Linear issues as evidence; on-call scheduling is out of scope. A Slack or Teams surface for handover notifications is a deferred opportunity.

## Related Concepts
- [[relay]]

## References
- https://rootly.com/changelog/2024-05-16-on-call-schedule-owners-gap-finder
- https://rootly.com/catalog
