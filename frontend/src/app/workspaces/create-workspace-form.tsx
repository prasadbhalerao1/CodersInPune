"use client";

import { useActionState } from "react";

import { createWorkspaceAction, type CreateWorkspaceState } from "./actions";

// `idempotencyKey` is generated once per rendered form, so a double submit or a retry of
// the same form creates at most one workspace.
export function CreateWorkspaceForm({ idempotencyKey }: { idempotencyKey: string }) {
  const [state, formAction, pending] = useActionState<CreateWorkspaceState, FormData>(
    createWorkspaceAction,
    {},
  );
  return (
    <form action={formAction} className="glass-clear flex flex-col gap-4 p-5">
      <input type="hidden" name="idempotencyKey" value={idempotencyKey} />
      <div>
        <h2 className="font-syne text-strong text-lg leading-tight font-bold">
          Start a new workspace
        </h2>
        <p className="text-fg-soft mt-1 text-[13px]">You will be its owner.</p>
      </div>
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="workspace-name"
          className="text-fg-mute font-mono text-[11px] font-semibold tracking-[0.14em] uppercase"
        >
          Workspace name
        </label>
        <input
          id="workspace-name"
          name="name"
          required
          maxLength={100}
          placeholder="e.g. Acme Engineering"
          className="border-line/15 bg-sunk/60 text-strong placeholder:text-fg-mute/80 focus:border-ac focus:ring-ac/25 h-10 rounded-lg border px-3 text-sm transition-colors outline-none focus:ring-3"
          aria-describedby={state.error ? "workspace-error" : undefined}
        />
      </div>
      <button
        type="submit"
        disabled={pending}
        aria-busy={pending}
        className="border-line/20 text-strong hover:border-ac hover:text-ac focus-visible:outline-ac inline-flex h-10 w-full items-center justify-center rounded-full border px-5 text-xs font-bold tracking-wider uppercase transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-60"
      >
        {pending ? "Creating…" : "Create workspace"}
      </button>
      {state.error ? (
        <p id="workspace-error" role="alert" className="text-bad text-sm">
          {state.error}
        </p>
      ) : null}
    </form>
  );
}
