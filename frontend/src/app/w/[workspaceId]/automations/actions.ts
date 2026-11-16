"use server";

import type { ActionState } from "@/lib/action-state";
import { mutate } from "@/lib/mutate";
import { api } from "@/lib/relay-api";

export async function updateAutomationAction(
  workspaceId: string,
  template: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const assignee = String(fd.get("assignee_user_id") ?? "");
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/automations/${template}`, {
      enabled: fd.get("enabled") === "on",
      action: String(fd.get("action") ?? "notify"),
      assignee_user_id: assignee || null,
    }),
  );
}

export async function runAutomationAction(
  workspaceId: string,
  template: string,
  retry: boolean,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/automations/${template}/${retry ? "retry" : "run"}`),
  );
}

export async function completeFollowUpAction(
  workspaceId: string,
  followUpId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/follow-ups/${followUpId}/complete`),
  );
}

export async function updatePolicyAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const days = Number(fd.get("knowledge_review_days"));
  if (!Number.isInteger(days) || days < 7 || days > 730) {
    return { error: "Review interval must be between 7 and 730 days." };
  }
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", "/policy", {
      critical_requires_backup: fd.get("critical_requires_backup") === "on",
      knowledge_review_days: days,
    }),
  );
}
