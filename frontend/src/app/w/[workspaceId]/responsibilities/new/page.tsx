import type { Metadata } from "next";
import { PageHeader } from "@/components/page";

import { createResponsibilityAction } from "../../actions";
import { ResponsibilityForm } from "../responsibility-form";

export const metadata: Metadata = { title: "New responsibility" };

export default async function NewResponsibilityPage({
  params,
}: PageProps<"/w/[workspaceId]/responsibilities/new">) {
  const { workspaceId } = await params;
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="New responsibility" />
      <div className="p-6">
        <ResponsibilityForm
          action={createResponsibilityAction.bind(null, workspaceId)}
          submitLabel="Create responsibility"
        />
      </div>
    </div>
  );
}
