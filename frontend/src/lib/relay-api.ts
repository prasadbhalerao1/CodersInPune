import "server-only";

import { withAuth } from "@workos-inc/authkit-nextjs";

// Server-side client for the Relay API. The WorkOS access token stays on the server:
// it is read from the encrypted session cookie and sent as a bearer token, never exposed
// to the browser. The API verifies it and resolves workspaces through Relay membership.

export type Workspace = { id: string; name: string; role: string };

export class RelayApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string | undefined,
    message: string,
  ) {
    super(message);
  }
}

function apiBaseUrl(): string {
  const url = process.env.RELAY_API_URL;
  if (!url) throw new Error("RELAY_API_URL is not configured");
  return url.replace(/\/$/, "");
}

async function relayFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { accessToken } = await withAuth({ ensureSignedIn: true });
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");

  const response = await fetch(`${apiBaseUrl()}${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as {
      code?: string;
      detail?: string;
    };
    throw new RelayApiError(
      response.status,
      problem.code,
      problem.detail ?? `Relay API error ${response.status}`,
    );
  }
  return (await response.json()) as T;
}

export function listWorkspaces(): Promise<Workspace[]> {
  return relayFetch<Workspace[]>("/workspaces");
}

export function getWorkspace(id: string): Promise<Workspace> {
  return relayFetch<Workspace>(`/workspaces/${encodeURIComponent(id)}`);
}

export function createWorkspace(name: string, idempotencyKey: string): Promise<Workspace> {
  return relayFetch<Workspace>("/workspaces", {
    method: "POST",
    body: JSON.stringify({ name }),
    headers: { "Idempotency-Key": idempotencyKey },
  });
}
