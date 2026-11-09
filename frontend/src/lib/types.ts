// Mirrors the Relay API response models (backend `*View` classes) field-for-field.

export type Criticality = "critical" | "high" | "standard" | "low";
export type Role = "primary" | "co_owner" | "backup" | "temporary";
export type Severity = "high" | "medium" | "low";

export type WorkspaceView = { id: string; name: string; role: string };

export type AssigneeView = {
  type: "person" | "team";
  id: string;
  name: string;
  status: string;
  department_name: string | null;
};

export type AssignmentView = {
  id: string;
  role: Role;
  assignee: AssigneeView;
  valid_from: string;
  valid_to: string | null;
  state: "current" | "scheduled" | "ended";
  reason: string | null;
};

export type ResponsibilitySummary = {
  id: string;
  name: string;
  category: string | null;
  criticality: Criticality;
  status: "active" | "archived";
  primary_owner: AssigneeView | null;
  backup_count: number;
  updated_at: string;
};

export type ResponsibilityDetail = {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  criticality: Criticality;
  status: "active" | "archived";
  version: number;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
  as_of: string;
  owners_as_of: AssignmentView[];
  assignments: AssignmentView[];
  assets: LinkedAssetView[];
};

export type ChangeView = {
  id: string;
  assignment_id: string;
  change_type: "assigned" | "ended";
  role: Role;
  assignee: AssigneeView;
  valid_from: string;
  valid_to: string | null;
  reason: string | null;
  changed_by: string;
  changed_at: string;
};

export type PersonView = {
  id: string;
  display_name: string;
  email: string | null;
  title: string | null;
  github_login: string | null;
  department_id: string | null;
  department_name: string | null;
  status: "active" | "archived";
  created_at: string;
};

export type TeamMemberView = { person_id: string; display_name: string };

export type TeamView = {
  id: string;
  name: string;
  description: string | null;
  github_slug: string | null;
  department_id: string | null;
  department_name: string | null;
  status: "active" | "archived";
  created_at: string;
  members: TeamMemberView[];
};

export type RiskSubjectView = { id: string; name: string; criticality: Criticality };

export type RiskView = {
  key: string;
  rule: string;
  severity: Severity;
  title: string;
  explanation: string;
  recommendation: string;
  responsibility: RiskSubjectView | null;
  person_id: string | null;
  person_name: string | null;
  related: RiskSubjectView[];
  status: RiskStatus;
  note: string | null;
  accepted_until: string | null;
  decided_by_name: string | null;
  decided_at: string | null;
  first_detected_at: string | null;
};

export type RiskStatus = "open" | "acknowledged" | "accepted" | "resolved";

export type ResolvedRiskView = {
  key: string;
  rule: string;
  severity: Severity;
  title: string;
  subject: string | null;
  first_detected_at: string;
  resolved_at: string;
};

export type RecentChangeView = {
  changed_at: string;
  change_type: "assigned" | "ended";
  role: Role;
  assignee_name: string;
  responsibility_id: string;
  responsibility_name: string;
  reason: string | null;
};

export type OverviewView = {
  active_responsibilities: number;
  without_primary_owner: number;
  critical_without_backup: number;
  open_risks: number;
  acknowledged_risks: number;
  accepted_risks: number;
  risks_by_severity: Record<Severity, number>;
  top_risks: RiskView[];
  recent_changes: RecentChangeView[];
};

export type CaseType = "transfer" | "coverage" | "departure";
export type CaseStatus = "draft" | "planning" | "executing" | "completed" | "cancelled";

export type CaseSummary = {
  id: string;
  case_type: CaseType;
  title: string;
  status: CaseStatus;
  outcome: "completed" | "completed_with_exceptions" | "cancelled" | null;
  affected_person_name: string | null;
  starts_at: string;
  ends_at: string | null;
  scope_count: number;
  open_tasks: number;
  overdue_tasks: number;
  emergency: boolean;
  emergency_reason: string | null;
  updated_at: string;
};

export type RecipientView = { type: "person" | "team"; id: string; name: string };

