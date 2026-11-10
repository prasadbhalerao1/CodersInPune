"use server";

import { refresh, revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";

// Every action re-validates input server-side and relies on the API for authorization;
// the UI hiding a control is never the security boundary.

const text = (fd: FormData, key: string) => String(fd.get(key) ?? "").trim();
const optional = (fd: FormData, key: string) => text(fd, key) || undefined;

function assignee(fd: FormData): { person_id?: string; team_id?: string } {
  const [kind, id] = text(fd, "assignee").split(":");
  if (kind === "person" && id) return { person_id: id };
  if (kind === "team" && id) return { team_id: id };
  throw new RelayApiError(422, "assignee_required", "Choose a person or team.");
}

async function mutate(workspaceId: string, run: () => Promise<unknown>): Promise<ActionState> {
  try {
    await run();
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  refresh(); // re-render the current route; data is never cached
  return {};
}

/** Governance fields shared by create and edit; one line per procedure/prerequisite. */
function stewardshipFields(fd: FormData) {
  const lines = (key: string) =>
    text(fd, key)
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
  const days = text(fd, "review_cadence_days");
  return {
    restricted: fd.get("restricted") === "on",
    needs_verification: fd.get("needs_verification") === "on",
    type_id: optional(fd, "type_id") ?? null,
    escalation_path: text(fd, "escalation_path"),
    escalation_contact: text(fd, "escalation_contact"),
    review_cadence_days: days ? Number(days) : null,
    procedures: lines("procedures"),
    access_prerequisites: lines("access_prerequisites"),
    accountable_person_id: optional(fd, "accountable_person_id") ?? null,
  };
}

export async function createResponsibilityAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  let id = "";
  const result = await mutate(workspaceId, async () => {
    const created = await api.send<{ id: string }>(workspaceId, "POST", "/responsibilities", {
      name: text(fd, "name"),
      description: optional(fd, "description"),
      category: optional(fd, "category"),
      criticality: text(fd, "criticality") || "standard",
      ...stewardshipFields(fd),
    });
    id = created.id;
  });
  if (result.error) return result;
  redirect(`/w/${workspaceId}/responsibilities/${id}`);
}

export async function updateResponsibilityAction(
  workspaceId: string,
  responsibilityId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const result = await mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/responsibilities/${responsibilityId}`, {
      version: Number(text(fd, "version")),
      name: text(fd, "name"),
      description: text(fd, "description"),
      category: text(fd, "category"),
      criticality: text(fd, "criticality"),
      ...stewardshipFields(fd),
    }),
  );
  if (result.error) return result;
  redirect(`/w/${workspaceId}/responsibilities/${responsibilityId}`);
}

export async function setResponsibilityStatusAction(
  workspaceId: string,
  responsibilityId: string,
  target: "archive" | "restore",
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/responsibilities/${responsibilityId}/${target}`),
  );
}

export async function assignOwnerAction(
  workspaceId: string,
  responsibilityId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/responsibilities/${responsibilityId}/assignments`, {
      role: text(fd, "role"),
      ...assignee(fd),
      starts_at: optional(fd, "starts_at"),
      reason: optional(fd, "reason"),
    }),
  );
}

export async function replacePrimaryAction(
  workspaceId: string,
  responsibilityId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/responsibilities/${responsibilityId}/primary`, {
      ...assignee(fd),
      effective_at: optional(fd, "effective_at"),
      reason: optional(fd, "reason"),
    }),
  );
}

export async function endAssignmentAction(
  workspaceId: string,
  responsibilityId: string,
  assignmentId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(
      workspaceId,
      "POST",
      `/responsibilities/${responsibilityId}/assignments/${assignmentId}/end`,
      { reason: optional(fd, "reason") },
    ),
  );
}

export async function createPersonAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", "/people", {
      display_name: text(fd, "display_name"),
      email: optional(fd, "email"),
      title: optional(fd, "title"),
      github_login: optional(fd, "github_login"),
      department_id: optional(fd, "department_id"),
    }),
  );
}

