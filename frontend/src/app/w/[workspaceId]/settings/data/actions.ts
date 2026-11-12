"use server";

import { refresh, revalidatePath } from "next/cache";

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
  refresh();
  return {};
}

export async function setRetentionAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const days = Number(fd.get("retention_days"));
  if (!Number.isInteger(days) || days < 30 || days > 3650) {
    return { error: "Keep records for 30 to 3650 days." };
  }
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", "/policy", { retention_days: days }),
  );
}

export async function applyRetentionAction(
  workspaceId: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () => api.send(workspaceId, "POST", "/retention/apply"));
}

export async function transferOwnershipAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const userId = String(fd.get("user_id") ?? "");
  if (!userId) return { error: "Choose the new owner." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", "/ownership/transfer", { user_id: userId }),
  );
}

export async function scheduleDeletionAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const name = String(fd.get("confirm_name") ?? "").trim();
  if (!name) return { error: "Type the workspace name to confirm." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", "/deletion", { confirm_name: name }),
  );
}

export async function cancelDeletionAction(
  workspaceId: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () => api.send(workspaceId, "DELETE", "/deletion"));
}
