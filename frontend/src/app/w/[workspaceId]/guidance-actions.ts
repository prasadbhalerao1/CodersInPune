"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/relay-api";
import type { GuidanceUpdate } from "@/lib/types";

// Guidance changes are small and never block the page: a failure leaves the tour usable.
export async function updateGuidanceAction(
  workspaceId: string,
  body: GuidanceUpdate,
): Promise<boolean> {
  try {
    await api.updateGuidance(workspaceId, body);
  } catch {
    return false;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  return true;
}
