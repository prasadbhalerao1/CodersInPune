import { withAuth } from "@workos-inc/authkit-nextjs";
import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { Walkthrough } from "@/components/landing/walkthrough";
import { RelayMark } from "@/components/workspace-heading";

export const metadata: Metadata = {
  title: "Relay — continuity when people and responsibilities change",
  description:
    "Relay finds what someone owns, reconstructs the context from your tools with cited evidence, and moves ownership through reviewed, auditable handovers.",
};

const PROBLEMS = [
  {
    stat: "Single owner",
    text: "Critical work quietly depends on one person until the day they leave or go on leave.",
  },
  {
    stat: "Scattered context",
    text: "Decisions live in PRs, tickets and old docs nobody can find, or that quietly went stale.",
  },
  {
    stat: "Unclear handovers",
    text: "Ownership moves in a chat message, with no record of what was handed over or missed.",
  },
];

const FEATURES = [
  {
    title: "Responsibility catalogue",
    text: "Who owns what, with primary, backup and co-owners, review cadence, escalation paths and full ownership history.",
    detail: "Restricted responsibilities stay hidden at the database, not just the UI.",
  },
  {
    title: "Continuity cases",
    text: "Onboarding, transfer, coverage, departure and project handover, with an explicit state model, approvals and readiness.",
    detail: "Separation of duties on critical changes; blockers escalate on their own.",
  },
  {
    title: "Evidence-backed analysis",
    text: "Findings labelled Fact, Rule, AI inference, Conflict or Missing evidence, each citing its source.",
    detail: "Uncited claims are dropped; managers-only evidence never reaches a member.",
  },
  {
    title: "Handover capsules",
    text: "A role-specific handover, versioned, redacted where needed, approved by a second person and acknowledged.",
    detail: "Omissions are listed, so the recipient knows what they can't see.",
  },
  {
    title: "Governed knowledge",
    text: "Versions you can compare, stewards who verify, disputes that keep history, and validity windows.",
    detail: "Imported pages stay unverified until a person checks them.",
  },
  {
    title: "Connected, read-only by default",
    text: "GitHub, Linear and Notion feed evidence. Creating an issue needs explicit approval of its exact content.",
    detail: "Retries can't create duplicates; every write leaves a receipt.",
  },
];

const PRINCIPLES = [
  [
    "People decide",
    "AI drafts proposals; it holds no write tools. Every change is approved and audited.",
  ],
  [
    "Least privilege",
    "Tenant isolation with row-level security, scoped roles and fail-closed restricted data.",
  ],
  [
    "Honest about gaps",
    "Stale, partial or missing sources are shown as such, never filled in by a model.",
  ],
  ["Yours to take", "Export your workspace and audit log any time; retention is yours to set."],
] as const;

