"use server";

import { api, RelayApiError } from "@/lib/relay-api";
import type { RehearsalGrade } from "@/lib/types";

export async function gradeRehearsalAction(
  workspaceId: string,
  capsuleId: string,
  drillId: string,
  answer: string,
): Promise<{ grade?: RehearsalGrade; error?: string }> {
  try {
    const grade = await api.send<RehearsalGrade>(
      workspaceId,
      "POST",
      `/ai/capsules/${capsuleId}/rehearsal`,
      { drill_id: drillId, answer },
    );
    return { grade };
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
}
