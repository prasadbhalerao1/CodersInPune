import type { Metadata } from "next";
import { connection } from "next/server";
import { Suspense } from "react";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { Skeleton } from "@/components/ui/skeleton";
import { api, RelayApiError } from "@/lib/relay-api";

import { CreateWorkspaceForm } from "./create-workspace-form";
import { SampleWorkspaceForm } from "./sample-workspace-form";
import { WorkspaceRows, WorkspacesBackdrop } from "./workspace-list";

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
    <div className="bg-page text-strong relative flex flex-1 flex-col overflow-hidden">
      <WorkspacesBackdrop />
      <section className="relative mx-auto flex w-full max-w-5xl flex-col gap-3 px-6 pt-14 pb-8">
        <p className="text-ac text-[13px] font-medium">Workspaces</p>
        <h1 className="font-display text-strong text-[2.75rem] leading-[0.95] tracking-[-0.01em] sm:text-7xl">
          Where does your work live?
        </h1>
        <p className="text-fg-soft max-w-xl text-sm leading-relaxed">
          A workspace holds one organisation&apos;s responsibilities, who owns them, what is at risk
          when someone is away, and the handovers that keep the work moving.
        </p>
      </section>
      <section className="relative mx-auto grid w-full max-w-5xl gap-6 px-6 pb-12 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Suspense
          fallback={
            <div className="flex flex-col gap-3">
              <Skeleton className="bg-line/5 h-[4.5rem] w-full rounded-[0.875rem]" />
              <Skeleton className="bg-line/5 h-[4.5rem] w-full rounded-[0.875rem]" />
            </div>
          }
        >
          <WorkspaceList />
        </Suspense>
        <div className="flex flex-col gap-5">
          <Suspense fallback={<Skeleton className="bg-line/5 h-44 w-full rounded-[0.875rem]" />}>
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
  return <WorkspaceRows workspaces={workspaces} />;
}
