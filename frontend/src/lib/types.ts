// Mirrors the Relay API response models (backend `*View` classes) field-for-field.

export type Criticality = "critical" | "high" | "standard" | "low";
export type Role = "primary" | "co_owner" | "backup";
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

export type MemberView = { person_id: string; display_name: string };

export type TeamView = {
  id: string;
  name: string;
  description: string | null;
  status: "active" | "archived";
  created_at: string;
  members: MemberView[];
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
