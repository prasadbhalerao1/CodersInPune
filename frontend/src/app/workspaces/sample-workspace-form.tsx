"use client";

import { useActionState } from "react";

import { Button } from "@/components/ui/button";

import { createSampleWorkspaceAction, type CreateWorkspaceState } from "./actions";

// Seeding takes a few seconds, so the button stays disabled while pending and the key is
// fixed per rendered form: a double click or retry yields one sample workspace.
export function SampleWorkspaceForm({ idempotencyKey }: { idempotencyKey: string }) {
  const [state, formAction, pending] = useActionState<CreateWorkspaceState, FormData>(
    createSampleWorkspaceAction,
    {},
  );
  return (
    <form action={formAction} className="flex flex-col gap-3 rounded-lg border p-4">
      <input type="hidden" name="idempotencyKey" value={idempotencyKey} />
      <div>
        <h2 className="text-sm font-semibold">Explore a sample organisation</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          Creates &ldquo;Northwind Labs (demo)&rdquo;: a fictional team with responsibilities,
          coverage gaps, an active departure and a handover waiting for your acknowledgement. No
          real data is used and nothing is connected.
        </p>
      </div>
      <div>
        <Button type="submit" variant="outline" disabled={pending} aria-busy={pending}>
          {pending ? "Setting up the sample…" : "Create sample workspace"}
        </Button>
      </div>
      {state.error ? (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      ) : null}
    </form>
  );
}
