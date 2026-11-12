import type { CasePriority, CaseStatus, CaseType } from "@/lib/types";

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
  onboarding: {
    label: "Onboarding",
    description:
      "Someone is joining or taking on new work: plan what they receive, their access and readiness.",
  },
  project_handover: {
    label: "Project handover",
    description:
      "Hand a project's context, decisions, open work and knowledge to a new lead or team.",
  },
};

export const STATUS_LABEL: Record<CaseStatus, string> = {
  draft: "Draft",
  investigating: "Investigating",
  awaiting_input: "Awaiting input",
  planning: "Planning",
  awaiting_review: "Awaiting review",
  ready_for_transfer: "Ready for transfer",
  executing: "Executing",
  verification: "Verification",
  blocked: "Blocked",
  reopened: "Reopened",
  completed: "Completed",
  cancelled: "Cancelled",
};

export const PRIORITY_LABEL: Record<CasePriority, string> = {
  low: "Low",
  normal: "Normal",
  high: "High",
  urgent: "Urgent",
};

export const CRITERION_LABEL: Record<string, string> = {
  attestation: "Attestation",
  task_completed: "Tasks completed",
  artefact_linked: "Artefact linked",
  supervised_demo: "Supervised demo",
  access_confirmed: "Access confirmed",
  qa_reviewed: "Q&A reviewed",
  rehearsal: "Rehearsal",
};
