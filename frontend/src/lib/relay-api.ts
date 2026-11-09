import "server-only";

import { withAuth } from "@workos-inc/authkit-nextjs";
import { connection } from "next/server";

import type {
  ActivityView,
  LinearIdentityView,
  LinearIntegrationView,
  LinearSignalView,
  AutomationRuleView,
  FollowUpView,
  InsightsView,
  PolicyView,
  ProfileView,
  ResponsibilityContextView,
  SearchView,
  NotionIntegrationView,
  EmailStatusView,
  PreferenceView,
  CaseKnowledgeItemView,
  KnowledgeOverviewView,
  KnowledgeView,
  GitHubTeamView,
  IdentityView,
  SignalView,
  AssetDetail,
  AssetSummary,
  AuditEventView,
  BriefingView,
  DepartmentView,
  InboxView,
  ResolvedRiskView,
  IntegrationView,
  InvitationView,
  MyInvitationView,
  SuggestionView,
  CaseDetail,
  CaseSummary,
  ChangeView,
  HistoryView,
  WorkspaceMemberView,
  MyWorkView,
  OverviewView,
  PersonView,
  ResponsibilityDetail,
  ResponsibilitySummary,
  RiskView,
  TeamView,
  WorkspaceView,
} from "@/lib/types";

// Server-side client for the Relay API. The WorkOS access token stays on the server:
// it is read from the encrypted session cookie and sent as a bearer token, never exposed
// to the browser. The API verifies it and resolves workspaces through Relay membership.

export class RelayApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string | undefined,
    message: string,
  ) {
    super(message);
  }
}

type Query = Record<string, string | undefined>;

function apiBaseUrl(): string {
  const url = process.env.RELAY_API_URL;
  if (!url) throw new Error("RELAY_API_URL is not configured");
  return url.replace(/\/$/, "");
}

function withQuery(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) if (value) params.set(key, value);
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

