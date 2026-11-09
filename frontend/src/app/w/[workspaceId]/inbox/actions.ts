"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";

export async function markAllReadAction(workspaceId: string): Promise<ActionState> {
  try {
    await api.send(workspaceId, "POST", "/notifications/read", {});
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  return {};
}

/** Opening a notification marks it read, then goes to its case or responsibility. */
export async function openNotificationAction(
  workspaceId: string,
  notificationId: string,
  target: string,
): Promise<ActionState> {
  try {
    await api.send(workspaceId, "POST", "/notifications/read", { ids: [notificationId] });
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  redirect(`/w/${workspaceId}/${target}`);
}
