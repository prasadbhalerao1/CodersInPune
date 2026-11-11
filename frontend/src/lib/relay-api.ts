import "server-only";

import { withAuth } from "@workos-inc/authkit-nextjs";
import { connection } from "next/server";

import type {
  AiAdminView,
  AnswerView,
  HistoryAnswer,
  CandidatesView,
  NarrativeView,
  SimulationView,
  TimelineCategory,
  TimelineView,
  AnalysisView,
  CapsuleSummary,
  CapsuleVersionView,
  CapsuleView,
  InterviewView,
  RunDetail,
  RunView,
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
  NotionPreviewView,
  EmailStatusView,
  PreferenceView,
  CaseKnowledgeItemView,
  KnowledgeOverviewView,
  KnowledgeView,
  GitHubTeamView,
  IdentityView,
  SignalView,
  AssetDetail,
  MetricsView,
  SnapshotView,
  ExpertView,
  ConnectorView,
  ExternalActionView,
  ExternalTargetsView,
  IdentityConflict,
  RoleView,
  PrivacyView,
  ReviewItemView,
  KnowledgeCompareView,
  KnowledgeGovernanceView,
  ResponsibilityTypeView,
  StewardshipView,
  TierView,
  TaskDetail,
  ImpactView,
  ParticipantView,
  SavedPage,
  SavedViewView,
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

async function relayResponse(path: string, init: RequestInit, accept: string): Promise<Response> {
  // Every Relay call is per-user data; render at request time (withAuth reads the clock).
  await connection();
  const { accessToken } = await withAuth({ ensureSignedIn: true });
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  headers.set("Accept", accept);
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
  return response;
}

export async function relayFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await relayResponse(path, init, "application/json");
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

/** A list page: the rows, plus the cursor for the next page (null on the last page). */
export type Paged<T> = T[] & { nextCursor?: string | null };

async function relayPaged<T>(path: string): Promise<Paged<T>> {
  const response = await relayResponse(path, {}, "application/json");
  const items = (await response.json()) as T[];
  return Object.assign(items, { nextCursor: response.headers.get("X-Next-Cursor") });
}

/** Plain-text endpoints (e.g. Markdown exports). */
export async function relayText(path: string): Promise<string> {
  return (await relayResponse(path, {}, "text/plain")).text();
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
  createSampleWorkspace: (idempotencyKey: string) =>
    relayFetch<WorkspaceView>("/workspaces/sample", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
    }),

  syncMyProfile: (displayName: string | undefined, email: string | undefined) =>
    relayFetch<void>("/me/profile", {
      method: "PUT",
      body: JSON.stringify({ display_name: displayName, email }),
    }),

  overview: (id: string) => relayFetch<OverviewView>(`${ws(id)}/overview`),
  risks: (id: string, status: "active" | "accepted" | "all" = "active") =>
    relayFetch<RiskView[]>(withQuery(`${ws(id)}/risks`, { status })),
  resolvedRisks: (id: string) => relayFetch<ResolvedRiskView[]>(`${ws(id)}/risks/resolved`),

  listResponsibilities: (id: string, query?: Query) =>
    relayPaged<ResponsibilitySummary>(withQuery(`${ws(id)}/responsibilities`, query)),
  getResponsibility: (id: string, rid: string, asOf?: string) =>
    relayFetch<ResponsibilityDetail>(
      withQuery(`${ws(id)}/responsibilities/${encodeURIComponent(rid)}`, { as_of: asOf }),
    ),
  responsibilityHistory: (id: string, rid: string) =>
    relayFetch<ChangeView[]>(`${ws(id)}/responsibilities/${encodeURIComponent(rid)}/history`),

  listPeople: (id: string, query?: Query) =>
    relayPaged<PersonView>(withQuery(`${ws(id)}/people`, query)),
  listTeams: (id: string, query?: Query) =>
    relayFetch<TeamView[]>(withQuery(`${ws(id)}/teams`, query)),
  departments: (id: string, query?: Query) =>
    relayFetch<DepartmentView[]>(withQuery(`${ws(id)}/departments`, query)),
  assets: (id: string, query?: Query) =>
    relayPaged<AssetSummary>(withQuery(`${ws(id)}/assets`, query)),
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
  searchFull: (id: string, q: string, kind?: string) =>
    relayFetch<SearchView>(
      withQuery(`${ws(id)}/search`, kind ? { q, full: "true", kind } : { q, full: "true" }),
    ),
  experts: (id: string, q: string) =>
    relayFetch<ExpertView[]>(withQuery(`${ws(id)}/search/experts`, { q })),
  policy: (id: string) => relayFetch<PolicyView>(`${ws(id)}/policy`),
  notionPreview: (id: string, sourceId: string) =>
    relayFetch<NotionPreviewView>(
      `${ws(id)}/integrations/notion/sources/${encodeURIComponent(sourceId)}/preview`,
    ),
  notion: (id: string) => relayFetch<NotionIntegrationView>(`${ws(id)}/integrations/notion`),
  linearSignals: (id: string) =>
    relayFetch<LinearSignalView[]>(`${ws(id)}/integrations/linear/signals`),
  githubSuggestions: (id: string, status = "open") =>
    relayFetch<SuggestionView[]>(
      withQuery(`${ws(id)}/integrations/github/suggestions`, { status }),
    ),
  myWork: (id: string) => relayFetch<MyWorkView>(`${ws(id)}/my-work`),
  listCases: (id: string, query?: Query) =>
    relayPaged<CaseSummary>(withQuery(`${ws(id)}/cases`, query)),
  getCase: (id: string, caseId: string) =>
    relayFetch<CaseDetail>(`${ws(id)}/cases/${encodeURIComponent(caseId)}`),
  caseExport: (id: string, caseId: string) =>
    relayText(`${ws(id)}/cases/${encodeURIComponent(caseId)}/export.md`),
  knowledgeItem: (id: string, itemId: string) =>
    relayFetch<KnowledgeView>(`${ws(id)}/knowledge/${encodeURIComponent(itemId)}`),
  knowledgeGovernance: (id: string, itemId: string) =>
    relayFetch<KnowledgeGovernanceView>(
      `${ws(id)}/knowledge/${encodeURIComponent(itemId)}/governance`,
    ),
  knowledgeCompare: (id: string, itemId: string, from: number, to: number) =>
    relayFetch<KnowledgeCompareView>(
      withQuery(`${ws(id)}/knowledge/${encodeURIComponent(itemId)}/compare`, {
        from_version: String(from),
        to_version: String(to),
      }),
    ),
  roles: (id: string) => relayFetch<RoleView[]>(`${ws(id)}/roles`),
  identityConflicts: (id: string) => relayFetch<IdentityConflict[]>(`${ws(id)}/identity-conflicts`),
  responsibilityTypes: (id: string) =>
    relayFetch<ResponsibilityTypeView[]>(`${ws(id)}/responsibilities/types`),
  stewardship: (id: string, responsibilityId: string) =>
    relayFetch<StewardshipView>(
      `${ws(id)}/responsibilities/${encodeURIComponent(responsibilityId)}/stewardship`,
    ),
  policyTiers: (id: string) => relayFetch<TierView[]>(`${ws(id)}/policy/tiers`),
  caseTask: (id: string, caseId: string, taskId: string) =>
    relayFetch<TaskDetail>(
      `${ws(id)}/cases/${encodeURIComponent(caseId)}/tasks/${encodeURIComponent(taskId)}`,
    ),
  casePrivacy: (id: string, caseId: string) =>
    relayFetch<PrivacyView>(`${ws(id)}/cases/${encodeURIComponent(caseId)}/privacy`),
  reviewInbox: (id: string) => relayFetch<ReviewItemView[]>(`${ws(id)}/review-inbox`),
  trendMetrics: (id: string, days: number) =>
    relayFetch<MetricsView>(withQuery(`${ws(id)}/insights/metrics`, { days: String(days) })),
  metricSnapshots: (id: string) => relayFetch<SnapshotView[]>(`${ws(id)}/insights/snapshots`),
  connectorHealth: (id: string) => relayFetch<ConnectorView[]>(`${ws(id)}/integrations/health`),
  externalTargets: (id: string) => relayFetch<ExternalTargetsView>(`${ws(id)}/external-targets`),
  taskExternal: (id: string, caseId: string, taskId: string) =>
    relayFetch<ExternalActionView[]>(
      `${ws(id)}/cases/${encodeURIComponent(caseId)}/tasks/${encodeURIComponent(taskId)}/external`,
    ),
  caseImpact: (id: string, caseId: string) =>
    relayFetch<ImpactView>(`${ws(id)}/cases/${encodeURIComponent(caseId)}/impact`),
  caseParticipants: (id: string, caseId: string) =>
    relayFetch<ParticipantView[]>(`${ws(id)}/cases/${encodeURIComponent(caseId)}/participants`),
  savedViews: (id: string, page: SavedPage) =>
    relayFetch<SavedViewView[]>(withQuery(`${ws(id)}/saved-views`, { page })),
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

  analysis: (id: string, caseId: string) =>
    relayFetch<AnalysisView>(`${ws(id)}/cases/${caseId}/analysis`),
  interview: (id: string, caseId: string) =>
    relayFetch<InterviewView>(`${ws(id)}/cases/${caseId}/interview`),
  caseCapsules: (id: string, caseId: string) =>
    relayFetch<CapsuleSummary[]>(`${ws(id)}/cases/${caseId}/capsules`),
  capsule: (id: string, capsuleId: string, version?: number) =>
    relayFetch<CapsuleView>(
      withQuery(`${ws(id)}/ai/capsules/${capsuleId}`, { version: version?.toString() }),
    ),
  capsuleQuestions: (id: string, capsuleId: string) =>
    relayFetch<AnswerView[]>(`${ws(id)}/ai/capsules/${capsuleId}/questions`),
  askCapsule: (id: string, capsuleId: string, question: string) =>
    relayFetch<AnswerView>(`${ws(id)}/ai/capsules/${capsuleId}/questions`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
  simulation: (id: string, personId: string, backupId?: string, days?: string) =>
    relayFetch<SimulationView>(
      withQuery(`${ws(id)}/simulation`, { person_id: personId, backup_id: backupId, days }),
    ),
  simulationCandidates: (id: string, personId: string, days?: string) =>
    relayFetch<CandidatesView>(
      withQuery(`${ws(id)}/simulation/candidates`, { person_id: personId, days }),
    ),
  timeline: (id: string, responsibilityId: string, category?: TimelineCategory) =>
    relayFetch<TimelineView>(
      withQuery(`${ws(id)}/responsibilities/${responsibilityId}/timeline`, {
        category,
        limit: "500",
      }),
    ),
  storedNarrative: (id: string, responsibilityId: string) =>
    relayFetch<NarrativeView>(`${ws(id)}/responsibilities/${responsibilityId}/timeline/narrative`),
  askHistory: (id: string, responsibilityId: string, question: string) =>
    relayFetch<HistoryAnswer>(`${ws(id)}/responsibilities/${responsibilityId}/timeline/questions`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
  narrateTimeline: (id: string, responsibilityId: string) =>
    relayFetch<NarrativeView>(`${ws(id)}/responsibilities/${responsibilityId}/timeline/narrative`, {
      method: "POST",
    }),
  capsuleVersions: (id: string, capsuleId: string) =>
    relayFetch<CapsuleVersionView[]>(`${ws(id)}/ai/capsules/${capsuleId}/versions`),
  aiOverview: (id: string) => relayFetch<AiAdminView>(`${ws(id)}/ai`),
  aiRuns: (id: string) => relayFetch<RunView[]>(`${ws(id)}/ai/runs`),
  aiRun: (id: string, runId: string) => relayFetch<RunDetail>(`${ws(id)}/ai/runs/${runId}`),

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
