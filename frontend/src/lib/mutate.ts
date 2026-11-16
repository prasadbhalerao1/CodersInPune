import "server-only";

import { refresh, revalidatePath } from "next/cache";

import type { ActionState } from "@/lib/action-state";
import { RelayApiError } from "@/lib/relay-api";

/**
 * Run a server action's API call and turn API errors into form state. On success, revalidate
 * the given workspace sections (default: the whole workspace) and re-render the current route.
 */
export async function mutate(
  workspaceId: string,
  run: () => Promise<unknown>,
  sections: readonly string[] = [""],
): Promise<ActionState> {
  try {
    await run();
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  for (const section of sections) revalidatePath(`/w/${workspaceId}${section}`, "layout");
  refresh(); // data is never cached
  return {};
}

/** `mutate` that only revalidates some sections, e.g. `mutateIn("/integrations")`. */
export const mutateIn =
  (...sections: string[]) =>
  (workspaceId: string, run: () => Promise<unknown>) =>
    mutate(workspaceId, run, sections);
