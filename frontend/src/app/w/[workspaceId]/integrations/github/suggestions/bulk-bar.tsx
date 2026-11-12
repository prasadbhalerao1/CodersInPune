"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";

import { Button } from "@/components/ui/button";

import { bulkSuggestionsAction, type BulkState } from "../../actions";

export const BULK_FORM = "bulk-suggestions";

function Action({ value, children }: { value: string; children: string }) {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      name="bulk_action"
      value={value}
      size="sm"
      variant={value === "approve" ? "default" : "outline"}
      disabled={pending}
    >
      {children}
    </Button>
  );
}

/** Rows opt in with `<input type="checkbox" name="ids" form={BULK_FORM}>`. */
export function BulkBar({ workspaceId, actions }: { workspaceId: string; actions: string[] }) {
  const [state, action] = useActionState<BulkState, FormData>(
    bulkSuggestionsAction.bind(null, workspaceId),
    {},
  );
  const toggleAll = (checked: boolean) =>
    document
      .querySelectorAll<HTMLInputElement>(`input[form="${BULK_FORM}"][name="ids"]`)
      .forEach((box) => (box.checked = checked));

  return (
    <form
      id={BULK_FORM}
      action={action}
      className="bg-muted/40 flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-sm"
    >
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          aria-label="Select all"
          onChange={(e) => toggleAll(e.target.checked)}
          className="size-4"
        />
        <span className="text-muted-foreground">Selected</span>
      </label>
      <span className="flex-1" />
      {actions.includes("approve") ? <Action value="approve">Approve</Action> : null}
      {actions.includes("defer") ? <Action value="defer">Later</Action> : null}
      {actions.includes("dismiss") ? <Action value="dismiss">Dismiss</Action> : null}
      {state.error ? (
        <p role="alert" className="text-destructive w-full text-xs">
          {state.error}
        </p>
      ) : state.done !== undefined ? (
        <p role="status" className="text-muted-foreground w-full text-xs">
          {state.done} done
          {state.failed?.length
            ? ` · ${state.failed.length} need attention: ${[...new Set(state.failed.map((f) => f.error))].join(" ")}`
            : ""}
        </p>
      ) : null}
    </form>
  );
}
