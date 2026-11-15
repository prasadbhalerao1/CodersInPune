# Product viability

An independent look at whether Relay solves a real problem, for whom, and what it should
stop trying to do. Sources: problem statement (`docs/round1/Problem_Statement.pdf`), SRS
v1.0 §1–6, Decision Register, and the product as built. No market statistics are invented
here; claims are reasoned from the documents and the code.

## 1. The problem, restated

When someone leaves, goes on leave or hands over a project, the knowledge of *what they
were responsible for* and *how it works* lives in their head and in scattered tools.
Handovers happen in a chat message or a hurried document. What fails is not the transfer of
files but the transfer of **accountability**: nobody is sure who owns the deploy pipeline,
the vendor contract or the month-end close until something breaks.

| Who | Experience |
|---|---|
| **Buyer** | Engineering or operations leader (VP Eng, Head of Platform, COO of a 50–500 person company) who has been burned by a departure |
| **Administrator** | Same leader or an engineering manager; no dedicated Relay admin assumed |
| **Daily users** | Engineering managers (cases, risks), service owners (keep their responsibilities current) |
| **Outgoing person** | Answers interview questions, reviews what is shared about their work |
| **Incoming person** | Receives and acknowledges the handover capsule |
| **Resistance** | Individual contributors who see "catalogue what you own" as surveillance or busywork; managers who think a Notion page is enough |

The pain peaks at a **continuity event** (notice period, sudden absence, re-org, project
transfer). Between events the pain is latent risk — which is why adoption is hard.

## 2. Value claims, tested against the code

| Claim | Supporting capability | Evidence | Verdict |
|---|---|---|---|
| Makes accountability transferable | Responsibilities with primary/backup/history; cases that apply ownership changes after approval | AC-01 e2e on a production build with real WorkOS; append-only history enforced in the DB | **Holds** |
| Detects continuity risks | Deterministic rules (no owner, no backup, overdue review, single point of failure) | `test_risk_lifecycle.py`; perf at 1,000 responsibilities | **Holds** — only as good as the catalogue |
| Reconstructs context | Evidence pool from GitHub/Linear/Notion + knowledge; analysis with citations | Live Gemini run: 11–12 cited claims per run, conflict and gaps flagged, uncited claims dropped | **Partly holds** — useful synthesis, but limited by what is connected and catalogued |
| Evidence-backed handovers | Capsules: per-recipient, versioned, approved, acknowledged, omissions listed | `test_handover.py`; demo | **Holds** |
| Verifies transfer happened | Readiness criteria, mandatory checks, acknowledgement per version | `test_case_lifecycle.py` | **Holds procedurally**; "verified" means a person attested, not that the recipient can actually do the work |
| Preserves operational knowledge | Knowledge with stewards, versions, disputes, freshness | `test_knowledge_governance.py` | **Holds** — but capture still depends on people writing things down; interviews help |

Overstated today: "reconstructs context **without manual rebuilding**". With only metadata
connectors (no source code, no Slack, no docs beyond shared Notion pages), most procedural
knowledge still has to be written or interviewed out of people.

## 3. Scenarios

