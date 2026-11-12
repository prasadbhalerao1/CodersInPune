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
    <form
      action={formAction}
      className="border border-[#D2FF00]/30 bg-gradient-to-b from-[#141A28] to-[#0A0D15] flex flex-col gap-3 rounded-2xl p-5 shadow-[0_12px_30px_rgba(0,0,0,0.6)] backdrop-blur-xl"
    >
      <input type="hidden" name="idempotencyKey" value={idempotencyKey} />
      <div>
        <div className="flex items-center gap-2">
          <span className="jewel-chartreuse" />
          <h2 className="text-sm font-bold text-white tracking-wide">
            EXPLORE SAMPLE WORKSPACE // RECOMMENDED
          </h2>
        </div>
        <p className="text-zinc-400 mt-2 text-xs leading-relaxed">
          Instantly stages &ldquo;Northwind Labs (demo)&rdquo;: a fully articulated team with real continuity
          vulnerabilities, absence blast radius simulations, an active departure case, and a verified handover dossier.
        </p>
      </div>
      <div className="mt-2">
        <Button 
          type="submit" 
          disabled={pending} 
          aria-busy={pending} 
          variant="titanium"
          className="w-full !h-11 !text-xs !justify-center"
        >
          <span className="jewel-emerald" />
          <span>{pending ? "STAGING WORKSPACE..." : "ENTER DEMO WORKSPACE ⟶"}</span>
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
