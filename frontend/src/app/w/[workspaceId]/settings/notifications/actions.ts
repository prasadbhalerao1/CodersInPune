"use server";

import { refresh, revalidatePath } from "next/cache";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";
import type { EmailCategory } from "@/lib/types";

const CATEGORIES: EmailCategory[] = ["tasks", "reminders", "approvals", "mentions", "case_updates"];

async function mutate(workspaceId: string, run: () => Promise<unknown>): Promise<ActionState> {
  try {
    await run();
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}/settings`, "layout");
  refresh(); // re-render the current route; data is never cached
  return {};
}

export async function savePreferencesAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const on = new Set(fd.getAll("enabled").map(String));
  const preferences = Object.fromEntries(CATEGORIES.map((c) => [c, on.has(c)]));
  const result = await mutate(workspaceId, () =>
    api.send(workspaceId, "PUT", "/notifications/preferences", { preferences }),
  );
  return result.error ? result : { ...result, error: undefined };
}

export async function retryEmailAction(
  workspaceId: string,
  deliveryId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/email/deliveries/${deliveryId}/retry`),
  );
}
