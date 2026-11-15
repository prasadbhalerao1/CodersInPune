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
        <span className="text-ac text-[13px] font-medium">Recommended</span>
        <h2 className="font-heading text-strong mt-1.5 text-lg leading-tight font-bold">
          Explore a sample workspace
        </h2>
        <p className="text-fg-soft mt-2 text-[13px] leading-relaxed">
          Creates &ldquo;Northwind Labs (demo)&rdquo;: a sample team with ownership gaps, a
          departure case in progress and a handover capsule to review. It never touches real data.
        </p>
      </div>
      <button
        type="submit"
        disabled={pending}
        aria-busy={pending}
        className="btn btn-primary focus-visible:outline-ac w-full focus-visible:outline-2 focus-visible:outline-offset-2 disabled:pointer-events-none disabled:opacity-60"
      >
        {pending ? "Creating sample…" : "Create sample workspace"}
        <ArrowRight aria-hidden className="btn-arrow size-3.5" />
      </button>
      {state.error ? (
        <p role="alert" className="text-bad text-sm">
          {state.error}
        </p>
      ) : null}
    </form>
  );
}