export type ScopeItemView = {
  id: string;
  responsibility_id: string;
  responsibility_name: string;
  criticality: Criticality;
  role: Role;
  current_owner_name: string | null;
  recipient: RecipientView | null;
  handover_notes: string | null;
  exception_reason: string | null;
  state: "planned" | "applied" | "excepted";
};

export type TaskView = {
  id: string;
  case_id: string;
  scope_item_id: string | null;
  title: string;
  description: string | null;
  assignee_user_id: string | null;
  assignee_name: string | null;
  due_at: string | null;
  status: "open" | "done" | "cancelled";
  overdue: boolean;
  completed_at: string | null;
};

export type CriterionView = {
  id: string;
  scope_item_id: string | null;
  criterion_type: string;
  title: string;
  mandatory: boolean;
  status: "pending" | "met" | "blocked" | "waived";
  note: string | null;
  resolved_at: string | null;
};

export type ApprovalView = {
  id: string;
  plan_version: number;
  decision: "approved" | "rejected";
  comment: string | null;
  sod_exception_reason: string | null;
  approver_user_id: string;
  approver_name: string | null;
  decided_at: string;
  current: boolean;
};

export type CaseAction =
  | "edit"
  | "cancel"
  | "submit"
  | "decide"
  | "execute"
  | "complete"
  | "extend"
  | "add_task"
  | "add_criterion"
  | "set_emergency"
  | "comment";

export type CaseDetail = CaseSummary & {
  reason: string | null;
  plan_version: number;
  initiator_user_id: string;
  coordinator_user_id: string;
  coordinator_name: string | null;
  critical: boolean;
  approved: boolean;
  readiness_met: number;
  readiness_total: number;
  readiness_blocked: number;
  allowed_actions: CaseAction[];
  scope: ScopeItemView[];
  tasks: TaskView[];
  criteria: CriterionView[];
  approvals: ApprovalView[];
};

export type HistoryView = {
  occurred_at: string;
  action: string;
  actor_name: string | null;
  details: Record<string, string | number | boolean | null>;
};

export type WorkspaceRole = "owner" | "admin" | "member" | "guest" | "auditor";

export type WorkspaceMemberView = {
  user_id: string;
  name: string;
  email: string | null;
  role: WorkspaceRole;
  status: "active" | "suspended" | "removed";
  joined_at: string;
};

export type InvitationView = {
  id: string;
  email: string;
  role: WorkspaceRole;
  status: string;
  expired: boolean;
  email_sent: boolean;
  created_at: string;
  expires_at: string;
};

export type MyInvitationView = {
  id: string;
  workspace_id: string;
  workspace_name: string;
  role: WorkspaceRole;
  expires_at: string;
};

export type InstallationView = {
  id: string;
  installation_id: number;
  account_login: string;
  account_type: string;
  status: "active" | "revoked" | "disconnected";
  last_synced_at: string | null;
  last_sync_status: "never" | "queued" | "ok" | "partial" | "error";
  last_sync_error: string | null;
};

export type RepositoryView = {
  id: string;
  installation_ref: string;
  full_name: string;
  html_url: string;
  private: boolean;
  archived: boolean;
  selected: boolean;
  accessible: boolean;
  last_synced_at: string | null;
  sync_error: string | null;
  responsibility_id: string | null;
};

export type IntegrationView = {
  configured: boolean;
  installations: InstallationView[];
  repositories: RepositoryView[];
  open_suggestions: number;
};

export type SuggestionView = {
  id: string;
  repository_id: string;
  repository: string;
  repository_url: string;
  handle: string;
  handle_type: "user" | "team" | "catalog";
  proposed_role: "primary" | "co_owner" | "backup";
  reason: string;
  evidence: { source: string; detail: string; url?: string | null }[];
  status: "open" | "approved" | "dismissed" | "deferred" | "withdrawn";
  match: { type: "person" | "team"; id: string; name: string } | null;
  responsibility_id: string | null;
};

export type MyWorkView = {
  emergencies: CaseSummary[];
  tasks: TaskView[];
  approvals: CaseSummary[];
  attention: CaseSummary[];
  mentions: {
    notification_id: string;
    case_id: string;
    case_title: string;
    actor_name: string | null;
    created_at: string;
  }[];
  reviews: {
    knowledge_id: string;
    title: string;
    responsibility_id: string;
    responsibility_name: string;
  }[];
};

