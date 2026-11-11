// Mirrors the Relay API response models (backend `*View` classes) field-for-field.

export type Criticality = "critical" | "high" | "standard" | "low";
export type Role = "primary" | "co_owner" | "backup" | "temporary";
export type Severity = "high" | "medium" | "low";

export type WorkspaceView = {
  id: string;
  name: string;
  role: string;
  deletion_scheduled_for: string | null;
};

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
  restricted: boolean;
  type_id: string | null;
  type_name: string | null;
  needs_verification: boolean;
  review_due: boolean;
  last_reviewed_at: string | null;
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
  restricted: boolean;
  type_id: string | null;
  type_name: string | null;
  escalation_path: string | null;
  escalation_contact: string | null;
  review_cadence_days: number | null;
  effective_review_days: number;
  last_reviewed_at: string | null;
  last_reviewed_by_name: string | null;
  review_due: boolean;
  needs_verification: boolean;
  procedures: string[];
  access_prerequisites: string[];
  accountable_person_id: string | null;
  accountable_person_name: string | null;
};

export type ResponsibilityTypeView = {
  id: string;
  name: string;
  description: string | null;
  review_cadence_days: number | null;
  responsibilities: number;
};

export type DependencyView = {
  id: string;
  direction: "outgoing" | "incoming";
  relationship: "depends_on" | "feeds" | "escalates_to" | "shares_access";
  provenance: string;
  note: string | null;
  target_type: "responsibility" | "asset";
  target_id: string;
  target_name: string;
  created_at: string;
};

export type StewardshipView = {
  dependencies: DependencyView[];
  access: { user_id: string; name: string; granted_at: string }[];
};

export type TierView = {
  criticality: Criticality;
  requires_backup: boolean;
  review_days: number;
  requires_accountable_contact: boolean;
  customised: boolean;
};

export type ChangeView = {
  id: string;
  assignment_id: string;
  change_type: "assigned" | "ended" | "extended" | "corrected";
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
  manager_person_id: string | null;
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
  asset_id: string | null;
  asset_name: string | null;
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
  assignee_user_id: string | null;
  assignee_name: string | null;
  case_id: string | null;
  decided_at: string | null;
  first_detected_at: string | null;
};

export type RiskStatus =
  "open" | "acknowledged" | "accepted" | "resolved" | "in_remediation" | "dismissed";

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

export type CaseType = "transfer" | "coverage" | "departure" | "onboarding" | "project_handover";
export type CaseStatus =
  | "draft"
  | "investigating"
  | "awaiting_input"
  | "planning"
  | "awaiting_review"
  | "ready_for_transfer"
  | "executing"
  | "verification"
  | "blocked"
  | "reopened"
  | "completed"
  | "cancelled";
export type CasePriority = "low" | "normal" | "high" | "urgent";

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
  priority: CasePriority;
  due_at: string | null;
  overdue: boolean;
  parent_case_id: string | null;
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
  decline_reason: string | null;
  declined_at: string | null;
  can_decline: boolean;
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
  priority: CasePriority;
  assignee_team_id: string | null;
  assignee_team_name: string | null;
  depends_on: string[];
  blocked_by: string[];
  needs_input_from_user_id: string | null;
  needs_input_from_name: string | null;
  completion_note: string | null;
  completion_url: string | null;
  external_provider: "github" | "linear" | null;
  external_url: string | null;
  sync_status: "not_mirrored" | "pending" | "synced" | "error" | "unlinked";
  case_title: string | null;
};

export type TaskEventView = {
  kind:
    | "comment"
    | "clarification_requested"
    | "clarification_answered"
    | "reassigned"
    | "due_changed"
    | "completed"
    | "reopened"
    | "cancelled";
  body: string | null;
  detail: Record<string, string | null>;
  actor_name: string | null;
  created_at: string;
};

export type TaskDetail = { task: TaskView; events: TaskEventView[]; can_answer: boolean };

export type ChecklistStep = {
  step: string;
  done: boolean;
  done_by: string | null;
  done_at: string | null;
};

