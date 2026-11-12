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
      className="bg-[#0E1118] border border-white/10 flex flex-col gap-3 rounded-2xl p-5 shadow-[0_8px_24px_rgba(0,0,0,0.5)] backdrop-blur-xl"
    >
      <input type="hidden" name="idempotencyKey" value={idempotencyKey} />
      <div>
        <h2 className="text-sm font-bold text-white tracking-wide">START SOVEREIGN WORKSPACE</h2>
        <p className="text-zinc-400 mt-0.5 text-xs">You will be its cryptographic owner.</p>
      </div>
      <label htmlFor="workspace-name" className="sr-only">
        Workspace name
      </label>
      <div className="flex flex-col gap-3 mt-1">
        <input
          id="workspace-name"
          name="name"
          required
          maxLength={100}
          placeholder="e.g. Acme Engineering"
          className="h-10 flex-1 rounded-xl border border-white/10 bg-black/40 px-3.5 text-xs text-white placeholder:text-zinc-600 outline-none focus:border-[#D2FF00]/50 focus:ring-1 focus:ring-[#D2FF00]/30 transition-all"
          aria-describedby={state.error ? "workspace-error" : undefined}
        />
        <Button 
          type="submit" 
          disabled={pending}
          variant="titaniumGhost"
          className="w-full !h-10 !text-xs !justify-center"
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
