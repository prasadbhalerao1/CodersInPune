"use server";

import { revalidatePath } from "next/cache";
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
  return {};
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
