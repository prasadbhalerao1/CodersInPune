# Competitive analysis

What adjacent products do well, where Relay already matches them, and which gaps we chose
to close, adapt, defer or reject. Researched November 2026 from vendors' public product pages
and documentation (sources at the end). Relay does not integrate with or imitate any of these
products; the point is to learn from established patterns and to be honest about scope.

## Where Relay sits

Each category below solves part of organisational continuity well, and each stops at its
own boundary:

| Category | Examples | What they own | Where they stop |
|---|---|---|---|
| Service catalogues and ownership | Backstage, Cortex, OpsLevel, Atlassian Compass | Which team owns which service; scorecards against standards | Ownership is a field on a software entity. Handing that ownership to a specific person, with context, is outside the product. |
| Knowledge management | Guru, Glean, Notion, Slab, Trainual | Verified knowledge, search, training content | Knows *what is written down*, not *who is accountable* for keeping something running or what breaks when they leave. |
| Work management | Linear, Jira, Asana | Issues, projects and their history | History is per issue; there is no view of what one person's absence does across all their work. |
| Incident and on-call | incident.io, Rootly | Who responds now; schedule gaps | Coverage for an on-call rota, not for the long tail of responsibilities that are not paged. |
| HR offboarding | Rippling, HR Cloud, generic checklists | Access, assets, payroll, exit tasks | Knowledge transfer is a checklist item that depends on the leaver's goodwill. |

Relay's thesis is the **connection** between those boundaries: one record of who is
accountable for what (people *and* non-software work), the evidence trail behind it from the
tools teams already use, a deterministic forecast of what an absence breaks, and a reviewed,
audited transfer that ends with the new owner confirmed.

## Capability comparison

Decision key: **Adopt**: take the pattern largely as is. **Adapt**: take the idea, implement it
the Relay way. **Defer**: worthwhile, not worth its cost now. **Reject**: outside Relay's purpose.
**Have**: Relay already does this.

