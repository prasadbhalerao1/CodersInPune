"use server";

import type { ActionState } from "@/lib/action-state";
import { mutate } from "@/lib/mutate";
import { api } from "@/lib/relay-api";

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
