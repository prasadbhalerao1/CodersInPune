"use client";

import { ArrowRight } from "lucide-react";
import { useActionState } from "react";

import { createSampleWorkspaceAction, type CreateWorkspaceState } from "./actions";

// Seeding takes a few seconds, so the button stays disabled while pending and the key is
// fixed per rendered form: a double click or retry yields one sample workspace.
export function SampleWorkspaceForm({ idempotencyKey }: { idempotencyKey: string }) {
  const [state, formAction, pending] = useActionState<CreateWorkspaceState, FormData>(
    createSampleWorkspaceAction,
    {},
  );
  return (
    <form action={formAction} className="glass flex flex-col gap-4 p-5">
      <input type="hidden" name="idempotencyKey" value={idempotencyKey} />
      <div>
        <span className="text-ac font-mono text-[11px] font-semibold tracking-[0.18em] uppercase">
          Recommended
        </span>
        <h2 className="font-syne text-strong mt-1.5 text-lg leading-tight font-bold">
          Explore a sample workspace
        </h2>
        <p className="text-fg-soft mt-2 text-[13px] leading-relaxed">
          Creates &ldquo;Northwind Labs (demo)&rdquo;: a synthetic team with ownership gaps, a
          departure case in progress and a handover capsule to review. It never touches real data.
        </p>
      </div>
      <button
        type="submit"
        disabled={pending}
        aria-busy={pending}
        className="group bg-cta text-cta-fg hover:bg-cta-hover focus-visible:outline-ac inline-flex h-11 w-full items-center justify-center gap-2 rounded-full px-5 text-xs font-bold tracking-wider uppercase transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-60"
      >
        {pending ? "Creating sample…" : "Create sample workspace"}
        <ArrowRight
          aria-hidden
          className="size-3.5 transition-transform group-hover:translate-x-0.5"
        />
      </button>
      {state.error ? (
        <p role="alert" className="text-bad text-sm">
          {state.error}
        </p>
      ) : null}
    </form>
  );
}
