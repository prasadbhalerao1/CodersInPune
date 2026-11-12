# Council: 12 November 2026

## Original question

How can Relay become a genuinely differentiated, indispensable Organisational Continuity Platform? Identify its biggest product, UX, technical and competitive weaknesses. What capabilities would make an engineering manager or enterprise choose Relay over combining Jira, Confluence, Backstage and an AI assistant? Be brutally critical.

## Framed question

How can Relay become a genuinely differentiated, indispensable Organisational Continuity Platform? Identify its biggest product, UX, technical and competitive weaknesses. What capabilities would make an engineering manager or enterprise choose Relay over combining Jira, Confluence, Backstage and an AI assistant? Be brutally critical. Stakes: building the wrong things wastes the remaining effort and leaves Relay as a well-engineered feature incumbents absorb.

## Workspace context used

Relay capabilities and gaps from docs/research/wiki/relay.md; competitor facts from the other wiki pages. Advisors ran on Sonnet and reviewers on Haiku to limit token use.

Peer review summary: Reviewer 1: strongest A, blind spot D; all missed privacy and consent of people scoring, and judging fit. Reviewer 2: strongest A, blind spot D; all missed surveillance and consent, accuracy measurement, rubric fit. Reviewer 3: strongest A, blind spot D; all missed privacy and demo-path reliability. Reviewer 4: strongest C, blind spot D; all missed consent, LLM data handling, a first-run value moment. Reviewer 5: strongest A, blind spot D; all missed surveillance (measure artefacts, not the person), judge-facing reliability, and turning tenant isolation into a verifiable trust story.

---

## Round 1: Advisor responses (raw, de-anonymized)

### The Contrarian

Fatal flaw: the bet that someone maintains ownership data. Manual entry drifts within about 90 days and the debt score then measures Relay hygiene; a confident score on stale data is worse than none. Without a leave or HRIS feed Relay learns of exits late; without Slack nobody opens it on a Tuesday; 'verify' confirms a form, not reality. Copilot and What If are used a few times a year: no daily loop, so renewal risk. Incumbents can add backup-owner and bus-factor scorecards in a quarter; citations are features, not a moat. Willingness to pay is unproven. Sleeping hosting and synthetic data hide real-data failures. Import five real teams and check the output is true before building more.

### The First Principles Thinker

Wrong question: not 'which features make Relay indispensable' but 'which single event does Relay own, and can it prove it changed an outcome there?'. Categories don't buy; departures, leave and reorgs do. Relay doesn't need parity with Jira or Backstage because they don't model who carries the work. The biggest weakness is that Relay predicts risk and writes a brief but never shows the transfer worked: the 'post-transfer follow-up' gap is the product, and it yields an outcome metric no competitor has. Second: stale truth. Manual data decays, so drift detection against source systems and leave signals keeps the model honest. Build the verification loop and one real trigger first.

### The Expansionist

Think bigger: become the system of record for accountability across the company, including non-software work. Make HRIS and leave feeds first so a resignation auto-opens a What If run and a pre-drafted handover, which opens HR and COO budgets. Close the loop with verified outcomes ('handover succeeded, 90-day verified'): a moat and future training data. Distribute through Slack or Teams with in-channel cited Q&A and acknowledgement. Package Continuity Debt and the audit log as operational-resilience evidence. Use the Compass-to-DX migration (vendor claim) as a window: be the continuity layer on top of catalogues, not a competitor.

### The Outsider

A stranger reads 'tracks who owns what and warns when someone leaving causes trouble', but the page never says it. Continuity Debt, Memory Replay, Copilot, brief coverage and separation of duties are internal names, not needs: say 'Alex resigns Friday. What breaks?'. 'Responsibilities' is vague. It is empty on day one, claims 'any work' while its connectors are software-only, has no trigger so users must remember to open it, never checks the handover worked, and doesn't answer 'why not just ask the AI?'. Pick one dated trigger, the notice period, and show a before and after.

### The Executor