export type CriterionView = {
  id: string;
  scope_item_id: string | null;
  criterion_type: string;
  title: string;
  mandatory: boolean;
  status: "pending" | "met" | "blocked" | "waived" | "needs_review" | "unable_to_assess";
  note: string | null;
  resolved_at: string | null;
  checklist: ChecklistStep[];
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
  | "add_blocker"
  | "update"
  | "transition"
  | "reopen"
  | "split"
  | "activate"
  | "fill_backups"
  | "comment";

export type BlockerView = {
  id: string;
  description: string;
  owner_user_id: string | null;
  owner_name: string | null;
  escalate_at: string;
  escalation_due: boolean;
  escalated_at: string | null;
  resolution: string | null;
  resolved_by_name: string | null;
  resolved_at: string | null;
  created_by_name: string | null;
  created_at: string;
};

export type StatusChangeView = {
  from_status: CaseStatus | null;
  to_status: CaseStatus;
  reason: string | null;
  outcome: string | null;
  closed_at: string | null;
  actor_name: string | null;
  changed_at: string;
};

export type CaseLink = { id: string; title: string; case_type: CaseType; status: CaseStatus };

export type ParticipantView = {
  key: string;
  kind: "user" | "person";
  subject_id: string;
  name: string;
  roles: string[];
  why: string[];
  participant_ids: string[];
};

export type SavedPage = "cases" | "responsibilities" | "assets" | "knowledge";
export type SavedViewView = {
  id: string;
  page: SavedPage;
  name: string;
  query: string;
  created_at: string;
};

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
  readiness_reasons: string[];
  allowed_actions: CaseAction[];
  scope: ScopeItemView[];
  tasks: TaskView[];
  criteria: CriterionView[];
  approvals: ApprovalView[];
  time_zone: string;
  accountable_manager_user_id: string | null;
  accountable_manager_name: string | null;
  delegate_approver_user_id: string | null;
  delegate_approver_name: string | null;
  approval_due_at: string | null;
  approval_overdue: boolean;
  project_asset_id: string | null;
  project_asset_name: string | null;
  reopen_count: number;
  blocked_from: CaseStatus | null;
  duplicate_override_reason: string | null;
  self_requested: boolean;
  activated_at: string | null;
  warnings: string[];
  transitions: CaseStatus[];
  blockers: BlockerView[];
  status_history: StatusChangeView[];
  duplicates: CaseLink[];
  parent: CaseLink | null;
  children: CaseLink[];
};

export type HistoryView = {
  occurred_at: string;
  action: string;
  actor_name: string | null;
  details: Record<string, string | number | boolean | null>;
};

export type WorkspaceRole =
  | "owner"
  | "admin"
  | "member"
  | "guest"
  | "auditor"
  | "continuity_manager"
  | "knowledge_steward"
  | "team_manager";
export type MemberType = "employee" | "contractor" | "external";

export type RoleView = { role: WorkspaceRole; description: string; permissions: string[] };

export type IdentityConflict = {
  kind: "github_login_mismatch" | "email_mismatch" | "duplicate_email" | "pending_match";
  provider: "GitHub" | "Linear" | "Directory";
  person_id: string | null;
  person_name: string | null;
  handle: string;
  detail: string;
};

