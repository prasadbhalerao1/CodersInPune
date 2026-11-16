"use client";

import { ExternalLink, PanelRightOpen, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { formatDateTime } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import type { EvidenceView } from "@/lib/types";

const SOURCE = { relay: "Relay", github: "GitHub", linear: "Linear", notion: "Notion" } as const;

/**
 * Opens one piece of evidence in a side panel: where it came from, when, whether it changed
 * since it was cited, and the full excerpt, without leaving the page that cites it.
 */
export function EvidenceSheet({ evidence: e }: { evidence: EvidenceView }) {
  const [open, setOpen] = useState(false);
  const close = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    close.current?.focus();
    const onKey = (ev: KeyboardEvent) => ev.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={`Inspect evidence ${e.ref}: ${e.title}`}
        className="text-muted-foreground hover:text-foreground inline-flex items-center"
      >
        <PanelRightOpen aria-hidden className="size-3.5" />
      </button>
      {open
        ? createPortal(
            <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
              <button
                type="button"
                aria-label="Close evidence"
                tabIndex={-1}
                onClick={() => setOpen(false)}
                className="absolute inset-0 bg-black/30 backdrop-blur-[1px]"
              />
              <aside
                role="dialog"
                aria-modal="true"
                aria-labelledby={`ev-${e.id}`}
                className="bg-background panel-in relative flex h-full w-full max-w-md flex-col gap-4 overflow-y-auto border-l p-5 text-sm shadow-xl"
              >
                <div className="flex items-start gap-3">
                  <span className="text-muted-foreground bg-muted rounded px-1.5 py-0.5 font-mono text-xs">
                    {e.ref}
                  </span>
                  <h2 id={`ev-${e.id}`} className="min-w-0 flex-1 font-semibold">
                    {e.title}
                  </h2>
                  <button
                    ref={close}
                    type="button"
                    onClick={() => setOpen(false)}
                    aria-label="Close"
                    className="text-muted-foreground hover:text-foreground"
                  >
                    <X aria-hidden className="size-4" />
                  </button>
                </div>
                <dl className="grid grid-cols-[7rem_1fr] gap-x-3 gap-y-1.5 text-xs">
                  <dt className="text-muted-foreground">Source</dt>
                  <dd>
                    {SOURCE[e.source_system]} · {e.source_type.replaceAll("_", " ")}
                  </dd>
                  <dt className="text-muted-foreground">Dated</dt>
                  <dd>{e.source_ts ? formatDateTime(e.source_ts) : "Unknown"}</dd>
                  {e.revision ? (
                    <>
                      <dt className="text-muted-foreground">Revision</dt>
                      <dd className="font-mono break-all">{e.revision.slice(0, 40)}</dd>
                    </>
                  ) : null}
                  <dt className="text-muted-foreground">Who may see it</dt>
                  <dd>
                    {e.audience === "managers" ? "Managers only" : "Everyone in the workspace"}
                  </dd>
                </dl>
                <div className="flex flex-wrap gap-1.5">
                  {e.status !== "active" ? (
                    <Badge tone="muted">{e.status === "stale" ? "Stale" : "Withdrawn"}</Badge>
                  ) : null}
                  {e.changed ? <Badge tone="warning">Changed since it was cited</Badge> : null}
                </div>
                <blockquote className="bg-muted/40 rounded-md border-l-2 px-3 py-2 leading-relaxed whitespace-pre-line">
                  {e.excerpt || "This source has no text excerpt."}
                </blockquote>
                {e.url && e.status === "active" ? (
                  <a
                    href={e.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary inline-flex items-center gap-1.5 font-medium hover:underline"
                  >
                    Open the source <ExternalLink aria-hidden className="size-3.5" />
                  </a>
                ) : null}
                <p className="text-muted-foreground mt-auto text-xs">
                  Relay quotes sources; it never edits them. A citation to something you can&apos;t
                  see is never shown.
                </p>
              </aside>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
