/**
 * What every computed number in Relay means, in one place. The ⓘ next to a number and the
 * public guide at /docs both read from here, so the explanation can't drift between them.
 * Each entry mirrors the backend code named in `source`; change both together.
 */
export type Explanation = {
  title: string;
  /** One or two sentences: what it tells you. */
  summary: string;
  /** How it is calculated, exactly. */
  formula?: string;
  /** What goes in, and what doesn't. */
  inputs: string[];
  /** How to read it and what to do next. */
  reading?: string;
  source: string;
};

export const EXPLAIN = {
  readiness: {
    title: "Readiness score",
    summary:
      "How well the work would carry on if this person were unavailable, out of 100. 100 means nothing they hold would be left exposed.",
    formula:
      "For each affected responsibility, weighted by criticality (critical 4, high 3, standard 2, low 1): someone still covers it 60%, it has usable (non-stale) knowledge 25%, and it keeps a second holder 15%. Score = earned ÷ possible × 100, rounded.",
    inputs: [
      "Current primary, co-owner and backup assignments, including team holders",
      "Active knowledge and whether it is past its review window",
      "Only responsibilities this person holds; everything else is unaffected",
    ],
    reading:
      "Below 60 usually means critical work would have nobody. Add a backup in the simulator to see which change moves the score most.",
    source: "backend/src/relay/continuity/simulation.py (_score)",
  },
  simulation: {
    title: "What-if simulation",
    summary:
      "A read-only rehearsal of someone's absence. Nothing is changed: no owner, task or record is written.",
    inputs: [
      "The live catalogue, as you are allowed to see it",
      "Open Relay tasks, GitHub pull requests and issues, Linear issues",
      "The absence length, to flag deadlines that fall inside it",
    ],
    reading:
      "Use it before a planned absence or as a regular drill. Plan a real handover turns the result into an audited case.",
    source: "backend/src/relay/continuity/simulation.py",
  },
  overload: {
    title: "Overload flag",
    summary:
      "Marks a cover candidate who would end up holding far more than is usual in this workspace.",
    formula:
      "Overloaded when responsibilities held after the change ≥ max(2 × typical, typical + 3). Typical = the average number held by people who hold any.",
    inputs: ["Active ownership assignments across the workspace"],
    reading: "Prefer a candidate without the flag, or split the work between two people.",
    source: "backend/src/relay/continuity/simulation.py (candidates)",
  },
  continuity_debt: {
    title: "Continuity Debt",
    summary:
      "A backlog, not a grade: the unresolved continuity problems in scope, added up so you can see whether it is shrinking.",
    formula:
      "Open ownership risks (high 5, medium 2, low 1) + responsibilities with no knowledge (critical 3, high 2, standard 1) + responsibilities whose knowledge is all overdue for review (critical 2, high 1) + overdue tasks (1 each) + cases past their end date (2 each).",
    inputs: [
      "Accepted risks are excluded and listed separately, so the number can't be lowered silently",
      "Every component lists the items behind it",
    ],
    reading: "Open a component to see exactly which items add points, then fix the largest first.",
    source: "backend/src/relay/insights/service.py",
  },
  risk: {
    title: "Continuity risks",
    summary:
      "Rule-based checks on the current catalogue. No AI and no hidden score: each risk names the rule that raised it.",
    formula:
      "No primary owner (high for critical/high work) · No backup (high for critical work) · Critical work with fewer than 2 owners (high) · An owner is archived (high for critical/high work) · One person is the only owner of 2 or more responsibilities (high if any is critical/high).",
    inputs: ["Current assignments, criticality, and whether holders are archived"],
    reading:
      "A risk resolves by itself when the gap is fixed. You can acknowledge it, or accept it until a date with a reason.",
    source: "backend/src/relay/risks/service.py",
  },
  coverage: {
    title: "Ownership coverage",
    summary: "How much of the work has someone accountable for it, and someone to step in.",
    formula:
      "With a primary = responsibilities with a current primary owner ÷ all in scope. With a backup = responsibilities with a current backup ÷ all in scope. Critical coverage counts critical work only.",
    inputs: ["Active (non-archived) responsibilities in the selected scope"],
    source: "backend/src/relay/insights/service.py (CoverageInsight)",
  },
  key_person: {
    title: "Key-person exposure",
    summary:
      "People who are the only holder of work. It describes where coverage is thin, not how anyone performs.",
    formula: "Responsibilities where this person is the only current owner, critical first.",
    inputs: ["Active ownership assignments; team-held work counts the team, not one member"],
    reading: "Add a backup for their critical work, or run the simulator for them.",
    source: "backend/src/relay/insights/service.py",
  },
  freshness: {
    title: "Knowledge freshness",
    summary: "Whether a piece of knowledge has been confirmed recently enough to rely on.",
    formula:
      "Fresh when reviewed (or written by a person) within the workspace's review window, 90 days by default (7 to 730). Imported content stays unreviewed until a person confirms it.",
    inputs: [
      "Last review date, origin (person or import), expiry date, and disputed or draft state",
    ],
    reading: "Stale knowledge still shows, labelled, so you can decide whether to trust it.",
    source: "backend/src/relay/catalog/knowledge.py (_freshness)",
  },
  follow_through: {
    title: "Handover follow-through",
    summary:
      "After a case completes, whether each transferred responsibility actually took hold with its new owner.",
    formula:
      "Settled: the new holder is recorded, has reviewed or worked on it, and its tasks are closed. Settling in: still within 14 days. Check in: 14 days without a review or any recorded activity, or open tasks.",
    inputs: ["Ownership records, reviews, linked activity and case tasks after completion"],
    reading: "It measures the work, not the person. A check in is a prompt for a conversation.",
    source: "backend/src/relay/continuity/follow_through.py",
  },
  evidence_labels: {
    title: "Fact, Rule and AI inference",
    summary:
      "Every statement in a brief says where it comes from, so you know how far to trust it.",
    formula:
      "Fact: read directly from a record. Rule: produced by a deterministic Relay rule. AI inference: proposed by a model from cited evidence, never stored as truth until a person accepts it.",
    inputs: ["Only evidence the reader is allowed to see; restricted items are removed first"],
    source: "backend/src/relay/intelligence/validate.py",
  },
  copilot: {
    title: "Handover Copilot answers",
    summary:
      "Answers come only from the evidence behind the brief that you can see, and each one cites it.",
    formula:
      "An answer is kept only if every citation points at real evidence in that set. Otherwise the reply is “not in the evidence”, with the closest sources to check. With AI off, you get a labelled search instead.",
    inputs: ["The brief's cited evidence and the case's latest analysis, filtered for you"],
    source: "backend/src/relay/intelligence/copilot.py",
  },
  confidence: {
    title: "Confidence",
    summary: "How strongly the cited evidence supports an AI statement: high, medium or low.",
    formula:
      "Set by the model from the evidence it cites, and lowered where it infers a reason the evidence doesn't state. Facts and rules carry no confidence: they are read, not judged.",
    inputs: ["Cited evidence only"],
    reading: "Treat low confidence as a question to ask the previous owner, not an answer.",
    source: "backend/src/relay/intelligence/capabilities.py",
  },
  memory_replay: {
    title: "Memory Replay",
    summary:
      "The history of one responsibility, rebuilt from its sources: owners, pull requests, issues, incidents, decisions and documents.",
    formula:
      "Events are facts with their source date. Categories come from the source's labels, then from words in the title, else “implementation”. Chapters and connections are AI inferences that must cite events; anything citing nothing is dropped.",
    inputs: ["GitHub, Linear, Notion and Relay records linked to the responsibility"],
    source: "backend/src/relay/intelligence/memory.py",
  },
  autopilot: {
    title: "Handover Autopilot",
    summary:
      "Runs a case's whole analysis in one go and shows each tool it uses as it works: reading the case, gathering evidence, checking continuity rules, four AI reviewers, then the exit interview and handover brief.",
    formula:
      "Each reviewer may only search and read the evidence you can see. A point or proposal citing nothing, or citing evidence that doesn't exist, is dropped and counted as “uncited dropped”. Proposals wait for a person; Autopilot never applies anything.",
    inputs: [
      "The case and the responsibilities it covers",
      "Relay, GitHub, Linear and Notion records you are allowed to see",
    ],
    reading:
      "Review the proposals under the run, accept what is right, and reject the rest with a reason so it isn't suggested again.",
    source: "backend/src/relay/intelligence/autopilot.py",
  },
  meetings: {
    title: "Meeting intelligence",
    summary:
      "Turns meeting notes or a transcript into decisions, actions, open questions and risks, each linked to the transcript lines it came from.",
    formula:
      "With AI on, the model lists items citing line refs (L1, L2…); an item citing no line or a line that doesn't exist is dropped. With AI off, rules find decisions (“decided”, “agreed”), actions (“I'll”, “will send”, “by Friday”), risks (“blocker”, “only she knows”) and unanswered questions.",
    inputs: ["The transcript you paste, and nothing else"],
    reading:
      "Accepting a decision records it as decision knowledge on the linked responsibility; accepting an action adds a task to the linked case, assigned to the person named if they are a member.",
    source: "backend/src/relay/intelligence/meetings.py",
  },
  decision_log: {
    title: "Decision log",
    summary:
      "Every decision in the workspace in one timeline, so a successor can see what is settled, when, and where it was decided.",
    formula:
      "Merges decision knowledge (ADRs), decisions from meetings (until accepted ones become knowledge), and decisions reconstructed by case analyses that weren't dismissed. Duplicates with the same wording are shown once.",
    inputs: [
      "Only records you are allowed to see; managers-only decisions stay hidden from members",
    ],
    source: "backend/src/relay/intelligence/meetings.py",
  },
  ask_relay: {
    title: "Ask Relay",
    summary:
      "Ask anything about the workspace in plain language. Relay searches the records you can see, then writes an answer that cites each one.",
    formula:
      "Search ranks responsibilities, knowledge, cases, people and synced items by text relevance; the top matches become the evidence. Each sentence of the answer must cite them; a reply citing nothing is shown as “not in the evidence”.",
    inputs: ["Records you can open yourself; restricted knowledge only for managers"],
    reading: "Click a source chip to open the record behind it.",
    source: "backend/src/relay/intelligence/ask.py",
  },
} satisfies Record<string, Explanation>;

export type ExplainKey = keyof typeof EXPLAIN;
