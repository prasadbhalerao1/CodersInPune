import { ApiErrorNotice } from "@/components/api-error-notice";
import { PageHeader } from "@/components/page";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

import { updateResponsibilityAction } from "../../../actions";
import { ResponsibilityForm } from "../../responsibility-form";

export default async function EditResponsibilityPage({
  params,
}: PageProps<"/w/[workspaceId]/responsibilities/[responsibilityId]/edit">) {
  const { workspaceId, responsibilityId } = await params;
  const [result, types, people] = await Promise.all([
    attempt(api.getResponsibility(workspaceId, responsibilityId)),
    attempt(api.responsibilityTypes(workspaceId)),
    attempt(api.listPeople(workspaceId)),
  ]);
  if (!result.ok) return <ApiErrorNotice error={result.error} />;
  if (!types.ok) return <ApiErrorNotice error={types.error} />;
  if (!people.ok) return <ApiErrorNotice error={people.error} />;
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title={`Edit ${result.data.name}`} />
      <div className="p-6">
        <ResponsibilityForm
          action={updateResponsibilityAction.bind(null, workspaceId, responsibilityId)}
          initial={result.data}
          submitLabel="Save changes"
          types={types.data}
          people={people.data}
        />
      </div>
    </div>
  );
}
