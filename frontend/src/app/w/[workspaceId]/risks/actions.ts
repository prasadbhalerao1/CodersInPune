"use server";

import { revalidatePath } from "next/cache";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";

export async function decideRiskAction(
  workspaceId: string,
  key: string,
  action: "acknowledge" | "accept" | "reopen",
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const note = String(fd.get("note") ?? "").trim() || undefined;
  const day = String(fd.get("accepted_until") ?? "").trim();
  // A date input has no time zone; the acceptance lasts to the end of that day (UTC).
  const until = /^\d{4}-\d{2}-\d{2}$/.test(day) ? `${day}T23:59:59Z` : undefined;
  if (action === "accept" && (!note || !until)) {
    return { error: "Give a reason and the date the acceptance ends." };
  }
  try {
    await api.send(workspaceId, "POST", "/risks/decision", {
      key,
      action,
      note,
      accepted_until: until,
    });
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  return {};
}
