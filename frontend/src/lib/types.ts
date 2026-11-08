// Mirrors the Relay API response models (backend `*View` classes) field-for-field.

export type Criticality = "critical" | "high" | "standard" | "low";
export type Role = "primary" | "co_owner" | "backup" | "temporary";
export type Severity = "high" | "medium" | "low";

export type WorkspaceView = { id: string; name: string; role: string };

export type AssigneeView = { type: "person" | "team"; id: string; name: string; status: string };

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
  status: "active" | "archived";
  created_at: string;
};

export type TeamMemberView = { person_id: string; display_name: string };

export type TeamView = {
  id: string;
  name: string;
  description: string | null;
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
  | "add_criterion";

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

export type WorkspaceMemberView = { user_id: string; name: string; role: string };

export type MyWorkView = { tasks: TaskView[]; approvals: CaseSummary[]; attention: CaseSummary[] };