export async function setPersonStatusAction(
  workspaceId: string,
  personId: string,
  status: "active" | "archived",
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/people/${personId}`, { status }),
  );
}

export async function createTeamAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", "/teams", {
      name: text(fd, "name"),
      description: optional(fd, "description"),
      github_slug: optional(fd, "github_slug"),
      department_id: optional(fd, "department_id"),
    }),
  );
}

export async function addTeamMemberAction(
  workspaceId: string,
  teamId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const personId = text(fd, "person_id");
  if (!personId) return { error: "Choose a person." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PUT", `/teams/${teamId}/members/${personId}`),
  );
}

export async function removeTeamMemberAction(
  workspaceId: string,
  teamId: string,
  personId: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "DELETE", `/teams/${teamId}/members/${personId}`),
  );
}

export async function createDepartmentAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", "/departments", {
      name: text(fd, "name"),
      description: optional(fd, "description"),
    }),
  );
}

export async function setDepartmentStatusAction(
  workspaceId: string,
  departmentId: string,
  status: "active" | "archived",
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/departments/${departmentId}`, { status }),
  );
}

export async function setDepartmentAction(
  workspaceId: string,
  kind: "people" | "teams",
  id: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/${kind}/${id}`, {
      department_id: optional(fd, "department_id") ?? null,
    }),
  );
}

export async function createResponsibilityTypeAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const days = text(fd, "review_cadence_days");
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", "/responsibilities/types", {
      name: text(fd, "name"),
      description: optional(fd, "description"),
      review_cadence_days: days ? Number(days) : null,
    }),
  );
}

export async function reviewResponsibilityAction(
  workspaceId: string,
  responsibilityId: string,
  verified: boolean,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(
      workspaceId,
      "POST",
      `/responsibilities/${responsibilityId}/review?verified=${verified}`,
    ),
  );
}

export async function addDependencyAction(
  workspaceId: string,
  responsibilityId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const [kind, id] = text(fd, "target").split(":");
  if (!id) return { error: "Choose what it depends on." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/responsibilities/${responsibilityId}/dependencies`, {
      depends_on_responsibility_id: kind === "responsibility" ? id : undefined,
      depends_on_asset_id: kind === "asset" ? id : undefined,
      relationship: text(fd, "relationship") || "depends_on",
      note: optional(fd, "note"),
    }),
  );
}

export async function removeDependencyAction(
  workspaceId: string,
  responsibilityId: string,
  dependencyId: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(
      workspaceId,
      "DELETE",
      `/responsibilities/${responsibilityId}/dependencies/${dependencyId}`,
    ),
  );
}

export async function grantAccessAction(
  workspaceId: string,
  responsibilityId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const userId = text(fd, "user_id");
  if (!userId) return { error: "Choose a member." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/responsibilities/${responsibilityId}/access`, {
      user_id: userId,
    }),
  );
}

export async function revokeAccessAction(
  workspaceId: string,
  responsibilityId: string,
  userId: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "DELETE", `/responsibilities/${responsibilityId}/access/${userId}`),
  );
}

export async function correctAssignmentAction(
  workspaceId: string,
  responsibilityId: string,
  assignmentId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const reason = text(fd, "reason");
  const from = optional(fd, "valid_from");
  if (!reason || !from) return { error: "Give the corrected start and a reason." };
  return mutate(workspaceId, () =>
    api.send(
      workspaceId,
      "POST",
      `/responsibilities/${responsibilityId}/assignments/${assignmentId}/correct`,
      { valid_from: from, valid_to: optional(fd, "valid_to") ?? null, reason },
    ),
  );
}

export async function updateTierAction(
  workspaceId: string,
  criticality: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PUT", `/policy/tiers/${criticality}`, {
      requires_backup: fd.get("requires_backup") === "on",
      review_days: Number(text(fd, "review_days")),
      requires_accountable_contact: fd.get("requires_accountable_contact") === "on",
    }),
  );
}
