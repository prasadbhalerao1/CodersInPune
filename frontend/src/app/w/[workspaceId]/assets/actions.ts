"use server";

import { refresh, revalidatePath } from "next/cache";

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
  refresh(); // re-render the current route; data is never cached
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
      criticality: optional(fd, "criticality"),
      tags: tags(fd),
    }),
  );
}

const tags = (fd: FormData) =>
  text(fd, "tags")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);

export async function updateAssetAction(
  workspaceId: string,
  assetId: string,
  fields: string[],
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  // Only the fields this asset type defines are sent; the backend rejects others.
  const metadata = Object.fromEntries(fields.map((f) => [f, text(fd, `meta_${f}`)]));
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/assets/${assetId}`, {
      criticality: optional(fd, "criticality") ?? null,
      lifecycle: text(fd, "lifecycle") || "active",
      tags: tags(fd),
      external_source: optional(fd, "external_source") ?? null,
      external_id: text(fd, "external_id"),
      source_state: text(fd, "source_state") || "available",
      metadata,
    }),
  );
}

export async function linkAssetTargetAction(
  workspaceId: string,
  assetId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const [kind, id] = text(fd, "target").split(":");
  if (!id) return { error: "Choose what to link." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/assets/${assetId}/links`, {
      knowledge_item_id: kind === "knowledge" ? id : undefined,
      case_id: kind === "case" ? id : undefined,
    }),
  );
}

export async function unlinkAssetTargetAction(
  workspaceId: string,
  assetId: string,
  linkId: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "DELETE", `/assets/${assetId}/links/${linkId}`),
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