| Scenario | What works | Remaining manual effort | Reasonable? |
|---|---|---|---|
| **A. Departure (2 weeks' notice)** | Departure case discovers every responsibility the person holds; risks show missing backups; analysis + interview questions; tasks/readiness; capsule; ownership applied | Someone must have catalogued responsibilities (or approved GitHub CODEOWNERS suggestions); recipients chosen per responsibility | Yes, if the catalogue exists. Without it, the first departure is where the catalogue gets built |
| **B. Three-week absence** | Coverage case assigns temporary backups, restores ownership on return, return briefing lists changes during the absence | Choosing backups; nothing pages the backup outside Relay | Yes |
| **C. New engineer onboarding** | Onboarding case; capsule of the responsibility's knowledge, open work and contacts ("who to ask") | Access provisioning is out of scope (no IAM integration) | Partly — access prerequisites are a task list, not automated |
| **D. Project handover** | Project-handover case on a project asset; open PRs/issues/Linear issues as evidence; decisions/questions timeline | Decisions not recorded anywhere can only come from interviews | Yes |
| **E. Conflicting knowledge** | Same-topic items flagged as a conflict with both sources and times; never "newest wins" | A person resolves it | Yes (a bug that hid this on the demo was found and fixed in this audit) |
| **F. Integration failure mid-handover** | Connector health shows revoked/error; analysis marked *partial*; withdrawn evidence drops out of capsules | Reconnect | Yes |

## 4. The wedge

Relay is trying to be: an ownership catalogue, a case/workflow tool, a knowledge base, a
risk dashboard, an AI analyst and a connector platform. That is a lot for a first buyer to
adopt.

**Smallest coherent product that keeps the promise** (recommendation):

1. Responsibility catalogue seeded from GitHub CODEOWNERS/catalog-info + CSV import.
2. Two case types: **departure/transfer** and **coverage** (onboarding and project handover
   are variants and can stay, but should not lead the pitch).
3. Risks limited to: no owner, no backup, single point of failure, overdue review.
4. Handover capsule with evidence and acknowledgement.
5. AI as an *assistant inside a case* (analysis + interview questions), off by default.

**Simplify or postpone:** insights trends (keep the debt view), eight automation templates
(keep three: review due, deadline, coverage ending), saved views, knowledge disputes and
validity windows (keep versions + steward verification), external issue creation (keep it
behind its flag). None needs deleting — they are built and tested — but the onboarding
path and navigation should lead with the five items above.

**Target customer:** engineering-led companies of 30–300 people using GitHub (+ Linear or
Notion), where a few people own critical systems and there is no dedicated SRE/IT
service-management tooling. A small team without HR can use it; the cost is the initial
catalogue (hours, not days, with CODEOWNERS import).

**Between events:** recurring value comes from the risk list (missing backups, stale
procedures) and review reminders. This is real but modest; expect weekly, not daily, use.

**Is AI necessary?** No — and the product is right to work without it. AI adds value in two
places: drafting interview questions from gaps, and summarising scattered evidence into a
handover draft. In the live run it produced cited, relevant findings (conflicting runbooks,
open tasks owned by the leaver, missing escalation contacts). It did **not** produce useful
task proposals (0 in two runs; validator rejected the planner's uncited output). Treat AI as
an accelerator, not the differentiator.

## 5. Viability judgement

| Dimension | Assessment |
|---|---|
| Problem clarity | Strong — specific, painful, recognisable |
| Target customer clarity | Moderate — "engineering-led org" is right; the SRS long-term profile (all departments) dilutes it |
| Differentiation | Moderate — the combination (ownership history + evidence-cited handover + approval) is uncommon; individual parts exist in catalogues (Backstage), wikis and ITSM tools |
| Adoption friction | High — needs a catalogue before value; mitigated by CODEOWNERS import and demo data |
| Day-to-day usefulness | Low–moderate (by design) |
| Value during a continuity event | High |
| Value between events | Moderate (risks, reviews) |
| Trustworthiness | High for a pilot: tenant isolation in the DB, approvals, audit, no AI writes |
| Operational feasibility | Good — one Postgres, one API, one worker |
| AI necessity | Optional; useful in a narrow role |
| Cost to operate | Low (≈ $7–60/month hosting; AI usage measured at ~8–9k tokens per analysis) |
| Commercial viability | Unproven — needs paid pilots; buying trigger is event-driven, so sales timing is hard |

**Conclusion: Valuable product but needs narrowing.** The core loop (catalogue → risk →
case → evidence-backed handover → acknowledged ownership change) is real, works end to
end and is trustworthy. The surface area around it is larger than a first customer needs,
and the adoption cost (building the catalogue) must be front-loaded into onboarding. Lead
with departure/coverage for engineering teams; keep the rest available but secondary.
