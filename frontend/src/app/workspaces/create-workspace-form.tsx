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
      className="bg-card border-line/10 flex flex-col gap-3 rounded-2xl border p-5 shadow-[0_8px_24px_rgba(0,0,0,0.5)] backdrop-blur-xl"
    >
      <input type="hidden" name="idempotencyKey" value={idempotencyKey} />
      <div>
        <h2 className="text-strong text-sm font-bold tracking-wide">START SOVEREIGN WORKSPACE</h2>
        <p className="text-fg-mute mt-0.5 text-xs">You will be its cryptographic owner.</p>
      </div>
      <label htmlFor="workspace-name" className="sr-only">
        Workspace name
      </label>
      <div className="mt-1 flex flex-col gap-3">
        <input
          id="workspace-name"
          name="name"
          required
          maxLength={100}
          placeholder="e.g. Acme Engineering"
          className="border-line/10 bg-sunk/40 text-strong placeholder:text-fg-mute focus:border-ac/50 focus:ring-ac/30 h-10 flex-1 rounded-xl border px-3.5 text-xs transition-all outline-none focus:ring-1"
          aria-describedby={state.error ? "workspace-error" : undefined}
        />
        <Button
          type="submit"
          disabled={pending}
          variant="titaniumGhost"
          className="!h-10 w-full !justify-center !text-xs"
        >
          {pending ? "CREATING..." : "INITIALIZE WORKSPACE ⟶"}
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
