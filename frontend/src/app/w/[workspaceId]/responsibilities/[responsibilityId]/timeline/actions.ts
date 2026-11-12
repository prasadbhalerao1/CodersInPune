"use server";

import { api, RelayApiError } from "@/lib/relay-api";
import type { HistoryAnswer, NarrativeView } from "@/lib/types";

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

export type AskHistoryState = { answer?: HistoryAnswer; error?: string };

export async function askHistoryAction(
  workspaceId: string,
  responsibilityId: string,
  question: string,
): Promise<AskHistoryState> {
  try {
    return { answer: await api.askHistory(workspaceId, responsibilityId, question) };
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
}
