"use server";

// WHY DEMO ACCOUNTS EXIST: Relay is a real product. Anyone can sign in with their own email
// (WorkOS) and connect their real GitHub, Linear, Notion and Slack accounts; that is the normal
// path and uses exactly the same code. Doing that during judging would be slow, and a fresh
// organisation would not yet show the edge cases (a leaver, stale knowledge, conflicts, blocked
// handovers). So, to give judges the full experience in minutes, we also ship pre-seeded
// sample data and one shared demo account per role. Nothing here is a mock or a shortcut.

import { refresh, revalidatePath } from "next/cache";

import { api, RelayApiError } from "@/lib/relay-api";

export async function switchDemoRoleAction(
  workspaceId: string,
  role: string,
): Promise<{ error?: string }> {
  try {
    await api.send(workspaceId, "PUT", "/demo-role", { role });
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  refresh();
  return {};
}
