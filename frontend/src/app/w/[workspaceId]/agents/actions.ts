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
  revalidatePath(`/w/${workspaceId}/agents`);
  refresh();
  return {};
}

export async function setAiEnabledAction(
  workspaceId: string,
  enabled: boolean,
): Promise<ActionState> {
  return mutate(workspaceId, () => api.send(workspaceId, "PATCH", "/ai", { enabled }));
}

export async function setBudgetAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const budget = Number(fd.get("monthly_token_budget"));
  if (!Number.isInteger(budget) || budget < 0) return { error: "Enter a whole number of tokens." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", "/ai", { monthly_token_budget: budget }),
  );
}

export async function setCapabilityAction(
  workspaceId: string,
  name: string,
  enabled: boolean,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/ai/capabilities/${name}`, { enabled }),
  );
}
