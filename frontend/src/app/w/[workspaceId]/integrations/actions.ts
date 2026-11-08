"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";

const gh = "/integrations/github";

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

export async function connectGitHubAction(
  workspaceId: string,
  _state: ActionState,
): Promise<ActionState> {
  let url = "";
  const result = await mutate(workspaceId, async () => {
    url = (await api.send<{ install_url: string }>(workspaceId, "POST", `${gh}/connect`))
      .install_url;
  });
  if (result.error) return result;
  redirect(url);
}

export async function syncInstallationAction(
  workspaceId: string,
  installationRef: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `${gh}/installations/${installationRef}/sync`),
  );
}

export async function disconnectInstallationAction(
  workspaceId: string,
  installationRef: string,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `${gh}/installations/${installationRef}/disconnect`),
  );
}

export async function setRepositorySelectedAction(
  workspaceId: string,
  repositoryId: string,
  selected: boolean,
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `${gh}/repositories/${repositoryId}`, { selected }),
  );
}

export async function decideSuggestionAction(
  workspaceId: string,
  suggestionId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const action = String(fd.get("action") ?? "approve");
  const [kind, id] = String(fd.get("assignee") ?? "").split(":");
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `${gh}/suggestions/${suggestionId}/decision`, {
      action,
      role: action === "approve" ? String(fd.get("role") ?? "") || undefined : undefined,
      person_id: action === "approve" && kind === "person" ? id : undefined,
      team_id: action === "approve" && kind === "team" ? id : undefined,
    }),
  );
}
