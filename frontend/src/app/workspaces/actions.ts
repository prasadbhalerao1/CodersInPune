"use server";

import { redirect } from "next/navigation";

import { createWorkspace, RelayApiError } from "@/lib/relay-api";

export type CreateWorkspaceState = { error?: string };

const KEY_PATTERN = /^[A-Za-z0-9_-]{8,128}$/;

export async function createWorkspaceAction(
  _previous: CreateWorkspaceState,
  formData: FormData,
): Promise<CreateWorkspaceState> {
  const name = String(formData.get("name") ?? "").trim();
  const idempotencyKey = String(formData.get("idempotencyKey") ?? "");
  if (!name || name.length > 100) return { error: "Enter a name of 1–100 characters." };
  if (!KEY_PATTERN.test(idempotencyKey)) return { error: "Please reload the page and try again." };

  let workspaceId: string;
  try {
    workspaceId = (await createWorkspace(name, idempotencyKey)).id;
  } catch (error) {
    if (error instanceof RelayApiError && error.status === 401) {
      return { error: "Your session could not be verified. Sign out and sign in again." };
    }
    return { error: "The workspace could not be created. Please try again." };
  }
  redirect(`/w/${workspaceId}`);
}
