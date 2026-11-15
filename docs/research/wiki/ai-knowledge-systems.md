---
title: "AI knowledge systems and organisational memory"
type: concept
language: en
created: 2026-11-12
modified: 2026-11-12
tags: [competitor, ai, search, bus-factor]
aliases: [Glean, Swimm]
summary: "Permission-aware AI search and assistants with cited answers; bus-factor analysis from code history."
confidence: medium
---

# AI knowledge systems and organisational memory

## Key Properties
- **Vendor claims (Glean, quoted in TechCrunch):** answers respect source-system permissions and cite their sources; a knowledge graph of people and content personalises results.
- **Third-party caveat (Bloomfire):** answers are only as reliable as the underlying content, and permissions across connected systems are easy to misconfigure.
- **Bus-factor tooling (Swimm docs, vendor):** knowledge concentration is measured from git history (Truck-Factor, Bus Factor Analyzer).

## Where they stop
They answer "what do we know?", not "who is accountable, what breaks if they leave, and did the handover happen?". Answers are not tied to a decision workflow.

## Relevance to Relay
Relay's AI is deliberately narrower: permission filtering before retrieval, citation validation, "Not in the evidence". Relay computes key-person exposure from accountability records rather than code authorship.

## Related Concepts
- [[knowledge-management]] · [[relay]]

## References
- https://techcrunch.com/2024/02/27/glean-wants-to-beat-chatgpt-at-its-own-game-in-the-enterprise
- https://bloomfire.com/resources/what-is-glean/
- https://docs.swimm.io/use-case-guides/increasing-bus-factor
