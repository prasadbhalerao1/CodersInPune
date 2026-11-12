import { ApiErrorNotice } from "@/components/api-error-notice";
import { Profile } from "@/components/profile";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

export default async function Page({ params }: PageProps<"/w/[workspaceId]/people/[personId]">) {
  const { workspaceId, personId } = await params;
  const [profile, workspace] = await Promise.all([
    attempt(api.profile(workspaceId, "people", personId)),
    attempt(api.getWorkspace(workspaceId)),
  ]);
  if (!profile.ok) return <ApiErrorNotice error={profile.error} />;
  const canSimulate =
    workspace.ok && ["owner", "admin", "continuity_manager"].includes(workspace.data.role);
  return <Profile workspaceId={workspaceId} p={profile.data} canSimulate={canSimulate} />;
}
