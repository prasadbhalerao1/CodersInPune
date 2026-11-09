"use server";

import { refresh, revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";
import type { CaseStatus, CaseType, SavedPage } from "@/lib/types";

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
  refresh(); // re-render the current route; data is never cached
  return {};
}

const casePath = (caseId: string, suffix = "") => `/cases/${encodeURIComponent(caseId)}${suffix}`;

export async function createCaseAction(
  workspaceId: string,
  caseType: CaseType,
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
      priority: optional(fd, "priority"),
      due_at: optional(fd, "due_at"),
      time_zone: optional(fd, "time_zone"),
      accountable_manager_user_id: optional(fd, "accountable_manager_user_id"),
      approval_due_at: optional(fd, "approval_due_at"),
      project_asset_id: optional(fd, "project_asset_id"),
      duplicate_override_reason: optional(fd, "duplicate_override_reason"),
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
  fd?: FormData,
): Promise<ActionState> {
  const sod = fd ? optional(fd, "sod_exception_reason") : undefined;
  return mutate(workspaceId, () =>
    api.send(
      workspaceId,
      "POST",
      casePath(caseId, `/${command}`),
      sod ? { sod_exception_reason: sod } : undefined,
    ),
  );
}

export async function updateCaseDetailsAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  // Empty date fields clear the deadline; the backend reschedules reminders.
  const nullable = (key: string) => optional(fd, key) ?? null;
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", casePath(caseId), {
      priority: text(fd, "priority") || "normal",
      due_at: nullable("due_at"),
      approval_due_at: nullable("approval_due_at"),
      time_zone: text(fd, "time_zone") || "UTC",
      accountable_manager_user_id: nullable("accountable_manager_user_id"),
      delegate_approver_user_id: nullable("delegate_approver_user_id"),
    }),
  );
}

export async function transitionAction(
  workspaceId: string,
  caseId: string,
  to: CaseStatus,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, "/transition"), {
      to,
      reason: optional(fd, "reason"),
    }),
  );
}

export async function reopenCaseAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const reason = text(fd, "reason");
  if (!reason) return { error: "Say why the case is being reopened." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, "/reopen"), { reason }),
  );
}

export async function addBlockerAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const description = text(fd, "description");
  if (!description) return { error: "Describe what is blocking the case." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, "/blockers"), {
      description,
      owner_user_id: optional(fd, "owner_user_id"),
      escalate_at: optional(fd, "escalate_at"),
    }),
  );
}

export async function resolveBlockerAction(
  workspaceId: string,
  caseId: string,
  blockerId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const resolution = text(fd, "resolution");
  if (!resolution) return { error: "Say how it was resolved." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, `/blockers/${blockerId}/resolve`), {
      resolution,
    }),
  );
}

export async function declineScopeAction(
  workspaceId: string,
  caseId: string,
  itemId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const reason = text(fd, "reason");
  if (!reason) return { error: "Say why you can't take this on." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, `/scope/${itemId}/decline`), { reason }),
  );
}

export async function splitCaseAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const ids = fd.getAll("item").map(String);
  if (!ids.length) return { error: "Choose at least one responsibility to split off." };
  return mutate(workspaceId, () => api.send(workspaceId, "POST", casePath(caseId, "/split"), ids));
}

export async function addParticipantAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const [kind, id] = text(fd, "subject").split(":");
  const why = text(fd, "why");
  if (!id || !why) return { error: "Choose someone and say why they are involved." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, "/participants"), {
      user_id: kind === "user" ? id : undefined,
      person_id: kind === "person" ? id : undefined,
      role: text(fd, "role") || "contributor",
      why,
    }),
  );
}

export async function removeParticipantAction(
  workspaceId: string,
  caseId: string,
  participantId: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "DELETE", casePath(caseId, `/participants/${participantId}`)),
  );
}