export type DepartmentView = {
  id: string;
  name: string;
  description: string | null;
  status: "active" | "archived";
  people_count: number;
  team_count: number;
  created_at: string;
};

export type AssetType =
  "repository" | "service" | "project" | "process" | "vendor" | "document_collection" | "other";

export type LinkedAssetView = {
  id: string;
  name: string;
  asset_type: AssetType;
  url: string | null;
  status: "active" | "archived";
  relationship: "stewards" | "uses";
};

export type AssetSummary = {
  id: string;
  name: string;
  asset_type: AssetType;
  description: string | null;
  url: string | null;
  status: "active" | "archived";
  responsibility_count: number;
  updated_at: string;
};

export type AssetResponsibilityView = {
  id: string;
  name: string;
  criticality: Criticality;
  relationship: "stewards" | "uses";
  primary_owner: AssigneeView | null;
};

export type AssetDetail = AssetSummary & {
  created_at: string;
  responsibilities: AssetResponsibilityView[];
};

export type ImportKind = "people" | "responsibilities" | "assignments";

export type ImportRowView = {
  line: number;
  action: "create" | "skip" | "error";
  label: string;
  message: string | null;
};

export type ImportResultView = {
  kind: ImportKind;
  committed: boolean;
  columns: string[];
  ignored_columns: string[];
  rows: ImportRowView[];
  created: number;
  skipped: number;
  errors: number;
};

export type MentionView = { user_id: string; name: string };

export type ActivityView = {
  kind: "comment" | "event";
  id: string;
  occurred_at: string;
  actor_name: string | null;
  body: string | null;
  mentions: MentionView[];
  action: string | null;
  details: Record<string, string | number | boolean | null>;
};

export type NotificationKind =
  | "task_assigned"
  | "task_due_soon"
  | "task_overdue"
  | "approval_requested"
  | "mentioned"
  | "case_update"
  | "automation";

export type NotificationView = {
  id: string;
  kind: NotificationKind;
  detail: string | null;
  case_id: string | null;
  case_title: string | null;
  case_emergency: boolean;
  responsibility_id: string | null;
  responsibility_name: string | null;
  task_id: string | null;
  task_title: string | null;
  actor_name: string | null;
  created_at: string;
  read_at: string | null;
};

export type InboxView = { unread: number; items: NotificationView[] };

export type BriefingItemView = {
  responsibility_id: string;
  responsibility_name: string;
  criticality: Criticality;
  covered_by: string | null;
  cover_ends_at: string | null;
  restoration: "not_started" | "covering" | "restored" | "excepted";
  original_owner_active: boolean;
  handover_notes: string | null;
  exception_reason: string | null;
};

export type BriefingView = {
  case_id: string;
  title: string;
  person_name: string | null;
  period_start: string;
  period_end: string;
  returned: boolean;
  items: BriefingItemView[];
  ownership_changes: {
    changed_at: string;
    responsibility_name: string;
    change_type: string;
    role: Role;
    assignee_name: string;
    reason: string | null;
  }[];
  responsibility_events: {
    occurred_at: string;
    responsibility_name: string;
    action: string;
    actor_name: string | null;
  }[];
  tasks: {
    title: string;
    status: string;
    assignee_name: string | null;
    completed_at: string | null;
  }[];
  notes: ActivityView[];
  knowledge: {
    responsibility_name: string;
    outcome: "handed_over" | "missing";
    title: string | null;
    url: string | null;
    note: string | null;
    recorded_at: string;
  }[];
  exceptions: number;
};

export type AuditEventView = {
  id: string;
  occurred_at: string;
  actor_type: "user" | "system";
  actor_user_id: string | null;
  actor_name: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  target_label: string | null;
  metadata: Record<string, string | number | boolean | null>;
};

export type PersonRef = { id: string; name: string };

export type IdentityView = {
  id: string;
  login: string;
  name: string | null;
  public_email: string | null;
  link_status: "unmatched" | "suggested" | "linked" | "dismissed";
  person: PersonRef | null;
  suggested_person: PersonRef | null;
  match_reason: string | null;
  teams: string[];
  recent_items: number;
  profile_url: string;
};

