import { ArrowRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { RelayLines } from "@/components/brand";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar } from "@/components/visual";
import { api, RelayApiError } from "@/lib/relay-api";

import { CreateWorkspaceForm } from "./create-workspace-form";
import { SampleWorkspaceForm } from "./sample-workspace-form";

export const metadata: Metadata = { title: "Workspaces" };

export default function WorkspacesPage() {
  return (
    <div className="flex flex-1 flex-col">
      <section className="relative overflow-hidden border-b">
        <RelayLines className="absolute inset-y-0 right-0 hidden h-full w-[45%] md:block" />
        <div className="relative mx-auto flex w-full max-w-4xl flex-col gap-2 px-6 pt-12 pb-10">
          <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
            Workspaces
          </p>
          <h1 className="font-display text-4xl leading-tight">Where does your work live?</h1>
          <p className="text-muted-foreground max-w-xl text-sm">
            A workspace holds one organisation&apos;s responsibilities, people and handovers. Open
            one you belong to, start a new one, or explore a fully worked sample first.
          </p>
        </div>
      </section>
      <section className="mx-auto grid w-full max-w-4xl gap-8 p-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <Suspense
          fallback={
            <div className="flex flex-col gap-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          }
        >
          <WorkspaceList />
        </Suspense>
        <div className="flex flex-col gap-4">
          <SampleWorkspaceForm idempotencyKey={crypto.randomUUID()} />
          <CreateWorkspaceForm idempotencyKey={crypto.randomUUID()} />
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
      <div className="bg-card/50 flex flex-col justify-center rounded-xl border border-dashed p-8">
        <h2 className="font-display text-2xl">No workspaces yet</h2>
        <p className="text-muted-foreground mt-2 max-w-sm text-sm">
          The quickest way to see Relay is the sample organisation: a team mid-handover, with a year
          of history and a handover waiting for you. Or create your own and you will be its owner.
        </p>
      </div>
    );
  }
  return (
    <ul className="motion-stagger flex flex-col gap-2" aria-label="Your workspaces">
      {workspaces.map((workspace) => (
        <li key={workspace.id}>
          <Link
            href={`/w/${workspace.id}`}
            className="bg-card lift group flex items-center gap-3 rounded-xl border px-4 py-3.5 shadow-xs"
          >
            <Avatar name={workspace.name} size="lg" className="rounded-lg" />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{workspace.name}</span>
              <span className="text-muted-foreground block text-xs capitalize">
                {workspace.role.replace("_", " ")}
              </span>
            </span>
            <ArrowRight
              aria-hidden
              className="text-muted-foreground size-4 transition-transform group-hover:translate-x-0.5"
            />
          </Link>
        </li>
      ))}
    </ul>
  );
}