export default function HomePage() {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="bg-background/80 sticky top-0 z-20 border-b backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <RelayMark className="size-6" />
            Relay
          </Link>
          <nav aria-label="Sections" className="text-muted-foreground hidden gap-5 text-sm sm:flex">
            <a href="#how" className="hover:text-foreground">
              How it works
            </a>
            <a href="#features" className="hover:text-foreground">
              Product
            </a>
            <a href="#trust" className="hover:text-foreground">
              Trust
            </a>
          </nav>
          <span className="flex-1" />
          <Suspense fallback={null}>
            <PrimaryAction compact />
          </Suspense>
        </div>
      </header>

      <main className="flex-1">
        <section className="relative overflow-hidden border-b">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 [background-image:linear-gradient(to_right,var(--border)_1px,transparent_1px),linear-gradient(to_bottom,var(--border)_1px,transparent_1px)] [mask-image:radial-gradient(ellipse_at_top,black_20%,transparent_70%)] [background-size:44px_44px] opacity-60"
          />
          <div className="relative mx-auto flex max-w-6xl flex-col items-start gap-6 px-4 pt-20 pb-16 sm:px-6 sm:pt-28">
            <p className="text-muted-foreground rounded-full border px-3 py-1 text-xs">
              Organisational continuity, with evidence
            </p>
            <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-6xl">
              When people move on, the work shouldn&apos;t stall.
            </h1>
            <p className="text-muted-foreground max-w-2xl text-lg text-pretty">
              Relay finds everything someone owns, rebuilds the context from the tools you already
              use, and moves responsibility through a reviewed handover that cites its sources.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <Suspense fallback={null}>
                <PrimaryAction />
              </Suspense>
              <a href="#how" className="text-muted-foreground hover:text-foreground text-sm">
                See how it works ↓
              </a>
            </div>
          </div>
        </section>

        <section className="border-b">
          <div className="mx-auto grid max-w-6xl gap-px overflow-hidden px-4 py-12 sm:grid-cols-3 sm:px-6">
            {PROBLEMS.map((p) => (
              <div key={p.stat} className="flex flex-col gap-1 p-4">
                <p className="text-sm font-semibold">{p.stat}</p>
                <p className="text-muted-foreground text-sm">{p.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section id="how" className="scroll-mt-16 border-b">
          <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-20 sm:px-6">
            <div className="max-w-2xl">
              <h2 className="text-3xl font-semibold tracking-tight">
                From a change to a reviewed handover
              </h2>
              <p className="text-muted-foreground mt-2">
                The whole loop, as it runs in the product. Click a step, or let it play.
              </p>
            </div>
            <Walkthrough />
          </div>
        </section>

        <section id="features" className="scroll-mt-16 border-b">
          <div className="mx-auto flex max-w-6xl flex-col gap-8 px-4 py-20 sm:px-6">
            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight">
              One place for who owns what, and how it moves
            </h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {FEATURES.map((f) => (
                <div
                  key={f.title}
                  tabIndex={0}
                  className="group hover:border-foreground/30 focus-visible:border-foreground/30 flex flex-col gap-2 rounded-xl border p-5 transition-colors outline-none"
                >
                  <p className="font-medium">{f.title}</p>
                  <p className="text-muted-foreground text-sm">{f.text}</p>
                  <p className="text-sm opacity-70 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                    {f.detail}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section id="trust" className="scroll-mt-16 border-b">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 py-20 sm:px-6 lg:grid-cols-[1fr_1.4fr]">
            <div>
              <h2 className="text-3xl font-semibold tracking-tight">Built to be trusted with it</h2>
              <p className="text-muted-foreground mt-2">
                Continuity data is sensitive. Relay is designed so the safe path is the only path.
              </p>
            </div>
            <dl className="grid gap-6 sm:grid-cols-2">
              {PRINCIPLES.map(([title, text]) => (
                <div key={title} className="border-l pl-4">
                  <dt className="font-medium">{title}</dt>
                  <dd className="text-muted-foreground mt-1 text-sm">{text}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section>
          <div className="mx-auto flex max-w-6xl flex-col items-start gap-5 px-4 py-20 sm:px-6">
            <h2 className="max-w-2xl text-3xl font-semibold tracking-tight">
              Start with one handover. Keep the habit.
            </h2>
            <Suspense fallback={null}>
              <PrimaryAction />
            </Suspense>
          </div>
        </section>
      </main>

      <footer className="border-t">
        <div className="text-muted-foreground mx-auto flex max-w-6xl flex-wrap gap-4 px-4 py-6 text-xs sm:px-6">
          <span>Relay</span>
          <span className="flex-1" />
          <span>Read-only integrations by default · Human approval for every change</span>
        </div>
      </footer>
    </div>
  );
}

async function PrimaryAction({ compact = false }: { compact?: boolean }) {
  // withAuth reads the clock for token expiry: render this part at request time.
  await connection();
  const { user } = await withAuth();
  const className = compact
    ? "bg-primary text-primary-foreground inline-flex h-8 items-center rounded-lg px-3 text-sm font-medium"
    : "bg-primary text-primary-foreground inline-flex h-10 items-center rounded-lg px-5 text-sm font-medium shadow-sm transition-transform hover:-translate-y-px";
  if (user) {
    return (
      <Link href="/workspaces" className={className}>
        {compact ? "Open Relay" : "Go to your workspaces →"}
      </Link>
    );
  }
  // A plain link (not prefetched) so navigation, not prefetching, starts sign-in.
  return (
    <a href="/sign-in" className={className}>
      {compact ? "Sign in" : "Get started →"}
    </a>
  );
}