| Capability | Competitor approach | Relay today | Gap | Decision |
|---|---|---|---|---|
| Ownership record | Catalogues attach an owning team to each service (Backstage `owner`, Cortex ownership) | Responsibilities (any work, not only services) with primary owner, co-owners and backups per person or team; ownership history | None for the core record; Relay also covers non-software work | Have |
| Owner verification on a cadence | Guru verifiers re-verify cards on an interval; Cortex notifies owners when an entity needs verification | Per-responsibility review cadence (7–730 days), *review due* flag, stewardship reviews recorded with reviewer and time | None | Have (adapted from the verification pattern) |
| Suggested owners for unowned work | Cortex predicts likely owners from commit/PR activity and on-call data | GitHub ownership suggestions from pull request activity; they change nothing until a manager accepts | Suggestions come from GitHub only | Have; Linear/Notion signals **Defer** |
| Knowledge freshness | Guru marks unverified cards, auto-archives unused ones | Knowledge items with review dates; stale knowledge raises a risk with the rule that raised it; cited sources that changed mark brief statements *changed* | No auto-archive | Have; auto-archive **Reject** (Relay should never silently remove context) |
| Coverage gaps | Rootly Gap Finder assigns uncovered on-call slots to the schedule owner | Risk rules: no owner, no backup, single holder of critical work, stale knowledge; What If? shows gaps for a named absence | None for responsibilities; on-call rotas are out of scope | Have; on-call schedules **Reject** |
| Absence impact forecast | Not offered by the categories above as a first-class workflow | What If? simulator: deterministic, read-only, per responsibility, with dependency propagation, deadlines in the window and readiness score | — | Have (differentiator) |
| Cover candidate workload | On-call tools balance rota load | Candidates from recorded links, each simulated; **overload flag** against the workspace's typical load | Was missing before Round 3 final pass | **Adopt** (shipped) |
| Handover document | Offboarding checklists; knowledge-base templates | Structured Handover Brief per recipient, statements labelled Fact / Rule / AI inference with citations, versions and approval | — | Have |
| Brief completeness | Not found in the products reviewed | **Brief coverage**: which in-scope responsibilities have a cited statement, which are mentioned without a source, which are not covered, critical first | Was missing | **Adapt** (shipped) |
| Change control on the brief | Document tools keep version history | Every edit is a version that needs approval; recipient acknowledges a specific version; **compare any two versions** | — | Have (comparison shipped) |
| AI answers with sources | Glean and Guru answer from indexed content with references | Copilot answers only from the brief's authorised evidence; every citation is validated; otherwise *Not in the evidence* | — | Have |
| Project history | Linear/Jira keep per-issue history | Memory Replay merges GitHub, Linear, Notion and Relay events per responsibility, with filters, replay, linked events, AI chapters labelled *Inferred*, cited Q&A; pages of 200 for large histories | Commits/code not read (by design) | Have; repository-level replay **Defer** |
| Recipient onboarding | Trainual and Guru deliver training paths | After acknowledging, the brief shows the recipient's open tasks, inherited responsibilities with their history, case status and where to ask | — | Have |
| In-product guidance | Product tours and checklists are common | Tours anchored to real elements, resume/replay, per-user guidance switch, checklist, tour eligibility that waits for real sync completion | — | Have |
| Scorecards / maturity levels | Cortex and OpsLevel grade services against rules | Continuity health (owner, backup, current knowledge) and readiness scores with their rules shown | No custom rule builder | **Defer** (custom scorecards add configuration cost judges and small teams don't need yet) |
| Chat-first workflows | incident.io and Rootly run from Slack | Email notifications and in-app inbox | No Slack app | **Defer** (roadmap) |
| HR system triggers | Offboarding tools start from the HR termination event | Cases are started by managers or self-requested by the person | No HRIS connector | **Defer** (roadmap: planned leave feeding the simulator) |
| Org-wide enterprise search | Glean indexes everything a company uses | Search across Relay's own records and imported evidence only | Not an enterprise search engine | **Reject** (different product; would dilute the continuity focus) |

## What we changed because of this research

1. **Cover candidates show workload**, so a manager doesn't pick the person already carrying
   double the team's typical load. Deterministic and explained on the page.
   (`backend/src/relay/continuity/simulation.py`, `tests/test_simulation.py`)
2. **Brief coverage** makes completeness visible before approval: a critical responsibility
   with nothing cited is the gap to close in the handover interview.
   (`backend/src/relay/intelligence/capsules.py::_coverage`, `tests/intelligence/test_handover.py`)
3. **Version comparison** for briefs, because approval and acknowledgement are per version and
   a reviewer needs to see what changed. (`capsules/[capsuleId]/version-diff.tsx`)
4. **Guidance that waits for data**: tours unlock only when the workspace has what they show,
   and a connector counts as ready only after its first sync drains. Common onboarding tools
   unlock on page visits; we tied it to real state instead. (`backend/src/relay/guidance/`)

## Sources

- Cortex ownership: <https://www.cortex.io/products/ownership>, <https://redesign-docs.cortex.io/ingesting-data-into-cortex/entities/ownership>
- Cortex ownership prediction: <https://www.cortex.io/posts/solve-service-ownership-in-minutes>
- OpsLevel ownership framework: <https://www.opslevel.com/resources/the-opslevel-ownership-framework>
- Guru verification: <https://www.getguru.com/features/verification>, <https://help.getguru.com/docs/verifying-and-unverifying-cards>
- Rootly on-call Gap Finder: <https://rootly.com/changelog/2024-05-16-on-call-schedule-owners-gap-finder>
- Rootly catalog: <https://rootly.com/catalog>
- Offboarding practice: <https://asana.com/resources/employee-offboarding>, <https://kayako.com/blog/employee-offboarding-best-practices/>

Vendor material describes vendors' own products; we have not used these products against
Relay's sample data, and nothing here claims Relay is better than them at what they do.
