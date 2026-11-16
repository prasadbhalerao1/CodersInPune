"use server";

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
