"use server";

import { revalidatePath } from "next/cache";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";

const text = (fd: FormData, key: string) => String(fd.get(key) ?? "").trim();
const optional = (fd: FormData, key: string) => text(fd, key) || undefined;

async function mutate(workspaceId: string, run: () => Promise<unknown>): Promise<ActionState> {
  try {
    await run();
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  return {};
}

export async function createAssetAction(
  workspaceId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", "/assets", {
      name: text(fd, "name"),
      asset_type: text(fd, "asset_type"),
      url: optional(fd, "url"),
      description: optional(fd, "description"),
    }),
  );
}

export async function setAssetStatusAction(
  workspaceId: string,
  assetId: string,
  status: "active" | "archived",
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/assets/${assetId}`, { status }),
  );
}

export async function linkAssetAction(
  workspaceId: string,
  responsibilityId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const assetId = text(fd, "asset_id");
  if (!assetId) return { error: "Choose an asset." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/responsibilities/${responsibilityId}/assets`, {
      asset_id: assetId,
      relationship: text(fd, "relationship") || "stewards",
    }),
  );
}

export async function unlinkAssetAction(
  workspaceId: string,
  responsibilityId: string,
  assetId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "DELETE", `/responsibilities/${responsibilityId}/assets/${assetId}`),
  );
}