export async function saveViewAction(
  workspaceId: string,
  page: SavedPage,
  query: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const name = text(fd, "name");
  if (!name) return { error: "Name the view." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", "/saved-views", { page, name, query: query || "status=open" }),
  );
}

export async function deleteViewAction(
  workspaceId: string,
  viewId: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "DELETE", `/saved-views/${encodeURIComponent(viewId)}`),
  );
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
      ...assignee(fd),
      due_at: optional(fd, "due_at"),
      scope_item_id: optional(fd, "scope_item_id"),
      priority: optional(fd, "priority"),
      depends_on: fd.getAll("depends_on").map(String).filter(Boolean),
    }),
  );
}

/** "user:<id>" or "team:<id>" from one assignee select; "" leaves it unassigned. */
function assignee(fd: FormData) {
  const [kind, id] = text(fd, "assignee").split(":");
  return {
    assignee_user_id: kind === "user" ? id : null,
    assignee_team_id: kind === "team" ? id : null,
  };
}

export async function setTaskStatusAction(
  workspaceId: string,
  caseId: string,
  taskId: string,
  status: "open" | "done" | "cancelled",
  _state: ActionState,
  fd?: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", casePath(caseId, `/tasks/${taskId}`), {
      status,
      completion_note: fd ? optional(fd, "completion_note") : undefined,
      completion_url: fd ? optional(fd, "completion_url") : undefined,
      reason: fd ? optional(fd, "reason") : undefined,
    }),
  );
}

export async function changeTaskAction(
  workspaceId: string,
  caseId: string,
  taskId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, `/tasks/${taskId}/change`), {
      ...assignee(fd),
      due_at: optional(fd, "due_at") ?? null,
      priority: optional(fd, "priority"),
      reason: optional(fd, "reason"),
    }),
  );
}

export async function taskMessageAction(
  workspaceId: string,
  caseId: string,
  taskId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const body = text(fd, "body");
  if (!body) return { error: "Write something first." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, `/tasks/${taskId}/messages`), {
      body,
      kind: text(fd, "kind") === "clarification" ? "clarification" : "comment",
      ask_user_id: optional(fd, "ask_user_id"),
    }),
  );
}

export async function bulkTasksAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const ids = fd.getAll("task").map(String);
  if (!ids.length) return { error: "Select tasks first." };
  let skipped = 0;
  const result = await mutate(workspaceId, async () => {
    const r = await api.send<{ done: string[]; skipped: Record<string, string> }>(
      workspaceId,
      "POST",
      casePath(caseId, "/tasks/bulk"),
      {
        task_ids: ids,
        action: text(fd, "action") === "reassign" ? "reassign" : "complete",
        assignee_user_id: optional(fd, "bulk_assignee"),
        reason: optional(fd, "reason"),
      },
    );
    skipped = Object.keys(r.skipped).length;
  });
  if (result.error) return result;
  return skipped
    ? { error: `${skipped} task(s) were left alone: they wait on other tasks or are closed.` }
    : {};
}

export async function setStepAction(
  workspaceId: string,
  caseId: string,
  criterionId: string,
  index: number,
  done: boolean,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", casePath(caseId, `/criteria/${criterionId}/steps/${index}`), {
      done,
    }),
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
      checklist:
        text(fd, "criterion_type") === "rehearsal"
          ? text(fd, "checklist")
              .split("\n")
              .map((line) => line.trim())
              .filter(Boolean)
          : [],
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

export async function addCommentAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const body = text(fd, "body");
  if (!body) return { error: "Write something first." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, "/comments"), {
      body,
      mention_user_ids: [...new Set(fd.getAll("mention_user_ids").map(String))],
    }),
  );
}

export async function setEmergencyAction(
  workspaceId: string,
  caseId: string,
  emergency: boolean,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const reason = optional(fd, "reason");
  if (emergency && !reason) return { error: "Say why this is an emergency." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", casePath(caseId, "/emergency"), { emergency, reason }),
  );
}