export type GitHubTeamView = {
  id: string;
  org: string;
  slug: string;
  name: string;
  removed: boolean;
  linked_team: PersonRef | null;
  members: { login: string; person: PersonRef | null }[];
};

export type SignalView = {
  key: string;
  kind: "owner_inactive" | "active_non_owner" | "unmaintained" | "unowned_active";
  severity: Severity;
  title: string;
  explanation: string;
  repository: string;
  repository_url: string;
  responsibility: PersonRef | null;
  evidence: { label: string; url: string }[];
};

export type BulkResultView = {
  id: string;
  ok: boolean;
  status: string | null;
  error: string | null;
};

export type KnowledgeKind = "note" | "link" | "document" | "procedure" | "context";

export type KnowledgeView = {
  id: string;
  responsibility_id: string;
  responsibility_name: string;
  kind: KnowledgeKind;
  title: string;
  body: string | null;
  url: string | null;
  visibility: "workspace" | "managers";
  origin: "person" | "notion";
  status: "active" | "archived" | "withdrawn";
  author_name: string;
  created_at: string;
  updated_at: string;
  last_reviewed_at: string | null;
  last_reviewed_by_name: string | null;
  freshness: "fresh" | "stale";
  can_edit: boolean;
};

export type KnowledgeOverviewView = {
  results: KnowledgeView[];
  missing: { responsibility_id: string; responsibility_name: string; criticality: Criticality }[];
  stale_items: number;
  fresh_items: number;
};

export type CaseKnowledgeItemView = {
  responsibility_id: string;
  responsibility_name: string;
  knowledge: KnowledgeView[];
  records: {
    id: string;
    knowledge_item_id: string | null;
    outcome: "handed_over" | "missing";
    note: string | null;
    recorded_by_name: string;
    recorded_at: string;
  }[];
};

export type EmailCategory = "tasks" | "reminders" | "approvals" | "mentions" | "case_updates";

export type PreferenceView = { category: EmailCategory; label: string; enabled: boolean };

export type DeliveryView = {
  id: string;
  kind: string;
  recipient: string;
  status: "pending" | "sent" | "failed" | "skipped";
  attempts: number;
  last_error: string | null;
  created_at: string;
  sent_at: string | null;
};

export type EmailStatusView = {
  configured: boolean;
  sender: string | null;
  healthy: boolean;
  sent_24h: number;
  failed_24h: number;
  pending: number;
  recent_failures: DeliveryView[];
};

export type LinearConnectionView = {
  id: string;
  organization_name: string;
  url_key: string | null;
  status: "active" | "revoked" | "disconnected";
  last_synced_at: string | null;
  last_sync_status: "never" | "queued" | "ok" | "partial" | "error";
  last_sync_error: string | null;
  next_reconcile_at: string | null;
};

export type LinearProjectView = {
  id: string;
  name: string;
  state: string | null;
  url: string;
  lead: string | null;
  open_issues: number;
  recent_issues: number;
  responsibility_id: string | null;
  responsibility_name: string | null;
};

export type LinearIntegrationView = {
  configured: boolean;
  connections: LinearConnectionView[];
  teams: { id: string; key: string; name: string }[];
  projects: LinearProjectView[];
  identities_to_review: number;
};

export type LinearIdentityView = {
  id: string;
  name: string;
  email: string | null;
  active: boolean;
  link_status: "unmatched" | "suggested" | "linked" | "dismissed";
  person: PersonRef | null;
  suggested_person: PersonRef | null;
  match_reason: string | null;
  recent_issues: number;
};

export type LinearSignalView = {
  key: string;
  kind: "unowned_important" | "active_uncovered" | "owner_absent";
  severity: Severity;
  title: string;
  explanation: string;
  project: string;
  project_url: string;
  responsibility_id: string | null;
  evidence: { label: string; url: string }[];
};

export type NotionConnectionView = {
  id: string;
  workspace_name: string;
  status: "active" | "revoked" | "disconnected";
  last_synced_at: string | null;
  last_sync_status: "never" | "queued" | "ok" | "partial" | "error";
  last_sync_error: string | null;
  next_reconcile_at: string | null;
};

