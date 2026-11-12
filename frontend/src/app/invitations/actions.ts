"use server";

import { redirect } from "next/navigation";

import type { ActionState } from "@/lib/action-state";
import { RelayApiError, relayFetch } from "@/lib/relay-api";

export async function acceptInvitationAction(
  invitationId: string,
  _state: ActionState,
): Promise<ActionState> {
  let workspaceId: string;
  try {
    const result = await relayFetch<{ workspace_id: string }>(
      `/me/invitations/${encodeURIComponent(invitationId)}/accept`,
      { method: "POST" },
    );
    workspaceId = result.workspace_id;
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  redirect(`/w/${workspaceId}`);
}
