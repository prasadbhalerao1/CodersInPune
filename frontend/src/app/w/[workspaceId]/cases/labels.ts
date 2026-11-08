import type { CaseType } from "@/lib/types";

export const CASE_TYPES: Record<CaseType, { label: string; description: string }> = {
  transfer: {
    label: "Responsibility transfer",
    description: "Hand one or more responsibilities to new owners on an effective date.",
  },
  coverage: {
    label: "Temporary coverage",
    description:
      "Cover someone's responsibilities while they are away; ownership returns automatically.",
  },
  departure: {
    label: "Departure",
    description: "Someone is leaving: find everything they own and hand each piece over.",
  },
};

export const CRITERION_LABEL: Record<string, string> = {
  attestation: "Attestation",
  task_completed: "Tasks completed",
  artefact_linked: "Artefact linked",
  supervised_demo: "Supervised demo",
  access_confirmed: "Access confirmed",
  qa_reviewed: "Q&A reviewed",
};
