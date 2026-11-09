import type { Metadata } from "next";
import { PageHeader } from "@/components/page";

import { ImportForm } from "./import-form";

export const metadata: Metadata = { title: "Import" };

export default async function ImportPage({ params }: PageProps<"/w/[workspaceId]/import">) {
  const { workspaceId } = await params;
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Import" />
      <div className="flex max-w-4xl flex-col gap-2 p-6">
        <p className="text-muted-foreground mb-4 max-w-prose text-sm">
          Bring your catalogue in from a spreadsheet. Import people first, then responsibilities,
          then ownership. Every file is previewed before anything is written.
        </p>
        <ImportForm workspaceId={workspaceId} />
      </div>
    </div>
  );
}
