"use client";

import { useActionState, useState } from "react";
import { useFormStatus } from "react-dom";

import { inputClass } from "@/components/action-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ImportKind } from "@/lib/types";
import { cn } from "@/lib/utils";

import { importCsvAction, type ImportState } from "./actions";

const KINDS: { value: ImportKind; label: string; columns: string; example: string }[] = [
  {
    value: "people",
    label: "People",
    columns: "name · email · title · department · github_login",
    example:
      "name,email,title,department\nAda Lovelace,ada@example.com,Staff engineer,Engineering\n",
  },
  {
    value: "responsibilities",
    label: "Responsibilities",
    columns: "name · criticality (critical, high, standard, low) · category · description",
    example: "name,criticality,category\nPayments on-call,critical,Operations\n",
  },
  {
    value: "assignments",
    label: "Ownership",
    columns:
      "responsibility · owner (email, name or team) · role (primary, co_owner, backup) · owner_type",
    example: "responsibility,owner,role\nPayments on-call,ada@example.com,primary\n",
  },
];

const ACTION = {
  create: { label: "Create", tone: "neutral" },
  skip: { label: "Skip", tone: "muted" },
  error: { label: "Error", tone: "danger" },
} as const;

function StepButton({
  step,
  children,
  disabled,
}: {
  step: string;
  children: string;
  disabled?: boolean;
}) {
  const { pending } = useFormStatus();
  return (
    <Button
      type="submit"
      name="step"
      value={step}
      variant={step === "commit" ? "default" : "outline"}
      disabled={pending || disabled}
    >
      {pending ? "Working…" : children}
    </Button>
  );
}

export function ImportForm({ workspaceId }: { workspaceId: string }) {
  const [state, action] = useActionState<ImportState, FormData>(
    importCsvAction.bind(null, workspaceId),
    {},
  );
  const [kind, setKind] = useState<ImportKind>("people");
  // The file is read into state: forms reset after each action, and the commit step must
  // send exactly the content that was previewed.
  const [file, setFile] = useState<{ name: string; text: string } | null>(null);
  const selected = KINDS.find((k) => k.value === kind) ?? KINDS[0];
  const [sent, setSent] = useState<string | null>(null);
  // Only show (and allow committing) the result for the exact file and kind previewed.
  const result =
    state.result?.kind === kind && file !== null && sent === file.text ? state.result : undefined;
  const template = `data:text/csv;charset=utf-8,${encodeURIComponent(selected.example)}`;

  return (
    <form
      action={action}
      onSubmit={() => setSent(file?.text ?? null)}
      className="flex flex-col gap-6"
    >
      <fieldset className="flex flex-col gap-3">
        <legend className="mb-2 text-sm font-semibold">What are you importing?</legend>
        <div role="radiogroup" className="grid gap-2 sm:grid-cols-3">
          {KINDS.map((k) => (
            <label
              key={k.value}
              className={cn(
                "flex cursor-pointer flex-col gap-0.5 rounded-lg border px-3 py-2.5 text-sm transition-colors",
                kind === k.value
                  ? "border-foreground/40 bg-foreground/[0.03]"
                  : "hover:bg-muted/60",
              )}
            >
              <input
                type="radio"
                name="kind"
                value={k.value}
                checked={kind === k.value}
                onChange={() => setKind(k.value)}
                className="sr-only"
              />
              <span className="font-medium">{k.label}</span>
            </label>
          ))}
        </div>
        <p className="text-muted-foreground text-xs">
          Columns: {selected.columns}.{" "}
          <a href={template} download={`relay-${kind}.csv`} className="text-foreground underline">
            Download a template
          </a>
        </p>
      </fieldset>

      <div className="flex flex-wrap items-end gap-2">
        <label className="flex min-w-72 flex-1 flex-col gap-1.5 text-xs font-medium">
          CSV file
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={async (e) => {
              const chosen = e.target.files?.[0];
              setFile(chosen ? { name: chosen.name, text: await chosen.text() } : null);
            }}
            className={cn(
              inputClass,
              "file:text-foreground py-1.5 file:mr-3 file:border-0 file:bg-transparent file:text-sm file:font-medium",
            )}
          />
        </label>
        <input type="hidden" name="csv" value={file?.text ?? ""} />
        {file ? (
          <span className="text-muted-foreground self-center text-xs">{file.name}</span>
        ) : null}
        <StepButton step="preview" disabled={!file}>
          Preview
        </StepButton>
        {result && !result.committed ? (
          <StepButton step="commit" disabled={result.created === 0}>
            {`Import ${result.created} ${result.created === 1 ? "row" : "rows"}`}
          </StepButton>
        ) : null}
      </div>

      {state.error ? (
        <p role="alert" className="text-destructive text-sm">
          {state.error}
        </p>
      ) : null}

      {result ? (
        <section aria-live="polite" className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="font-medium">{result.committed ? "Imported" : "Preview"}</span>
            <span className="text-muted-foreground">·</span>
            <span>
              {result.created} {result.committed ? "created" : "to create"}
            </span>
            <span className="text-muted-foreground">· {result.skipped} skipped</span>
            {result.errors ? <Badge tone="danger">{result.errors} with errors</Badge> : null}
            {result.ignored_columns.length ? (
              <span className="text-muted-foreground text-xs">
                Ignored columns: {result.ignored_columns.join(", ")}
              </span>
            ) : null}
          </div>
          {!result.committed && result.errors ? (
            <p className="text-muted-foreground text-xs">
              Rows with errors are left out; fix them and import the file again. Existing records
              are never changed and existing owners are never replaced.
            </p>
          ) : null}
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-muted-foreground text-left text-xs">
                <tr>
                  <th className="w-16 px-3 py-2 font-medium">Line</th>
                  <th className="px-3 py-2 font-medium">Row</th>
                  <th className="w-24 px-3 py-2 font-medium">Result</th>
                  <th className="px-3 py-2 font-medium">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {result.rows.map((r) => (
                  <tr
                    key={r.line}
                    className={r.action === "error" ? "bg-red-50/40 dark:bg-red-950/10" : undefined}
                  >
                    <td className="text-muted-foreground px-3 py-2 tabular-nums">{r.line}</td>
                    <td className="px-3 py-2 font-medium">{r.label || "—"}</td>
                    <td className="px-3 py-2">
                      <Badge tone={ACTION[r.action].tone}>
                        {result.committed && r.action === "create"
                          ? "Created"
                          : ACTION[r.action].label}
                      </Badge>
                    </td>
                    <td className="text-muted-foreground px-3 py-2 text-xs">{r.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </form>
  );
}
