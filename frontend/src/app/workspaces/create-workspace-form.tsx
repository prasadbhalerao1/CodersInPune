"use client";

import { useActionState } from "react";

import { Button } from "@/components/ui/button";

import { createWorkspaceAction, type CreateWorkspaceState } from "./actions";

// `idempotencyKey` is generated once per rendered form, so a double submit or a retry of
// the same form creates at most one workspace.
export function CreateWorkspaceForm({ idempotencyKey }: { idempotencyKey: string }) {
  const [state, formAction, pending] = useActionState<CreateWorkspaceState, FormData>(
    createWorkspaceAction,
    {},
  );
  return (
    <form
      action={formAction}
      className="bg-card flex flex-col gap-3 rounded-xl border p-4 shadow-xs"
    >
      <input type="hidden" name="idempotencyKey" value={idempotencyKey} />
      <div>
        <h2 className="text-sm font-semibold">Start your own</h2>
        <p className="text-muted-foreground mt-0.5 text-xs">You will be its owner.</p>
      </div>
      <label htmlFor="workspace-name" className="sr-only">
        Workspace name
      </label>
      <div className="flex flex-col gap-2">
        <input
          id="workspace-name"
          name="name"
          required
          maxLength={100}
          placeholder="Acme Engineering"
          className="border-input bg-background focus-visible:ring-ring/50 h-9 flex-1 rounded-md border px-3 text-sm outline-none focus-visible:ring-3"
          aria-describedby={state.error ? "workspace-error" : undefined}
        />
        <Button type="submit" disabled={pending}>
          {pending ? "Creating…" : "Create workspace"}
        </Button>
      </div>
      {state.error ? (
        <p id="workspace-error" role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      ) : null}
    </form>
  );
}
