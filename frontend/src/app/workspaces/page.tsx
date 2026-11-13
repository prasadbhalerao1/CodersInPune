import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { RelayLines } from "@/components/brand";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar } from "@/components/visual";
import { api, RelayApiError } from "@/lib/relay-api";

import { CreateWorkspaceForm } from "./create-workspace-form";
import { SampleWorkspaceForm } from "./sample-workspace-form";

export const metadata: Metadata = { title: "Workspaces" };

// Each render gets fresh idempotency keys, so it must happen per request, not at build time.
async function WorkspaceForms() {
  await connection();
  return (
    <>
      <SampleWorkspaceForm idempotencyKey={crypto.randomUUID()} />
      <CreateWorkspaceForm idempotencyKey={crypto.randomUUID()} />
    </>
  );
}

export default function WorkspacesPage() {
  return (
    <div className="bg-page text-strong flex flex-1 flex-col">
      <section className="border-line/[0.08] from-card to-page relative overflow-hidden border-b bg-gradient-to-b">
        <RelayLines className="absolute inset-y-0 right-0 hidden h-full w-[45%] opacity-20 md:block" />
        <div className="relative mx-auto flex w-full max-w-5xl flex-col gap-3 px-6 pt-16 pb-12">
          <div className="flex items-center gap-2">
            <span className="jewel-emerald" />
            <p className="font-mono text-xs tracking-widest text-emerald-400 uppercase">
              SOVEREIGN DOMAINS // WORKSPACES
            </p>
          </div>
          <h1 className="font-syne text-strong text-4xl font-extrabold tracking-tight sm:text-5xl">
            WHERE DOES YOUR WORK LIVE?
          </h1>
          <p className="text-fg-mute max-w-xl text-sm leading-relaxed">
            A workspace encapsulates an organization&apos;s responsibilities, cryptographic access
            controls, absence blast radii, and audited continuity handovers.
          </p>
        </div>
      </section>
      <section className="mx-auto grid w-full max-w-5xl gap-8 p-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Suspense
          fallback={
            <div className="flex flex-col gap-3">
              <Skeleton className="bg-line/5 h-20 w-full rounded-2xl" />
              <Skeleton className="bg-line/5 h-20 w-full rounded-2xl" />
            </div>
          }
        >
          <WorkspaceList />
        </Suspense>
        <div className="flex flex-col gap-5">
          <Suspense fallback={<Skeleton className="bg-line/5 h-44 w-full rounded-2xl" />}>
            <WorkspaceForms />
          </Suspense>
        </div>
      </section>
    </div>
  );
}

async function WorkspaceList() {
  let workspaces;
  try {
    workspaces = await api.listWorkspaces();
  } catch (error) {
    if (error instanceof RelayApiError) return <ApiErrorNotice error={error} />;
    throw error;
  }
  if (workspaces.length === 0) {
    return (
      <div className="border-line/15 bg-card/60 flex flex-col justify-center rounded-2xl border border-dashed p-8 text-left">
        <span className="text-ac font-mono text-xs tracking-wider uppercase">TENANT DISCOVERY</span>
        <h2 className="font-syne text-strong mt-1 text-2xl font-bold">No Active Workspaces Yet</h2>
        <p className="text-fg-mute mt-2 max-w-md text-xs leading-relaxed">
          The fastest way to test Relay&apos;s continuity engine is staging the demo workspace: a
          complete team mid-handover, with live absence blast radius simulations and pending audit
          acknowledgements.
        </p>
      </div>
    );
  }
  return (
    <ul className="motion-stagger flex flex-col gap-3" aria-label="Your workspaces">
      {workspaces.map((workspace) => (
        <li key={workspace.id}>
          <Link
            href={`/w/${workspace.id}`}
            className="group border-line/10 bg-card hover:border-ac/40 flex items-center gap-4 rounded-2xl border px-5 py-4 shadow-lg transition-all hover:bg-[#131722]"
          >
            <Avatar name={workspace.name} size="lg" className="border-line/15 rounded-xl border" />
            <span className="min-w-0 flex-1">
              <span className="text-strong group-hover:text-ac block truncate font-semibold transition-colors">
                {workspace.name}
              </span>
              <span className="text-fg-mute font-mono text-[11px] capitalize">
                ROLE: {workspace.role.replace("_", " ")}
              </span>
            </span>
            <div className="border-line/10 bg-line/[0.04] text-fg-mute group-hover:text-ac group-hover:border-ac/40 flex h-8 w-8 items-center justify-center rounded-full border transition-all">
              <ArrowRight
                aria-hidden
                className="size-4 transition-transform group-hover:translate-x-0.5"
              />
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
