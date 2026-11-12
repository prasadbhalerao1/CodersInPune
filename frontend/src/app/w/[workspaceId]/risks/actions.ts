"use server";

import { refresh, revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";
import type { RiskView } from "@/lib/types";

export async function decideRiskAction(
  workspaceId: string,
  key: string,
  action: "acknowledge" | "accept" | "reopen" | "remediate" | "dismiss",
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
  if (action === "dismiss" && !note) return { error: "Say why the risk is dismissed." };
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
  refresh(); // re-render the current route; data is never cached
  return {};
}

export async function assignRiskAction(
  workspaceId: string,
  key: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const userId = String(fd.get("user_id") ?? "");
  try {
    await api.send(workspaceId, "POST", "/risks/assign", { key, user_id: userId || null });
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  refresh();
  return {};
}

export async function openRiskCaseAction(
  workspaceId: string,
  key: string,
  _state: ActionState,
): Promise<ActionState> {
  let risk: RiskView;
  try {
    risk = await api.send<RiskView>(workspaceId, "POST", "/risks/case", { key });
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  redirect(`/w/${workspaceId}/cases/${risk.case_id}`);
}
