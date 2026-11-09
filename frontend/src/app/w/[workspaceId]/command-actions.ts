"use server";

import { refresh, revalidatePath } from "next/cache";

import { api, RelayApiError } from "@/lib/relay-api";
import type { SearchView } from "@/lib/types";

export async function searchAction(workspaceId: string, q: string): Promise<SearchView> {
  try {
    return await api.search(workspaceId, q);
  } catch (error) {
    if (error instanceof RelayApiError) return { query: q, hits: [] };
    throw error;
  }
}

export type QuickCreateKind = "person" | "team" | "department" | "asset";
export type QuickCreateResult = { id?: string; error?: string };

const PATH: Record<QuickCreateKind, string> = {
  person: "/people",
  team: "/teams",
  department: "/departments",
  asset: "/assets",
};

const value = (fd: FormData, key: string) => {
  const v = String(fd.get(key) ?? "").trim();
  return v || undefined;
};

/** Quick create from the command menu: same API, validation and permissions as the full forms. */
export async function quickCreateAction(
  workspaceId: string,
  kind: QuickCreateKind,
  fd: FormData,
): Promise<QuickCreateResult> {
  const body =
    kind === "person"
      ? {
          display_name: value(fd, "name"),
          email: value(fd, "email"),
          title: value(fd, "title"),
        }
      : kind === "asset"
        ? { name: value(fd, "name"), asset_type: value(fd, "asset_type"), url: value(fd, "url") }
        : { name: value(fd, "name") };
  try {
    const created = await api.send<{ id: string }>(workspaceId, "POST", PATH[kind], body);
    revalidatePath(`/w/${workspaceId}`, "layout");
    refresh();
    return { id: created.id };
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
}