Stop adding features; nobody can feel the value with real data. (1) CSV import for responsibilities, owners and backups with preview and accept, then AI-proposed responsibilities from pasted org-chart or runbook text that a human accepts. (2) Read-only Jira connector cloned from Linear. (3) Post-transfer follow-up at 14 and 30 days raising a risk if nothing happens. (4) Outbound weekly Slack digest. (5) Manual leave dates on a person feeding What If and the risk rules. (6) Keep-warm ping and one scripted demo path. Cut new AI features, Teams, Confluence and more tours. Pitch: the only product closing the loop from risk to verified handover to confirmed new owner.

---

## Anonymization map

Session timestamp: `2026-11-12-175825` · permutation index: `fixed: A=First Principles, B=Executor, C=Contrarian, D=Expansionist, E=Outsider`

| Advisor | Letter shown to reviewers |
|---|---|
| Contrarian | C |
| First Principles Thinker | A |
| Expansionist | D |
| Outsider | E |
| Executor | B |

---

## Round 2: Peer reviews (reviewers saw only the anonymized A to E responses)

### Reviewer 1

Strongest A: names the event Relay should own and the missing proof that a handover worked. Blind spot D: assumes enterprise scale for a solo build. All missed: privacy and consent of scoring named people; judging fit.

### Reviewer 2

Strongest A: the 30-day proof is the clearest argument against Jira, Confluence and Backstage. Blind spot D: scope. All missed: surveillance and works-council concerns, no accuracy measurement, no tie to the judging rubric.

### Reviewer 3

Strongest A: concrete, testable outcome metric. Blind spot D: SOC 2, HRIS and a land grab on an unverified vendor date. All missed: privacy, notice and purpose limitation; harden the scripted demo path first.

### Reviewer 4

Strongest C: stale data is existential; test on five real teams. Blind spot D: unrealistic scope. All missed: consent and visibility rules for people scores, LLM data-handling policy, a first-run value moment.

### Reviewer 5

Strongest A: measurable outcome and build order. Blind spot D: enterprise scope. All missed: monitoring a named person is surveillance, so measure handover artefacts instead; warmed demo path; turn tenant isolation into a verifiable trust story.

---

## Chairman synthesis

### Where the council agrees

- All five: Relay never proves a handover worked. A post-transfer check is the differentiator and the outcome measure.
- Four of five: ownership data entered by hand decays; trust in every score depends on keeping it current.
- Relay needs a dated trigger (notice period or leave) rather than relying on someone remembering to open it.
- Do not chase feature parity with Jira, Confluence or Backstage; they don't model who carries the work.

### Where the council clashes

- Scope: D wants HRIS feeds, Slack or Teams, compliance packaging and a catalogue land grab; B and C say cut scope and prove value on real data first. All five reviewers named D the biggest blind spot for a solo build.
- Distribution: D and B rank a Slack surface highly; A calls chat only a delivery channel.

### Blind spots the council caught

- Privacy and consent (raised by 4 of 5 reviewers): ranking named people and watching a new owner's commits reads as surveillance; who may see these scores must be explicit.
- Judging-path reliability: cold starts and synthetic data can fail the demo at the moment that counts.
- Accuracy: nobody proposed measuring whether risk rules and briefs are correct on real data.
- Chairman's fact check against the repository: several 'missing' items already exist. CSV import with preview and commit (relay/imports), self-requested coverage cases for planned absence, email notifications and automation rules are built; key-person exposure is visible only to owners, admins and auditors (members get 403).

### The recommendation

Build the verification loop, on the work rather than the worker. Each executed handover gets a follow-through check per responsibility: is the new holder recorded, has the responsibility been reviewed or shown recorded activity (any source, any person) since, and are the handover tasks closed. Settled, settling in, check in, or new holder not recorded, with the rule shown. No individual activity scoring; people-level exposure stays restricted to managers and auditors. The chairman overrules the Expansionist's scope (HRIS, compliance packaging) for now, and the Executor's Jira connector, which duplicates the Linear path without changing the outcome story.

### The one thing to do first

Ship the per-responsibility follow-through check on executed cases (done in this pass), then run Relay against one real team's repositories and record where its output is wrong.
