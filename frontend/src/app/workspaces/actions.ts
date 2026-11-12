"use server";

import { withAuth } from "@workos-inc/authkit-nextjs";
import { redirect } from "next/navigation";

import { api, RelayApiError } from "@/lib/relay-api";

export type CreateWorkspaceState = { error?: string };

const KEY_PATTERN = /^[A-Za-z0-9_-]{8,128}$/;

export async function createSampleWorkspaceAction(
  _previous: CreateWorkspaceState,
  formData: FormData,
): Promise<CreateWorkspaceState> {
  const idempotencyKey = String(formData.get("idempotencyKey") ?? "");
  if (!KEY_PATTERN.test(idempotencyKey)) return { error: "Please reload the page and try again." };

  let workspaceId: string;
  try {
    workspaceId = (await api.createSampleWorkspace(idempotencyKey)).id;
  } catch (error) {
    if (error instanceof RelayApiError) {
      if (error.status === 401) {
        return { error: "Your session could not be verified. Sign out and sign in again." };
      }
      if (error.status === 429) {
        return { error: "You have created several sample workspaces today. Open one below." };
      }
      if (error.status === 404) return { error: "Sample workspaces are turned off here." };
    }
    return { error: "The sample workspace could not be created. Please try again." };
  }
  await syncProfile();
  redirect(`/w/${workspaceId}`);
}

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
    workspaceId = (await api.createWorkspace(name, idempotencyKey)).id;
  } catch (error) {
    if (error instanceof RelayApiError && error.status === 401) {
      return { error: "Your session could not be verified. Sign out and sign in again." };
    }
    return { error: "The workspace could not be created. Please try again." };
  }
  await syncProfile();
  redirect(`/w/${workspaceId}`);
}

// A new membership has no display profile yet (it is copied at sign-in); copy it now so
// teammates see a name instead of "Member". Display-only; never blocks creation.
async function syncProfile(): Promise<void> {
  const { user } = await withAuth();
  if (!user) return;
  const displayName = [user.firstName, user.lastName].filter(Boolean).join(" ") || undefined;
  await api.syncMyProfile(displayName, user.email).catch(() => undefined);
}
