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

export async function connectSlackAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PUT", "/integrations/slack", {
      webhook_url: String(fd.get("webhook_url") ?? "").trim(),
      channel: String(fd.get("channel") ?? "").trim(),
    }),
  );
}

export async function disconnectSlackAction(workspaceId: string): Promise<ActionState> {
  return mutate(workspaceId, () => api.send(workspaceId, "DELETE", "/integrations/slack"));
}

export async function shareMeetingToSlackAction(
  workspaceId: string,
  meetingId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () => api.send(workspaceId, "POST", `/meetings/${meetingId}/slack`));
}
