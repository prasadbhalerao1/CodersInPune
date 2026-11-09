"use server";

import { refresh, revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";

const base = "/integrations/notion";

async function mutate(workspaceId: string, run: () => Promise<unknown>): Promise<ActionState> {
  try {
    await run();
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}/integrations`, "layout");
  revalidatePath(`/w/${workspaceId}/knowledge`);
  refresh(); // re-render the current route; data is never cached
  return {};
}

export async function connectNotionAction(workspaceId: string): Promise<ActionState> {
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

export async function syncNotionAction(workspaceId: string, ref: string): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `${base}/connections/${ref}/sync`),
  );
}

export async function disconnectNotionAction(
  workspaceId: string,
  ref: string,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `${base}/connections/${ref}/disconnect`),
  );
}

export async function mapNotionSourceAction(
  workspaceId: string,
  sourceId: string,
  unmap: boolean,
  _state: ActionState,
  fd?: FormData,
): Promise<ActionState> {
  const responsibilityId = unmap ? null : String(fd?.get("responsibility_id") ?? "") || null;
  const visibility = unmap ? null : String(fd?.get("visibility") ?? "") || null;
  if (!unmap && (!responsibilityId || !visibility)) {
    return { error: "Choose a responsibility and who can see it." };
  }
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PUT", `${base}/sources/${sourceId}/mapping`, {
      responsibility_id: responsibilityId,
      visibility,
    }),
  );
}
