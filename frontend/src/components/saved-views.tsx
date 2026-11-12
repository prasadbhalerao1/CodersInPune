import Link from "next/link";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { deleteViewAction, saveViewAction } from "@/app/w/[workspaceId]/cases/actions";
import type { SavedPage, SavedViewView } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Personal saved filters for a list page: a row of views plus "save current filters". */
export function SavedViews({
  workspaceId,
  page,
  base,
  views,
  current,
}: {
  workspaceId: string;
  page: SavedPage;
  base: string;
  views: SavedViewView[];
  current: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {views.length ? <span className="text-muted-foreground text-xs">Saved views</span> : null}
      {views.map((v) => (
        <span
          key={v.id}
          className={cn(
            "flex items-center gap-1 rounded-md border pl-2.5",
            v.query === current && "bg-foreground/[0.06] font-medium",
          )}
        >
          <Link href={`${base}?${v.query}`} className="py-1">
            {v.name}
          </Link>
          <ActionForm action={deleteViewAction.bind(null, workspaceId, v.id)}>
            <SubmitButton
              size="sm"
              variant="ghost"
              pendingLabel="…"
              confirm={`Delete the saved view “${v.name}”?`}
            >
              <span aria-label={`Delete ${v.name}`}>×</span>
            </SubmitButton>
          </ActionForm>
        </span>
      ))}
      {current ? (
        <details className="relative">
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-xs">
            Save these filters
          </summary>
          <ActionForm
            action={saveViewAction.bind(null, workspaceId, page, current)}
            className="bg-background absolute z-10 mt-1 w-64 flex-row rounded-lg border p-2 shadow-sm"
          >
            <input
              name="name"
              required
              maxLength={80}
              placeholder="View name"
              aria-label="View name"
              className={cn(inputClass, "h-8")}
            />
            <SubmitButton size="sm" pendingLabel="…">
              Save
            </SubmitButton>
          </ActionForm>
        </details>
      ) : null}
    </div>
  );
}
