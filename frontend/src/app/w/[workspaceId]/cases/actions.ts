"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";

// Thin wrappers over the case API. The backend enforces lifecycle, permissions and
// approvals; these only translate form data and surface API errors to the form.

const text = (fd: FormData, key: string) => String(fd.get(key) ?? "").trim();
const optional = (fd: FormData, key: string) => text(fd, key) || undefined;

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

const casePath = (caseId: string, suffix = "") => `/cases/${encodeURIComponent(caseId)}${suffix}`;

export async function createCaseAction(
  workspaceId: string,
  caseType: "transfer" | "coverage" | "departure",
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  let id = "";
  const result = await mutate(workspaceId, async () => {
    const created = await api.send<{ id: string }>(workspaceId, "POST", "/cases", {
      case_type: caseType,
      title: text(fd, "title"),
      reason: optional(fd, "reason"),
      affected_person_id: optional(fd, "affected_person_id"),
      starts_at: optional(fd, "starts_at") ?? new Date().toISOString(),
      ends_at: caseType === "coverage" ? optional(fd, "ends_at") : undefined,
    });
    id = created.id;
  });
  if (result.error) return result;
  redirect(`/w/${workspaceId}/cases/${id}`);
}

export async function caseCommandAction(
  workspaceId: string,
  caseId: string,
  command: "submit" | "execute" | "complete" | "cancel",
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () => api.send(workspaceId, "POST", casePath(caseId, `/${command}`)));
}

export async function decideAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, "/decisions"), {
      decision: text(fd, "decision") || "approved",
      comment: optional(fd, "comment"),
      sod_exception_reason: optional(fd, "sod_exception_reason"),
    }),
  );
}

export async function extendAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const endsAt = optional(fd, "ends_at");
  if (!endsAt) return { error: "Choose the new end date." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, "/extend"), { ends_at: endsAt }),
  );
}

export async function addScopeAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const responsibilityId = text(fd, "responsibility_id");
  if (!responsibilityId) return { error: "Choose a responsibility." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, "/scope"), {
      responsibility_id: responsibilityId,
      role: text(fd, "role") || "primary",
    }),
  );
}

export async function updateScopeAction(
  workspaceId: string,
  caseId: string,
  itemId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const [kind, id] = text(fd, "recipient").split(":");
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", casePath(caseId, `/scope/${itemId}`), {
      recipient_person_id: kind === "person" ? id : null,
      recipient_team_id: kind === "team" ? id : null,
      handover_notes: text(fd, "handover_notes"),
      exception_reason: text(fd, "exception_reason"),
    }),
  );
}

export async function removeScopeAction(
  workspaceId: string,
  caseId: string,
  itemId: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "DELETE", casePath(caseId, `/scope/${itemId}`)),
  );
}

export async function addTaskAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, "/tasks"), {
      title: text(fd, "title"),
      assignee_user_id: optional(fd, "assignee_user_id"),
      due_at: optional(fd, "due_at"),
      scope_item_id: optional(fd, "scope_item_id"),
    }),
  );
}

export async function setTaskStatusAction(
  workspaceId: string,
  caseId: string,
  taskId: string,
  status: "open" | "done",
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", casePath(caseId, `/tasks/${taskId}`), { status }),
  );
}

export async function addCriterionAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, "/criteria"), {
      criterion_type: text(fd, "criterion_type"),
      title: text(fd, "title"),
      mandatory: fd.get("mandatory") === "on",
    }),
  );
}

export async function setCriterionStatusAction(
  workspaceId: string,
  caseId: string,
  criterionId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", casePath(caseId, `/criteria/${criterionId}`), {
      status: text(fd, "status"),
      note: optional(fd, "note"),
    }),
  );
}
