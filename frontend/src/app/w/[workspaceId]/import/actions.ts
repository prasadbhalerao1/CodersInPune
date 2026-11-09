"use server";

import { refresh, revalidatePath } from "next/cache";

import { api, RelayApiError } from "@/lib/relay-api";
import type { ImportKind, ImportResultView } from "@/lib/types";

export type ImportState = { error?: string; result?: ImportResultView };

const KINDS: ImportKind[] = ["people", "responsibilities", "assignments"];
const MAX_BYTES = 512_000;

/** One action for both steps: `step=preview` validates only, `step=commit` writes. */
export async function importCsvAction(
  workspaceId: string,
  _state: ImportState,
  fd: FormData,
): Promise<ImportState> {
  const kind = String(fd.get("kind") ?? "") as ImportKind;
  const step = fd.get("step") === "commit" ? "commit" : "preview";
  const csv = String(fd.get("csv") ?? "");
  if (!KINDS.includes(kind)) return { error: "Choose what you are importing." };
  if (!csv.trim()) return { error: "Choose a CSV file." };
  if (csv.length > MAX_BYTES) return { error: "The file is larger than 500 KB. Split it up." };
  try {
    const result = await api.send<ImportResultView>(workspaceId, "POST", `/imports/${step}`, {
      kind,
      csv,
    });
    if (step === "commit") {
      revalidatePath(`/w/${workspaceId}`, "layout");
      refresh();
    }
    return { result };
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
}
