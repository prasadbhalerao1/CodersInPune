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
  revalidatePath(`/w/${workspaceId}`, "layout");
  refresh(); // re-render the current route; data is never cached
  return {};
}

export async function inviteMemberAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const email = String(fd.get("email") ?? "").trim();
  if (!email) return { error: "Enter an email address." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", "/invitations", {
      email,
      role: String(fd.get("role") ?? "member"),
    }),
  );
}

export async function revokeInvitationAction(
  workspaceId: string,
  invitationId: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/invitations/${invitationId}/revoke`),
  );
}

export async function updateMemberAction(
  workspaceId: string,
  userId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const role = fd.get("role");
  const status = fd.get("status");
  const memberType = fd.get("member_type");
  const teams = fd.getAll("team_ids").map(String);
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/members/${userId}`, {
      ...(role ? { role: String(role) } : {}),
      ...(status ? { status: String(status) } : {}),
      ...(memberType ? { member_type: String(memberType) } : {}),
      // Only team managers carry a team scope; the field is sent when the picker is shown.
      ...(fd.has("scope") ? { team_ids: teams } : {}),
    }),
  );
}
