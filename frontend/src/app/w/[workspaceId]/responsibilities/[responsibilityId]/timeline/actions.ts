"use server";

import { api, RelayApiError } from "@/lib/relay-api";
import type { NarrativeView } from "@/lib/types";

export type NarrateState = { narrative?: NarrativeView; error?: string };

export async function narrateTimelineAction(
  workspaceId: string,
  responsibilityId: string,
): Promise<NarrateState> {
  try {
    return { narrative: await api.narrateTimeline(workspaceId, responsibilityId) };
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
}