export type WorkspaceMemberView = {
  user_id: string;
  name: string;
  email: string | null;
  role: WorkspaceRole;
  status: "active" | "suspended" | "removed";
  joined_at: string;
  member_type: MemberType;
  team_ids: string[];
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
  audience: "workspace" | "managers";
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

export type HandoverForMe = {
  capsule_id: string;
  case_id: string;
  case_title: string;
  status: "approved" | "acknowledged";
  version: number;
  updated_at: string;
};
export type MyWorkView = {
  handovers: HandoverForMe[];
  emergencies: CaseSummary[];
  tasks: TaskView[];
  approvals: CaseSummary[];
  attention: CaseSummary[];
  needs_input: TaskView[];
  completed: TaskView[];
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
  | "repository"
  | "service"
  | "project"
  | "process"
  | "vendor"
  | "document_collection"
  | "customer_account"
  | "infrastructure"
  | "other";
export type AssetLifecycle = "planned" | "active" | "deprecated" | "retired";

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
  criticality: Criticality | null;
  tags: string[];
  lifecycle: AssetLifecycle;
  external_source: "github" | "linear" | "notion" | "manual" | null;
  external_id: string | null;
  source_state: "available" | "unavailable";
  stewarded: boolean;
};

export type AssetLinkView = {
  id: string;
  kind: "knowledge" | "case" | "task";
  target_id: string;
  case_id: string | null;
  title: string;
  status: string;
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
  metadata: Record<string, string>;
  metadata_fields: string[];
  links: AssetLinkView[];
  dependents: AssetResponsibilityView[];
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

export type KnowledgeKind =
  | "note"
  | "link"
  | "document"
  | "procedure"
  | "context"
  | "adr"
  | "faq"
  | "postmortem"
  | "escalation_contact"
  | "onboarding_resource"
  | "project_overview";
export type KnowledgeState =
  "draft" | "verified" | "disputed" | "stale" | "expired" | "inaccessible" | "archived";

export type KnowledgeView = {
  id: string;
  responsibility_id: string;
  responsibility_name: string;
  kind: KnowledgeKind;
  title: string;
  body: string | null;
  url: string | null;
  visibility: "workspace" | "managers";
  origin: "person" | "notion" | "ai";
  status: "active" | "archived" | "withdrawn";
  author_name: string;
  created_at: string;
  updated_at: string;
  last_reviewed_at: string | null;
  last_reviewed_by_name: string | null;
  freshness: "fresh" | "stale";
  can_edit: boolean;
  state: KnowledgeState;
  review_state: "draft" | "verified" | "disputed";
  version: number;
  steward_user_id: string | null;
  steward_name: string | null;
  valid_from: string | null;
  valid_until: string | null;
  applies_to: string | null;
  decision_rationale: string | null;
  decision_approver: string | null;
  decided_at: string | null;
  superseded_by_id: string | null;
  current: boolean;
  dispute_reason: string | null;
  disputed_by_name: string | null;
  disputed_at: string | null;
  can_verify: boolean;
};

export type KnowledgeRelatedView = {
  id: string;
  title: string;
  responsibility_name: string;
  state: KnowledgeState;
  updated_at: string;
  last_reviewed_at: string | null;
};

export type KnowledgeGovernanceView = {
  versions: {
    version: number;
    kind: KnowledgeKind;
    title: string;
    body: string | null;
    url: string | null;
    change_note: string | null;
    changed_by_name: string;
    changed_at: string;
  }[];
  feedback: {
    kind: "stale" | "authoritative";
    note: string | null;
    user_name: string;
    created_at: string;
  }[];
  duplicates: KnowledgeRelatedView[];
  conflicts: KnowledgeRelatedView[];
  superseded_by: KnowledgeRelatedView | null;
};

export type KnowledgeCompareView = {
  from_version: number;
  to_version: number;
  title_changed: boolean;
  diff: string[];
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
  provider: string | null;
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
  audience: "workspace" | "managers";
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
  retention_days: number;
  updated_by_name: string | null;
  updated_at: string | null;
};

export type SearchKind =
  | "responsibility"
  | "person"
  | "team"
  | "department"
  | "asset"
  | "case"
  | "knowledge"
  | "risk"
  | "github"
  | "linear";

export type SearchHit = {
  kind: SearchKind;
  id: string;
  title: string;
  detail: string | null;
  status: string | null;
  url: string | null;
  updated_at: string | null;
};

export type SearchView = {
  query: string;
  hits: SearchHit[];
  facets: Partial<Record<SearchKind, number>>;
};

export type ExpertView = {
  person_id: string;
  name: string;
  reasons: { kind: "owns" | "wrote" | "worked_on"; text: string }[];
};

export type ProfileRef = { id: string; name: string; detail: string | null };
export type ProfileView = {
  reports_to: ProfileRef | null;
  direct_reports: ProfileRef[];
  tasks: {
    id: string;
    case_id: string;
    case_title: string;
    title: string;
    due_at: string | null;
  }[];
  knowledge: ProfileRef[];
  history: { change: string; unit: string; changed_at: string }[];
  coverage: {
    responsibilities: number;
    critical: number;
    without_backup: number;
    single_holder: number;
  } | null;
  risk_breakdown: Record<string, number>;
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

export type ResponsibilityContextView = {
  risks: {
    key: string;
    title: string;
    severity: Severity;
    status: string;
    accepted_until: string | null;
  }[];
  cases: {
    id: string;
    title: string;
    case_type: CaseType;
    status: CaseStatus;
    emergency: boolean;
    recipient_planned: boolean;
  }[];
  evidence: {
    source: "GitHub" | "Linear" | "Notion";
    label: string;
    url: string;
    detail: string | null;
  }[];
  suggestions: { source: "GitHub"; label: string; reason: string; url: string }[];
};

export type NotionPreviewView = {
  source_id: string;
  kind: "page" | "database";
  title: string;
  pages: { title: string; url: string; last_edited_at: string | null; already_imported: boolean }[];
  more: boolean;
};

// --- AI runtime (backend relay.intelligence) ---------------------------------------
export type AiAudience = "workspace" | "managers";
export type ClaimKind =
  "finding" | "decision" | "question" | "dependency" | "conflict" | "missing" | "work";
export type ClaimType = "direct_fact" | "rule" | "ai_inference" | "human_decision";
export type Confidence = "high" | "medium" | "low" | "insufficient";
export type RunState =
  | "queued"
  | "running"
  | "waiting_for_approval"
  | "completed"
  | "partial"
  | "failed"
  | "cancelled"
  | "timed_out"
  | "needs_human_review";

export type EvidenceView = {
  id: string;
  ref: string;
  source_system: "relay" | "github" | "linear" | "notion";
  source_type: string;
  title: string;
  url: string | null;
  revision: string | null;
  source_ts: string | null;
  excerpt: string;
  audience: AiAudience;
  status: "active" | "stale" | "withdrawn";
  changed: boolean;
};

export type ClaimView = {
  id: string;
  capability: string;
  kind: ClaimKind;
  claim_type: ClaimType;
  text: string;
  confidence: Confidence;
  audience: AiAudience;
  review_status: "unreviewed" | "accepted" | "rejected";
  supported: boolean;
  timeline_at: string | null;
  evidence: EvidenceView[];
};

export type RunView = {
  id: string;
  capability: string;
  case_id: string | null;
  state: RunState;
  step: number;
  steps: string[];
  ai: "on" | "off" | "not_configured";
  provider: string | null;
  model: string | null;
  key_index: number | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: string;
  duration_ms: number;
  error_code: string | null;
  partial_sources: string[];
  created_at: string;
  finished_at: string | null;
};

export type RunEventView = {
  step: string;
  level: "info" | "warning" | "error";
  code: string;
  detail: Record<string, unknown>;
  created_at: string;
};

export type RunDetail = RunView & { events: RunEventView[] };

export type ProposalType =
  | "knowledge_draft"
  | "case_finding"
  | "task"
  | "readiness_criterion"
  | "exception"
  | "handover_content"
  | "coordination_message";

export type ProposalView = {
  id: string;
  capability: string;
  type: ProposalType;
  title: string;
  detail: string;
  confidence: Confidence;
  audience: AiAudience;
  status: "pending" | "accepted" | "edited" | "rejected";
  reason: string | null;
  result_ref: string | null;
  reviewed_at: string | null;
  created_at: string;
  evidence: EvidenceView[];
};

export type AnalysisView = {
  case_id: string;
  ai_configured: boolean;
  run: RunView | null;
  claims: ClaimView[];
  proposals: ProposalView[];
  hidden_restricted: boolean;
  can_run: boolean;
  can_review: boolean;
};

export type QuestionView = {
  id: string;
  question: string;
  why: string;
  status: "open" | "answered" | "unknown" | "not_applicable" | "cannot_share";
  answer: string | null;
  answered_by: string | null;
  answered_at: string | null;
  reviewed_at: string | null;
  asked_user_id: string | null;
  asked_name: string | null;
  ai: boolean;
  can_answer: boolean;
  evidence: EvidenceView[];
};

export type InterviewView = {
  case_id: string;
  ai_configured: boolean;
  run: RunView | null;
  questions: QuestionView[];
  can_generate: boolean;
  can_review: boolean;
};

export type CapsulePoint = {
  key: string;
  text: string;
  kind: ClaimKind;
  claim_type: ClaimType;
  confidence: Confidence;
  redacted: boolean;
  changed: boolean;
  evidence: EvidenceView[];
};
export type CapsuleSection = { heading: string; points: CapsulePoint[] };
export type CapsuleOmission = { reason: string; count: number };
export type CapsuleStatus = "draft" | "approved" | "acknowledged" | "superseded";

export type CapsuleView = {
  id: string;
  case_id: string;
  case_title: string;
  recipient_user_id: string;
  recipient_name: string;
  status: CapsuleStatus;
  version: number;
  source: "rules" | "ai" | "edit";
  summary: string | null;
  sections: CapsuleSection[];
  omissions: CapsuleOmission[];
  approved_by: string | null;
  approved_at: string | null;
  acknowledged_at: string | null;
  created_at: string;
  can_edit: boolean;
  can_approve: boolean;
  can_acknowledge: boolean;
  generating: boolean;
  changed_points: number;
  changed_sources: string[];
};

export type CapsuleSummary = {
  id: string;
  recipient_user_id: string;
  recipient_name: string;
  status: CapsuleStatus;
  version: number;
  updated_at: string;
};

export type CapsuleVersionView = {
  version: number;
  source: "rules" | "ai" | "edit";
  created_by: string | null;
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
  acknowledged: boolean;
};

export type CapabilityView = {
  name: string;
  version: number;
  title: string;
  description: string;
  produces: string[];
  tools: string[];
  token_budget: number;
  timeout_seconds: number;
  enabled: boolean;
  accepted: number;
  rejected: number;
  pending: number;
};

export type AiAdminView = {
  configured: boolean;
  providers: string[];
  gemini_keys: number;
  enabled: boolean;
  monthly_token_budget: number;
  tokens_this_month: number;
  capabilities: CapabilityView[];
};

export type SourceStatus = {
  source: "GitHub" | "Linear" | "Notion";
  state: "connected" | "partial" | "not_connected";
};

export type ImpactItem = {
  scope_item_id: string;
  responsibility_id: string;
  responsibility_name: string;
  criticality: Criticality;
  role: Role;
  current_owner_name: string | null;
  recipient_name: string | null;
  state: ScopeItemView["state"];
  assets: { id: string; name: string; asset_type: string; status: string }[];
  evidence: ResponsibilityContextView["evidence"];
  risks: ResponsibilityContextView["risks"];
  knowledge: { total: number; stale: number };
};

export type ImpactView = { items: ImpactItem[]; sources: SourceStatus[] };

export type ReviewItemView = {
  id: string;
  case_id: string;
  case_title: string | null;
  subject_type: "responsibility" | "knowledge" | "source";
  subject_id: string;
  summary: string;
  audience: "case" | "workspace" | "managers";
  audience_label: string;
  decision: "pending" | "confirmed" | "corrected" | "disputed";
  note: string | null;
  decided_by_name: string | null;
  decided_at: string | null;
  can_decide: boolean;
};

export type PrivacyView = {
  notice: string;
  notice_acknowledged_at: string | null;
  excluded_sources: string[];
  sources: { source: string; state: string }[];
  reviewer_name: string | null;
  items: ReviewItemView[];
  pending: number;
  can_manage: boolean;
};

export type ExternalTargetsView = {
  github_enabled: boolean;
  linear_enabled: boolean;
  github_blocker: string | null;
  linear_blocker: string | null;
  targets: { provider: "github" | "linear"; target: string; label: string }[];
};

export type ExternalActionView = {
  id: string;
  task_id: string;
  provider: "github" | "linear";
  target_label: string;
  title: string;
  body: string;
  state: "approved" | "executing" | "succeeded" | "uncertain" | "failed";
  attempts: number;
  external_id: string | null;
  external_url: string | null;
  error: string | null;
  receipt: { recovered_existing?: boolean; [key: string]: unknown };
  approved_by_name: string | null;
  approved_at: string;
};

export type ConnectorHealth =
  | "healthy"
  | "stale"
  | "partial"
  | "attention_required"
  | "rate_limited"
  | "permission_changed"
  | "paused"
  | "revoked"
  | "failed";

export type ConnectorView = {
  provider: "github" | "linear" | "notion";
  ref: string;
  name: string;
  health: ConnectorHealth;
  advice: string;
  last_synced_at: string | null;
  last_success_at: string | null;
  failure_rate: number | null;
  runs: {
    status: "ok" | "partial" | "error" | "skipped";
    error: string | null;
    duration_ms: number;
    finished_at: string;
  }[];
};

export type MetricView = {
  key: string;
  name: string;
  definition: string;
  numerator: number;
  denominator: number;
  value: number | null;
  unit: string;
  sample_size: number;
  coverage: string;
  limitations: string;
  distribution: Record<string, number>;
};

export type MetricsView = { period_start: string; period_end: string; metrics: MetricView[] };

export type SnapshotView = MetricsView & { id: string; trigger: string; taken_at: string };

// Handover Copilot (relay.intelligence.copilot)
export type AnswerView = {
  id: string;
  question: string;
  answer: string;
  mode: "ai" | "search" | "not_found";
  confidence: Confidence | null;
  note: string | null;
  asked_by: string;
  asked_at: string;
  capsule_version: number;
  evidence: EvidenceView[];
  withdrawn_sources: number;
};

// "What if?" simulator (relay.continuity.simulation)
export type SimulationCover = "covered" | "covered_by_backup" | "uncovered";
export type SimulationHolder = { name: string; role: string; kind: "person" | "team" };
export type SimulatedResponsibility = {
  responsibility_id: string;
  name: string;
  criticality: Criticality;
  role: Role;
  cover: SimulationCover;
  covered_by: SimulationHolder | null;
  remaining_holders: SimulationHolder[];
  knowledge_total: number;
  knowledge_stale: number;
  single_holder_after: boolean;
  assets: string[];
  reasons: string[];
};
export type SimulationOpenWork = {
  source: "Relay task" | "GitHub" | "Linear";
  title: string;
  url: string | null;
  responsibility_name: string | null;
  due_at: string | null;
  due_in_window: boolean;
};
export type ExposedRisk = {
  kind: "uncovered" | "single_holder" | "undocumented" | "stale_knowledge";
  severity: Severity;
  responsibility_id: string;
  responsibility_name: string;
  detail: string;
};
export type SimulationPersonRef = { id: string; name: string; title: string | null };
export type SimulationRiskRef = {
  key: string;
  title: string;
  severity: Severity;
  status: string;
  subject: string | null;
};
export type SimulationView = {
  person: SimulationPersonRef;
  backup: SimulationPersonRef | null;
  affected_responsibilities: SimulatedResponsibility[];
  covered_by_backup: string[];
  uncovered_responsibilities: string[];
  orphaned_knowledge_count: number;
  open_work_without_cover: SimulationOpenWork[];
  open_work_total: number;
  existing_risks: SimulationRiskRef[];
  exposed_risks: ExposedRisk[];
  baseline_score: number;
  readiness_score: number;
  score_basis: string;
  backup_load: { current_responsibilities: number; would_take_over: number } | null;
  simulated_at: string;
  days: number | null;
  affected_assets: string[];
  due_in_window: number;
};
export type SimulationCandidate = {
  person: SimulationPersonRef | null;
  signals: string[];
  covered: number;
  total: number;
  critical_gaps: number;
  knowledge_gaps: number;
  remaining_risks: number;
  readiness_score: number;
  load_after: number | null;
};
export type CandidatesView = {
  person: SimulationPersonRef;
  candidates: SimulationCandidate[];
  basis: string;
};

// Project Memory Replay (relay.catalog.timeline, relay.intelligence.memory)
export type TimelineCategory =
  | "implementation"
  | "bug_fix"
  | "incident"
  | "documentation"
  | "technical_change"
  | "decision"
  | "ownership_change";
export type TimelineEvent = {
  id: string;
  occurred_at: string;
  category: TimelineCategory;
  category_basis: "label" | "title" | "record" | "default";
  title: string;
  summary: string;
  significance: Severity;
  source_system: "Relay" | "GitHub" | "Linear" | "Notion";
  source_url: string | null;
  actor: string | null;
  uncertainty_level: "factual";
  linked_events: string[];
};
export type TimelineView = {
  responsibility_id: string;
  responsibility_name: string;
  events: TimelineEvent[];
  total: number;
  counts: Record<TimelineCategory, number>;
  truncated: boolean;
  sources: SourceStatus[];
  first_at: string | null;
  last_at: string | null;
};
export type NarrativeChapter = {
  title: string;
  summary: string;
  why_it_matters: string;
  confidence: Confidence;
  uncertainty_level: "inferred";
  event_ids: string[];
  started_at: string;
  ended_at: string;
};
export type NarrativeView = {
  responsibility_id: string;
  state: "ready" | "empty" | "unavailable" | "none";
  reason: string | null;
  overview: string | null;
  overview_event_ids: string[];
  chapters: NarrativeChapter[];
  links: {
    from_event: string;
    to_event: string;
    relation: string;
    uncertainty_level: "inferred";
  }[];
  events_considered: number;
  rejected: number;
  generated_at: string;
  outdated: boolean;
  withheld: number;
};
export type HistoryAnswer = {
  question: string;
  answer: string;
  mode: "ai" | "search" | "not_found";
  confidence: Confidence | null;
  note: string | null;
  event_ids: string[];
};
