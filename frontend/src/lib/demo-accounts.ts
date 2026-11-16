// Shared sign-ins for judges: one real WorkOS account per role, all members of the
// "Northwind Labs (judges)" sample workspace (seeded by `relay-seed-judges`). They exist only
// so judges can see each role without inviting anyone; every account behaves exactly like a
// real user in a real workspace. Ordered by how much of the product each one shows.

export const DEMO_PASSWORD = "relay-password@987";

export type DemoAccount = { role: string; label: string; email: string; shows: string };

export const DEMO_ACCOUNTS: DemoAccount[] = [
  {
    role: "owner",
    label: "Owner",
    email: "demo-owner@example.com",
    shows: "Everything, plus Try Relay as… to switch roles. Start here.",
  },
  {
    role: "continuity_manager",
    label: "Continuity manager",
    email: "demo-continuity@example.com",
    shows: "Runs the handover: cases, Autopilot, approvals, What If?",
  },
  {
    role: "member",
    label: "Member",
    email: "demo-member@example.com",
    shows: "Receives the brief, answers the interview, asks Relay.",
  },
  {
    role: "auditor",
    label: "Auditor",
    email: "demo-auditor@example.com",
    shows: "Reads everything incl. the audit log; can change nothing.",
  },
  {
    role: "admin",
    label: "Admin",
    email: "demo-admin@example.com",
    shows: "Members, integrations, policies and AI settings.",
  },
  {
    role: "knowledge_steward",
    label: "Knowledge steward",
    email: "demo-steward@example.com",
    shows: "Verifies knowledge and settles disputes.",
  },
  {
    role: "team_manager",
    label: "Team manager",
    email: "demo-teamlead@example.com",
    shows: "Manages only the responsibilities their teams hold.",
  },
  {
    role: "guest",
    label: "Guest",
    email: "demo-guest@example.com",
    shows: "An outside contractor: read-only, no AI output.",
  },
];

export function demoEmail(role: string | null): string | undefined {
  return DEMO_ACCOUNTS.find((a) => a.role === role)?.email;
}
