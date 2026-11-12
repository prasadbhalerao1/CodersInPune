import type { TourId } from "@/lib/types";

// Each step points at an element on the tour's start page by a stable selector (aria
// labels, section titles or data-tour). A step whose element isn't on the page (no data
// yet, narrow screen) is still shown, centred, so a tour never silently breaks.
export type TourStep = { target?: string; title: string; body: string };
export type Tour = { title: string; summary: string; minutes: number; steps: TourStep[] };

const section = (title: string) => `[data-section="${title}"]`;

export const TOURS: Record<TourId, Tour> = {
  basics: {
    title: "Find your way around",
    summary: "The Overview, navigation and search: where continuity gaps show up first.",
    minutes: 1,
    steps: [
      {
        target: '[aria-label="Continuity health"]',
        title: "Continuity health",
        body: "How much of your critical work has an owner, a backup and current knowledge. It is computed from your records, never estimated.",
      },
      {
        target: 'nav[aria-label="Workspace"]',
        title: "Everything is one click away",
        body: "Responsibilities, people, risks and cases. Planning tools (What-if simulator) and history sit alongside them.",
      },
      {
        target: '[data-tour="search"]',
        title: "Search or create anything",
        body: "Press Ctrl K (⌘K on a Mac) to jump to a person or responsibility, or start a case without leaving the page.",
      },
      {
        target: 'a[href$="/help"]',
        title: "Tutorials live here",
        body: "Learn Relay holds every tutorial and the switch for automatic guidance. Replay any tour whenever you like.",
      },
    ],
  },
  ownership: {
    title: "Ownership and backups",
    summary: "Responsibilities, their owners and backups, and how risks are raised.",
    minutes: 1,
    steps: [
      {
        target: '[data-tour="responsibility-table"]',
        title: "Every responsibility has an owner",
        body: "Each row is something that must keep working. Criticality, the primary owner and backups decide how exposed it is.",
      },
      {
        target: '[data-tour="new-responsibility"]',
        title: "Add what matters",
        body: "Create a responsibility, then assign a primary owner and at least one backup. A critical item with one holder becomes a risk automatically.",
      },
      {
        target: 'a[href$="/risks"]',
        title: "Risks follow from the records",
        body: "No owner, no backup, stale knowledge: Risks lists each gap with the rule that raised it.",
      },
    ],
  },
  integrations: {
    title: "Connected evidence",
    summary: "What GitHub, Linear and Notion add, and how to read sync health.",
    minutes: 1,
    steps: [
      {
        target: section("GitHub"),
        title: "Read-only connections",
        body: "Relay reads pull requests, issues and pages as evidence. It never writes back to your tools.",
      },
      {
        target: 'a[href$="/integrations/health"]',
        title: "Sync health",
        body: "Each connector shows its last sync, failures and what to do about them. A connection only counts as ready once its first sync finishes.",
      },
    ],
  },
  memory_replay: {
    title: "Project Memory Replay",
    summary:
      "Replay how a responsibility got here: decisions, incidents and changes, with sources.",
    minutes: 2,
    steps: [
      {
        target: '[aria-label="Filter by category"]',
        title: "Filter the history",
        body: "Every event is a fact from a source. Filter by category (decisions, incidents, releases) to follow one thread.",
      },
      {
        target: '[aria-label="Events"]',
        title: "Inspect any event",
        body: "Open an event to see where it came from, how its category was derived and which events it is linked to.",
      },
      {
        target: '[aria-label="Replay position"]',
        title: "Replay it",
        body: "Play the history forward, pause or step through it. AI chapters are labelled Inferred and cite the events they rest on.",
      },
      {
        target: '[aria-label="Ask about this history"]',
        title: "Ask the history",
        body: "Ask why something is the way it is. Answers cite events, or say the history doesn't record it.",
      },
    ],
  },
  what_if: {
    title: "What If? simulator",
    summary: "See what breaks if someone is away, and who could cover, without changing anything.",
    minutes: 2,
    steps: [
      {
        target: '[data-tour="simulator-form"]',
        title: "Pick a person and a period",
        body: "Choose who is unavailable and for how long. Optionally add a backup to see whether the gap closes.",
      },
      {
        target: section("Who could cover?"),
        title: "Compare cover candidates",
        body: "Candidates come from recorded links (planned recipient, existing role, team, department). Each is simulated with the same rules and compared with nobody stepping in.",
      },
      {
        title: "Simulations change nothing",
        body: "The simulator only reads. To act on it, start a real case with Prepare handover: that is a separate, audited step.",
      },
    ],
  },
  copilot: {
    title: "Handover Copilot",
    summary: "Read an evidence-backed handover brief and ask questions about it.",
    minutes: 2,
    steps: [
      {
        target: section("What you now own"),
        title: "A structured brief",
        body: "What you now own, in-flight work, decisions, gaps, risks and first steps. Each statement is labelled Fact, Rule or AI inference.",
      },
      {
        target: "#copilot-heading",
        title: "Ask about the handover",
        body: "Answers use only the evidence behind this brief and cite it. If the evidence doesn't say, you get 'Not in the evidence', never a guess.",
      },
      {
        target: '[data-tour="capsule-versions"]',
        title: "Versions and changes",
        body: "Every edit is a new version that needs approval. Compare any two versions to see exactly what changed.",
      },
    ],
  },
  recipient: {
    title: "After you accept a handover",
    summary: "Where your new responsibilities, tasks and questions show up.",
    minutes: 1,
    steps: [
      {
        target: '[aria-label="Handovers waiting for you"]',
        title: "Handovers addressed to you",
        body: "Open the brief, read it and acknowledge it. The brief then shows your next steps.",
      },
      {
        title: "Your work in one place",
        body: "Tasks assigned to you across cases, reviews and anything waiting on your input appear on My Work.",
      },
    ],
  },
  verify: {
    title: "Verify a transfer",
    summary: "Check that ownership really moved after a case was executed.",
    minutes: 1,
    steps: [
      {
        target: '[data-tour="case-list"]',
        title: "Completed cases",
        body: "Open a completed case: its status history and audit trail record who executed it and when.",
      },
      {
        title: "Ownership history",
        body: "Each responsibility keeps its ownership history, so you can confirm the new owner and when the change took effect.",
      },
    ],
  },
};
