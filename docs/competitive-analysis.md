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
| Blast radius | Port: `dependsOn` relations traversed for blast radius; catalogues map component dependencies (Compass: depends on / contains) | Responsibility and asset dependencies (depends on, feeds, escalates to, shares access); the simulator propagates an absence across them | Dependencies are recorded by hand, not discovered | Have; discovery from code **Defer** |
| Knowledge concentration (bus factor) | Bus-factor tools (Truck-Factor, Bus Factor Analyzer, Swimm guidance) estimate it from git authorship | **Key-person exposure**: people who are the only holder of work, ranked by criticality, from accountability records rather than code authorship; one click to simulate their absence | Was a count only, not a named, actionable list | **Adapt** (shipped) |
| Did the handover take hold? | Not found in any product reviewed; offboarding tools stop at the checklist, catalogues at the owner field | **Follow-through** on executed cases: per responsibility, is the new holder recorded, reviewed or active since, tasks closed; *settled / settling in / check in / new holder not recorded* | Was missing; all five council advisors named it the main gap | **Build** (shipped) |
| Capture from departing staff | Sensay and Enterprise Knowledge use AI adaptive interviews | Handover interview: AI proposes questions from evidence gaps; answers are reviewed and can become knowledge | — | Have |
| Catalogue migration | Atlassian is moving Compass's catalogue and scorecards to DX (Atlassian docs); a Cortex blog says access ends 31 Dec 2027 (vendor claim) | Relay reads CODEOWNERS and `catalog-info.yaml` as ownership evidence | No Compass or DX importer | **Defer** (a migration window, not a reason to build a catalogue) |

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

5. **Key-person exposure** on Insights names the people whose absence would leave work with
   nobody, critical first, each with a *What if … is away?* link into the simulator. Visible
   only to owners, admins and auditors. (`relay/insights/service.py::_key_people`,
   `tests/security/test_insights.py`)
6. **Follow-through** on executed cases checks whether each transfer took hold, measuring the
   responsibility (holder recorded, reviewed or recorded activity from any source and person,
   tasks closed), never an individual's output. (`relay/continuity/follow_through.py`,
   `test_follow_through_shows_whether_each_transfer_took_hold`, `e2e/smoke.spec.ts`)
7. **Readable by crawlers and AI agents**: `robots.txt`, `sitemap.xml`, `llms.txt`, canonical and
   Open Graph metadata, and schema.org structured data on the public landing page; workspaces
   stay private and disallowed. (`frontend/src/app/robots.ts`, `sitemap.ts`, `public/llms.txt`)

## Council review

We put the question *"How can Relay become a differentiated, indispensable continuity platform,
and why would an engineering manager choose it over Jira + Confluence + Backstage + an AI
assistant?"* to an [LLM Council](https://github.com/YonasValentin/llm-council): five advisors
with different thinking styles, then five anonymous peer reviewers. Full transcript and
report: [`research/council/2026-11-12-175825/`](research/council/2026-11-12-175825/).

**Where it agreed.** All five advisors: Relay predicts risk and writes a brief but never proved
that a handover worked; closing that loop is the differentiator and the outcome measure. Four
of five: ownership data entered by hand decays, so every score is only as good as its upkeep.
Relay needs a dated trigger (notice period, planned leave) instead of relying on someone
remembering to open it.

**Where it clashed.** One advisor wanted HRIS integrations, Slack and Teams, compliance
packaging and a catalogue "land grab"; all five reviewers called that the biggest blind spot
for a one-person build judged on reliability and usability.

**What the reviewers said everyone missed.** Privacy: ranking named people and watching a
successor's commits reads as surveillance. Accuracy: nobody proposed measuring whether rules
and briefs are right on real data. Demo reliability on a sleeping free host.

**Fact check against the code.** Several "missing" items already exist: CSV import with
preview and commit (`relay/imports`), self-requested coverage cases for planned absence, email
notifications and automation rules. People-level scores were already restricted to managers
and auditors.

## Decisions

| Finding | Decision | What we did |
|---|---|---|
| No proof a handover took hold | **BUILD** | Follow-through per transferred responsibility, measuring the work, not the person |
| Single points of failure are counted, not named | **BUILD** | Key-person exposure with a direct link into the simulator, managers and auditors only |
| Public site invisible to crawlers and AI agents | **FIX** | robots, sitemap, llms.txt, structured data, canonical metadata |
| Deterministic simulation, cited AI, "Not in the evidence", permission filtering before retrieval | **KEEP** | Unchanged |
| Ownership data decays | **KEEP + next** | Review cadences and stale-knowledge risks exist; next: drift view comparing Relay owners with CODEOWNERS |
| No dated trigger | **FIX next** | Planned leave dates on a person feeding the simulator and risks |
| Watching an individual's commits after a transfer | **REJECT** | Follow-through counts activity from any person on the responsibility |
| HRIS suites, compliance packaging, Jira connector, Slack bot | **REJECT for now** | Revisit after a real-team trial |

## Roadmap from this analysis

1. **Now:** run Relay on one real team's repositories and record where risks, suggestions and
   briefs are wrong; publish the error list.
2. **Next:** planned-leave dates as a trigger; an ownership drift view (Relay owner vs
   CODEOWNERS / catalog-info); a weekly outbound digest of check-ins and critical exposure.
3. **Later:** dependency discovery from code and tickets; a catalogue importer for teams leaving
   Compass; HR-system leave feeds once privacy rules for people-level data are documented with
   customers.

## Sources

- Cortex ownership: <https://www.cortex.io/products/ownership>, <https://redesign-docs.cortex.io/ingesting-data-into-cortex/entities/ownership>
- Cortex ownership prediction: <https://www.cortex.io/posts/solve-service-ownership-in-minutes>
- OpsLevel ownership framework: <https://www.opslevel.com/resources/the-opslevel-ownership-framework>
- Guru verification: <https://www.getguru.com/features/verification>, <https://help.getguru.com/docs/verifying-and-unverifying-cards>
- Rootly on-call Gap Finder: <https://rootly.com/changelog/2024-05-16-on-call-schedule-owners-gap-finder>
- Rootly catalog: <https://rootly.com/catalog>
- Offboarding practice: <https://asana.com/resources/employee-offboarding>, <https://kayako.com/blog/employee-offboarding-best-practices/>
- Atlassian Compass: <https://support.atlassian.com/compass/docs/add-component-dependencies/>, <https://support.atlassian.com/compass/docs/what-is-compass/>; end-of-life claim: <https://www.cortex.io/post/atlassian-compass-end-of-life-what-to-do-next>
- Port blast radius: <https://www.port.io/blog/context-layer-for-ai-sdlc>; critique: <https://dev.to/danielwe/inferred-context-is-not-a-dependency-graph-22j2>
- Bus factor: <https://docs.swimm.io/use-case-guides/increasing-bus-factor>
- AI knowledge transfer: <https://www.barchart.com/story/news/36018738/sensay-launches-worlds-first-ai-offboarding-platform-for-knowledge-transfer>, <https://www.apqc.org/resource-library/resource/navigating-great-retirement-current-state-knowledge-capture-transfer> (statistics cited secondhand, not verified at source)
- Glean: <https://techcrunch.com/2024/02/27/glean-wants-to-beat-chatgpt-at-its-own-game-in-the-enterprise>, <https://bloomfire.com/resources/what-is-glean/>
- Research wiki with per-topic notes and verified-vs-claimed markers: [`research/wiki/`](research/wiki/)

Vendor material describes vendors' own products; we have not used these products against
Relay's sample data, and nothing here claims Relay is better than them at what they do.
