import type { Metadata } from "next";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { PageHeader } from "@/components/page";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

import { createResponsibilityAction } from "../../actions";
import { ResponsibilityForm } from "../responsibility-form";

export const metadata: Metadata = { title: "New responsibility" };

export default async function NewResponsibilityPage({
  params,
}: PageProps<"/w/[workspaceId]/responsibilities/new">) {
  const { workspaceId } = await params;
  const [types, people] = await Promise.all([
    attempt(api.responsibilityTypes(workspaceId)),
    attempt(api.listPeople(workspaceId)),
  ]);
  if (!types.ok) return <ApiErrorNotice error={types.error} />;
  if (!people.ok) return <ApiErrorNotice error={people.error} />;
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="New responsibility" />
      <div className="p-6">
        <ResponsibilityForm
          action={createResponsibilityAction.bind(null, workspaceId)}
          submitLabel="Create responsibility"
          types={types.data}
          people={people.data}
        />
      </div>
    </div>
  );
}