export async function relayFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  // Every Relay call is per-user data; render at request time (withAuth reads the clock).
  await connection();
  const { accessToken } = await withAuth({ ensureSignedIn: true });
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");

  const response = await fetch(`${apiBaseUrl()}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as {
      code?: string;
      detail?: string | { msg: string }[];
    };
    const detail = Array.isArray(problem.detail)
      ? problem.detail.map((d) => d.msg).join("; ")
      : problem.detail;
    throw new RelayApiError(response.status, problem.code, detail ?? `Request failed`);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

const ws = (workspaceId: string) => `/workspaces/${encodeURIComponent(workspaceId)}`;

export const api = {
  listWorkspaces: () => relayFetch<WorkspaceView[]>("/workspaces"),
  getWorkspace: (id: string) => relayFetch<WorkspaceView>(ws(id)),
  createWorkspace: (name: string, idempotencyKey: string) =>
    relayFetch<WorkspaceView>("/workspaces", {
      method: "POST",
      body: JSON.stringify({ name }),
      headers: { "Idempotency-Key": idempotencyKey },
    }),

  overview: (id: string) => relayFetch<OverviewView>(`${ws(id)}/overview`),
  risks: (id: string, status: "active" | "accepted" | "all" = "active") =>
    relayFetch<RiskView[]>(withQuery(`${ws(id)}/risks`, { status })),
  resolvedRisks: (id: string) => relayFetch<ResolvedRiskView[]>(`${ws(id)}/risks/resolved`),

  listResponsibilities: (id: string, query?: Query) =>
    relayFetch<ResponsibilitySummary[]>(withQuery(`${ws(id)}/responsibilities`, query)),
  getResponsibility: (id: string, rid: string, asOf?: string) =>
    relayFetch<ResponsibilityDetail>(
      withQuery(`${ws(id)}/responsibilities/${encodeURIComponent(rid)}`, { as_of: asOf }),
    ),
  responsibilityHistory: (id: string, rid: string) =>
    relayFetch<ChangeView[]>(`${ws(id)}/responsibilities/${encodeURIComponent(rid)}/history`),

  listPeople: (id: string, query?: Query) =>
    relayFetch<PersonView[]>(withQuery(`${ws(id)}/people`, query)),
  listTeams: (id: string, query?: Query) =>
    relayFetch<TeamView[]>(withQuery(`${ws(id)}/teams`, query)),
  departments: (id: string, query?: Query) =>
    relayFetch<DepartmentView[]>(withQuery(`${ws(id)}/departments`, query)),
  assets: (id: string, query?: Query) =>
    relayFetch<AssetSummary[]>(withQuery(`${ws(id)}/assets`, query)),
  getAsset: (id: string, assetId: string) =>
    relayFetch<AssetDetail>(`${ws(id)}/assets/${encodeURIComponent(assetId)}`),

  members: (id: string, query?: Query) =>
    relayFetch<WorkspaceMemberView[]>(withQuery(`${ws(id)}/members`, query)),
  invitations: (id: string) => relayFetch<InvitationView[]>(`${ws(id)}/invitations`),
  myInvitations: () => relayFetch<MyInvitationView[]>("/me/invitations"),
  github: (id: string) => relayFetch<IntegrationView>(`${ws(id)}/integrations/github`),
  githubIdentities: (id: string, status?: string) =>
    relayFetch<IdentityView[]>(withQuery(`${ws(id)}/integrations/github/identities`, { status })),
  githubTeams: (id: string) => relayFetch<GitHubTeamView[]>(`${ws(id)}/integrations/github/teams`),
  githubSignals: (id: string) => relayFetch<SignalView[]>(`${ws(id)}/integrations/github/signals`),
  linear: (id: string) => relayFetch<LinearIntegrationView>(`${ws(id)}/integrations/linear`),
  linearIdentities: (id: string) =>
    relayFetch<LinearIdentityView[]>(`${ws(id)}/integrations/linear/identities`),
  insights: (id: string, query?: Query) =>
    relayFetch<InsightsView>(withQuery(`${ws(id)}/insights`, query)),
  automations: (id: string) => relayFetch<AutomationRuleView[]>(`${ws(id)}/automations`),
  followUps: (id: string, mine = true) =>
    relayFetch<FollowUpView[]>(withQuery(`${ws(id)}/follow-ups`, { mine: String(mine) })),
  profile: (id: string, kind: "people" | "teams" | "departments", ref: string) =>
    relayFetch<ProfileView>(`${ws(id)}/${kind}/${encodeURIComponent(ref)}/profile`),
  responsibilityContext: (id: string, rid: string) =>
    relayFetch<ResponsibilityContextView>(
      `${ws(id)}/responsibilities/${encodeURIComponent(rid)}/context`,
    ),
  search: (id: string, q: string) => relayFetch<SearchView>(withQuery(`${ws(id)}/search`, { q })),
  policy: (id: string) => relayFetch<PolicyView>(`${ws(id)}/policy`),
  notion: (id: string) => relayFetch<NotionIntegrationView>(`${ws(id)}/integrations/notion`),
  linearSignals: (id: string) =>
    relayFetch<LinearSignalView[]>(`${ws(id)}/integrations/linear/signals`),
  githubSuggestions: (id: string, status = "open") =>
    relayFetch<SuggestionView[]>(
      withQuery(`${ws(id)}/integrations/github/suggestions`, { status }),
    ),
  myWork: (id: string) => relayFetch<MyWorkView>(`${ws(id)}/my-work`),
  listCases: (id: string, query?: Query) =>
    relayFetch<CaseSummary[]>(withQuery(`${ws(id)}/cases`, query)),
  getCase: (id: string, caseId: string) =>
    relayFetch<CaseDetail>(`${ws(id)}/cases/${encodeURIComponent(caseId)}`),
  caseHistory: (id: string, caseId: string) =>
    relayFetch<HistoryView[]>(`${ws(id)}/cases/${encodeURIComponent(caseId)}/history`),
  caseActivity: (id: string, caseId: string) =>
    relayFetch<ActivityView[]>(`${ws(id)}/cases/${encodeURIComponent(caseId)}/activity`),
  caseBriefing: (id: string, caseId: string) =>
    relayFetch<BriefingView>(`${ws(id)}/cases/${encodeURIComponent(caseId)}/briefing`),
  knowledge: (id: string, query?: Query) =>
    relayFetch<KnowledgeOverviewView>(withQuery(`${ws(id)}/knowledge`, query)),
  responsibilityKnowledge: (id: string, rid: string) =>
    relayFetch<KnowledgeView[]>(`${ws(id)}/responsibilities/${encodeURIComponent(rid)}/knowledge`),
  caseKnowledge: (id: string, caseId: string) =>
    relayFetch<CaseKnowledgeItemView[]>(`${ws(id)}/cases/${encodeURIComponent(caseId)}/knowledge`),
  notificationPreferences: (id: string) =>
    relayFetch<PreferenceView[]>(`${ws(id)}/notifications/preferences`),
  emailStatus: (id: string) => relayFetch<EmailStatusView>(`${ws(id)}/email/status`),
  inbox: (id: string, query?: Query) =>
    relayFetch<InboxView>(withQuery(`${ws(id)}/notifications`, query)),
  auditEvents: (id: string, query?: Query) =>
    relayFetch<AuditEventView[]>(withQuery(`${ws(id)}/audit-events`, query)),

  send: <T>(id: string, method: "POST" | "PATCH" | "PUT" | "DELETE", path: string, body?: object) =>
    relayFetch<T>(`${ws(id)}${path}`, {
      method,
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
};

export const isOwner = (workspace: WorkspaceView) => workspace.role === "owner";

export const canAudit = (workspace: WorkspaceView) =>
  ["owner", "admin", "auditor"].includes(workspace.role);

export const canManage = (workspace: WorkspaceView) => ["owner", "admin"].includes(workspace.role);