export type NotionSourceView = {
  id: string;
  kind: "page" | "database";
  title: string;
  url: string;
  last_edited_at: string | null;
  removed: boolean;
  responsibility_id: string | null;
  responsibility_name: string | null;
  visibility: "workspace" | "managers" | null;
  imported_pages: number;
  withdrawn_pages: number;
  last_imported_at: string | null;
};

export type NotionIntegrationView = {
  configured: boolean;
  connections: NotionConnectionView[];
  sources: NotionSourceView[];
};

export type DebtItem = {
  label: string;
  detail: string | null;
  kind: "responsibility" | "case" | "person";
  id: string;
  points: number;
};

export type DebtComponent = {
  key: string;
  label: string;
  rule: string;
  count: number;
  points: number;
  items: DebtItem[];
};

export type InsightsView = {
  generated_at: string;
  filters: { department_id: string | null; criticality: string | null };
  departments: { id: string; name: string }[];
  coverage: {
    responsibilities: number;
    with_primary: number;
    with_backup: number;
    critical: number;
    critical_with_backup: number;
    archived_owner_assignments: number;
    single_person_dependencies: number;
  };
  knowledge: {
    responsibilities_with_knowledge: number;
    responsibilities_missing_knowledge: number;
    responsibilities_only_stale: number;
    stale_items: number;
    imported_needing_review: number;
    review_interval_days: number;
  };
  operations: {
    open_cases: number;
    emergency_cases: number;
    overdue_tasks: number;
    overdue_cases: number;
    closed_last_90_days: number;
    median_days_to_close: number | null;
    risks_resolved_last_30_days: number;
    accepted_risks: number;
  };
  continuity_debt: number;
  debt: DebtComponent[];
};

export type AutomationTemplate =
  | "critical_without_backup"
  | "no_primary_owner"
  | "stale_knowledge"
  | "archived_owner"
  | "coverage_ending"
  | "case_overdue"
  | "task_overdue"
  | "risk_acceptance_expiring";

export type AutomationRunView = {
  id: string;
  trigger: "schedule" | "manual" | "retry";
  status: "ok" | "failed";
  matched: number;
  actions: number;
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

export type AutomationRuleView = {
  template: AutomationTemplate;
  title: string;
  description: string;
  enabled: boolean;
  action: "notify" | "create_follow_up";
  assignee_user_id: string | null;
  assignee_name: string | null;
  last_run_at: string | null;
  last_status: "never" | "ok" | "failed";
  last_error: string | null;
  next_run_at: string | null;
  open_follow_ups: number;
  runs: AutomationRunView[];
};

export type FollowUpView = {
  id: string;
  template: AutomationTemplate;
  title: string;
  detail: string | null;
  responsibility_id: string | null;
  case_id: string | null;
  assignee_user_id: string | null;
  status: "open" | "done";
  created_at: string;
};

export type PolicyView = {
  critical_requires_backup: boolean;
  knowledge_review_days: number;
  updated_by_name: string | null;
  updated_at: string | null;
};

export type SearchKind =
  "responsibility" | "person" | "team" | "department" | "asset" | "case" | "knowledge" | "risk";

export type SearchHit = {
  kind: SearchKind;
  id: string;
  title: string;
  detail: string | null;
  status: string | null;
};

export type SearchView = { query: string; hits: SearchHit[] };

export type ProfileRef = { id: string; name: string; detail: string | null };
export type ProfileView = {
  kind: "person" | "team" | "department";
  id: string;
  name: string;
  status: string;
  description: string | null;
  email: string | null;
  title: string | null;
  department: ProfileRef | null;
  teams: ProfileRef[];
  members: ProfileRef[];
  people: ProfileRef[];
  roles: {
    responsibility_id: string;
    responsibility_name: string;
    criticality: Criticality;
    role: string;
    holder: string;
    valid_from: string;
    valid_to: string | null;
    state: "current" | "scheduled";
  }[];
  risks: {
    key: string;
    title: string;
    severity: Severity;
    status: string;
    subject: string | null;
  }[];
  cases: {
    id: string;
    title: string;
    case_type: CaseType;
    status: string;
    emergency: boolean;
    relation: string;
  }[];
  identities: { provider: string; handle: string }[];
  continuity_debt: number | null;
};
