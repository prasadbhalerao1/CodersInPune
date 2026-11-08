import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { getWorkspace, RelayApiError } from "@/lib/relay-api";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function WorkspacePage({ params }: PageProps<"/w/[workspaceId]">) {
  return (
    <Suspense fallback={<p className="text-muted-foreground p-6 text-sm">Loading workspace…</p>}>
      <Workspace params={params} />
    </Suspense>
  );
}

async function Workspace({ params }: Pick<PageProps<"/w/[workspaceId]">, "params">) {
  const { workspaceId } = await params;
  if (!UUID.test(workspaceId)) notFound();

  let workspace;
  try {
    workspace = await getWorkspace(workspaceId);
  } catch (error) {
    if (error instanceof RelayApiError && error.status === 404) notFound();
    if (error instanceof RelayApiError) {
      return (
        <div className="p-6">
          <ApiErrorNotice error={error} />
        </div>
      );
    }
    throw error;
  }

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex h-14 items-center justify-between border-b px-6">
        <h1 className="text-base font-semibold">{workspace.name}</h1>
        <Link href="/workspaces" className="text-muted-foreground text-sm hover:underline">
          Switch workspace
        </Link>
      </header>
      <section className="p-6">
        <p className="text-muted-foreground text-sm">
          You are signed in as this workspace&apos;s{" "}
          <span className="text-foreground font-medium">{workspace.role}</span>. Responsibilities
          and continuity features arrive in the next milestones.
        </p>
      </section>
    </div>
  );
}
