"use server";

import { revalidatePath } from "next/cache";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";

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
