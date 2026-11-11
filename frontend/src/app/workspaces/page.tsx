import Link from "next/link";
import { Suspense } from "react";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { api, RelayApiError } from "@/lib/relay-api";

import { CreateWorkspaceForm } from "./create-workspace-form";
import { SampleWorkspaceForm } from "./sample-workspace-form";

export default function WorkspacesPage() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="flex h-14 items-center border-b px-6">
        <h1 className="text-base font-semibold">Workspaces</h1>
      </header>
      <section className="mx-auto flex w-full max-w-2xl flex-col gap-8 p-6">
        <Suspense fallback={<p className="text-muted-foreground text-sm">Loading workspaces…</p>}>
          <WorkspaceList />
        </Suspense>
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
  return (
    <>
      {workspaces.length === 0 ? (
        <div>
          <h2 className="font-semibold">Create your first workspace</h2>
          <p className="text-muted-foreground mt-1 text-sm">
            A workspace holds your organisation&apos;s responsibilities and continuity work. You
            will be its owner.
          </p>
        </div>
      ) : (
        <ul className="divide-y rounded-lg border" aria-label="Your workspaces">
          {workspaces.map((workspace) => (
            <li key={workspace.id}>
              <Link
                href={`/w/${workspace.id}`}
                className="hover:bg-muted flex items-center justify-between px-4 py-3 text-sm"
              >
                <span className="font-medium">{workspace.name}</span>
                <span className="text-muted-foreground capitalize">{workspace.role}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <CreateWorkspaceForm idempotencyKey={crypto.randomUUID()} />
      <SampleWorkspaceForm idempotencyKey={crypto.randomUUID()} />
    </>
  );
}
