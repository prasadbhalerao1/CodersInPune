"use server";

import { idempotencyKey, type ActionState } from "@/lib/action-state";

import { refresh, revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { api, RelayApiError } from "@/lib/relay-api";
import type { MeetingDetail } from "@/lib/types";

const text = (fd: FormData, name: string) => String(fd.get(name) ?? "").trim();

export async function createMeetingAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const date = text(fd, "held_at");
  let made: MeetingDetail;
  try {
    made = await api.send<MeetingDetail>(
      workspaceId,
      "POST",
      "/meetings",
      {
        title: text(fd, "title"),
        transcript: text(fd, "transcript"),
        held_at: date ? new Date(`${date}T10:00:00Z`).toISOString() : undefined,
        responsibility_id: text(fd, "responsibility_id") || undefined,
        case_id: text(fd, "case_id") || undefined,
      },
      idempotencyKey(fd),
    );
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}/meetings`);
  redirect(`/w/${workspaceId}/meetings/${made.id}`);
}

async function mutate(workspaceId: string, run: () => Promise<unknown>): Promise<ActionState> {
  try {
    await run();
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  refresh();
  return {};
}

export async function reviewMeetingItemAction(
  workspaceId: string,
  itemId: string,
  verb: "accept" | "dismiss",
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/meeting-items/${itemId}/${verb}`),
  );
}

export async function reextractMeetingAction(
  workspaceId: string,
  meetingId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () => api.send(workspaceId, "POST", `/meetings/${meetingId}/extract`));
}
