"use server";

import type { ActionState } from "@/lib/action-state";
import { mutate } from "@/lib/mutate";
import { api } from "@/lib/relay-api";

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
