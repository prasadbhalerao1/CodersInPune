import "server-only";

import { notFound } from "next/navigation";

import { RelayApiError } from "@/lib/relay-api";

export type Attempt<T> = { ok: true; data: T } | { ok: false; error: RelayApiError };

/** Resolve an API call for a page: 404 → notFound(), other API errors → returned for a notice. */
export async function attempt<T>(promise: Promise<T>): Promise<Attempt<T>> {
  try {
    return { ok: true, data: await promise };
  } catch (error) {
    if (error instanceof RelayApiError) {
      if (error.status === 404) notFound();
      return { ok: false, error };
    }
    throw error;
  }
}
