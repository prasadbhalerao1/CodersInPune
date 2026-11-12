"use server";

import { refresh, revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";

const base = "/integrations/linear";

async function mutate(workspaceId: string, run: () => Promise<unknown>): Promise<ActionState> {
  try {
    await run();
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}/integrations`, "layout");
  refresh(); // re-render the current route; data is never cached
  return {};
}

export async function connectLinearAction(workspaceId: string): Promise<ActionState> {
  let url = "";
  try {
    url = (await api.send<{ authorize_url: string }>(workspaceId, "POST", `${base}/connect`))
      .authorize_url;
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  redirect(url);
}

export async function syncLinearAction(workspaceId: string, ref: string): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `${base}/connections/${ref}/sync`),
  );
}

export async function disconnectLinearAction(
  workspaceId: string,
  ref: string,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `${base}/connections/${ref}/disconnect`),
  );
}

export async function linkProjectAction(
  workspaceId: string,
  projectId: string,
  action: "link" | "create" | "unlink",
  _state: ActionState,
  fd?: FormData,
): Promise<ActionState> {
  const responsibilityId = fd ? String(fd.get("responsibility_id") ?? "") || undefined : undefined;
  const audience = fd?.get("audience") === "workspace" ? "workspace" : "managers";
  if (action === "link" && !responsibilityId) return { error: "Choose a responsibility." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `${base}/projects/${projectId}/link`, {
      action,
      responsibility_id: responsibilityId,
      audience,
    }),
  );
}

export async function decideLinearIdentityAction(
  workspaceId: string,
  identityId: string,
  action: "link" | "unlink" | "dismiss",
  _state: ActionState,
  fd?: FormData,
): Promise<ActionState> {
  const personId = fd ? String(fd.get("person_id") ?? "") || undefined : undefined;
  if (action === "link" && !personId) return { error: "Choose a person." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `${base}/identities/${identityId}/decision`, {
      action,
      person_id: personId,
    }),
  );
}
