"use client";

import { useState } from "react";

import { inputClass } from "@/components/action-form";
import { cn } from "@/lib/utils";

const EXAMPLE = `Priya: Quick sync on the payments migration before Arjun leaves on Friday.
Arjun: We decided to keep Stripe webhooks on the old endpoint until the March cut-over.
Priya: Agreed. Who approves refunds over 50k while Arjun is away?
Arjun: Only I know how the vault recovery works, that's a real risk.
Priya: I'll write the rollback runbook by Thursday.
Arjun: Meera will review the reconciliation job alerts next week.
Priya: Can you share the PagerDuty escalation order with Meera?
Arjun: Yes. Final call: we go with Postgres advisory locks for the settlement batch.
Priya: Thanks all.`;

/** The transcript box, with an example a first-time visitor can try at once. */
export function TranscriptField() {
  const [value, setValue] = useState("");
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor="transcript" className="text-sm font-medium">
          Notes or transcript
        </label>
        <button
          type="button"
          onClick={(e) => {
            setValue(EXAMPLE);
            // The title is required too: fill it if empty, so the example works in one click.
            const title = e.currentTarget.form?.elements.namedItem("title");
            if (title instanceof HTMLInputElement && !title.value) {
              title.value = "Payments migration sync";
            }
          }}
          className="text-primary text-xs font-medium hover:underline"
        >
          Use an example
        </button>
      </div>
      <textarea
        id="transcript"
        name="transcript"
        required
        rows={9}
        maxLength={60000}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder={"One line per speaker turn works best, e.g.\nPriya: We decided to …"}
        className={cn(inputClass, "h-auto py-2 font-mono text-[13px] leading-relaxed")}
      />
    </div>
  );
}
