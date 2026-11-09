import { ApiErrorNotice } from "@/components/api-error-notice";
import { Profile } from "@/components/profile";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

export default async function Page({ params }: PageProps<"/w/[workspaceId]/people/[personId]">) {
  const { workspaceId, personId } = await params;
  const profile = await attempt(api.profile(workspaceId, "people", personId));
  if (!profile.ok) return <ApiErrorNotice error={profile.error} />;
  return <Profile workspaceId={workspaceId} p={profile.data} />;
}
