"use client";

import { RotateCcw } from "lucide-react";
import { useActionState, useState } from "react";

import { createSampleWorkspaceAction, type CreateWorkspaceState } from "@/app/workspaces/actions";
import { Button } from "@/components/ui/button";

/**
 * A clean copy of the sample, for a fresh demo: creates a new "Northwind Labs (sample)" and
 * opens it. The current one is left as it is (it can be deleted in Settings).
 */
export function ResetSampleButton() {
  const [key] = useState(() => crypto.randomUUID().replaceAll("-", ""));
  const [state, action, pending] = useActionState<CreateWorkspaceState, FormData>(
    createSampleWorkspaceAction,
    {},
  );
  return (
    <form action={action} className="flex items-center gap-2">
      <input type="hidden" name="idempotencyKey" value={key} />
      {state.error ? (
        <span role="alert" className="text-xs text-amber-700 dark:text-amber-300">
          {state.error}
        </span>
      ) : null}
      <Button type="submit" size="sm" variant="outline" disabled={pending}>
        <RotateCcw aria-hidden className="size-3.5" />
        {pending ? "Preparing a fresh copy…" : "Fresh sample"}
      </Button>
    </form>
  );
}
