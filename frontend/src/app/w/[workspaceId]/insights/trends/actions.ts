"use server";

import { refresh, revalidatePath } from "next/cache";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";

export async function takeSnapshotAction(
  workspaceId: string,
  days: number,
  _state: ActionState,
): Promise<ActionState> {
  try {
    await api.send(workspaceId, "POST", `/insights/snapshots?days=${days}`);
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  refresh();
  return {};
}
