"use client";

import { useActionState, useState, type ReactNode } from "react";
import { useFormStatus } from "react-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { ActionState } from "@/lib/action-state";

export const inputClass =
  "border-input bg-background focus-visible:ring-ring/40 h-9 w-full rounded-md border px-3 text-sm outline-none focus-visible:ring-3 disabled:opacity-60";

export function ActionForm({
  action,
  children,
  className,
  id,
}: {
  action: (state: ActionState, formData: FormData) => Promise<ActionState>;
  children: ReactNode;
  className?: string;
  /** Lets inputs elsewhere on the page join this form via their `form` attribute. */
  id?: string;
}) {
  const [state, formAction] = useActionState(action, {});
  return (
    <form id={id} action={formAction} className={cn("flex flex-col gap-3", className)}>
      {children}
      {state.error ? (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      ) : null}
    </form>
  );
}

export function SubmitButton({
  children,
  pendingLabel,
  variant,
  size,
  confirm,
}: {
  children: ReactNode;
  pendingLabel?: string;
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm";
  /** Ask before submitting (irreversible or disruptive actions). */
  confirm?: string;
}) {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      disabled={pending}
      variant={variant}
      size={size}
      onClick={confirm ? (event) => window.confirm(confirm) || event.preventDefault() : undefined}
    >
      {pending ? (pendingLabel ?? "Saving…") : children}
    </Button>
  );
}

export function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-xs font-medium">
        {label}
      </label>
      {children}
    </div>
  );
}

// datetime-local has no timezone; send the browser's interpretation as an ISO instant.
/** Local date-time picker that submits ISO 8601 (UTC). An empty value submits "". */
export function DateTimeInput({
  id,
  name,
  defaultValue,
}: {
  id: string;
  name: string;
  defaultValue?: string | null;
}) {
  const [iso, setIso] = useState(defaultValue ?? "");
  const local = defaultValue ? toLocalInput(defaultValue) : undefined;
  return (
    <>
      <input
        id={id}
        type="datetime-local"
        className={inputClass}
        defaultValue={local}
        suppressHydrationWarning // the server renders in its own time zone
        onChange={(e) => setIso(e.target.value ? new Date(e.target.value).toISOString() : "")}
      />
      <input type="hidden" name={name} value={iso} />
    </>
  );
}

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
