"use client";

import { useState, useTransition } from "react";

import { Button } from "@/components/ui/button";

import { sendTestEmailAction, type TestEmailResult } from "./actions";

/** Admins can confirm email works end to end; it only ever goes to their own address. */
export function TestEmailButton({ workspaceId }: { workspaceId: string }) {
  const [result, setResult] = useState<TestEmailResult | null>(null);
  const [pending, start] = useTransition();
  return (
    <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={pending}
        onClick={() => start(async () => setResult(await sendTestEmailAction(workspaceId)))}
      >
        {pending ? "Sending\u2026" : "Send test email to me"}
      </Button>
      {result ? (
        <span role="status" className={result.sent ? "" : "text-red-700 dark:text-red-400"}>
          {result.sent
            ? `Sent to ${result.to}. Check that inbox (and spam).`
            : `Not sent: ${result.error ?? "unknown error"}.`}
        </span>
      ) : null}
    </div>
  );
}
