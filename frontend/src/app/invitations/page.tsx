import { Suspense } from "react";

import { ActionForm, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader } from "@/components/page";
import { PageSkeleton } from "@/components/ui/skeleton";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

import { acceptInvitationAction } from "./actions";

export default function InvitationsPage() {
  return (
    <Suspense fallback={<PageSkeleton rows={2} />}>
      <Invitations />
    </Suspense>
  );
}

async function Invitations() {
  const invitations = await attempt(api.myInvitations());
  if (!invitations.ok) return <ApiErrorNotice error={invitations.error} />;
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Invitations" />
      <div className="flex max-w-2xl flex-col gap-4 p-6">
        {invitations.data.length === 0 ? (
          <EmptyState
            title="No pending invitations"
            description="Invitations sent to your verified email address appear here."
          />
        ) : (
          <ul className="divide-y rounded-lg border">
            {invitations.data.map((i) => (
              <li key={i.id} className="flex items-center gap-3 px-4 py-3 text-sm">
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{i.workspace_name}</span>
                  <span className="text-muted-foreground block text-xs">
                    Join as {i.role} · expires {formatDateTime(i.expires_at)}
                  </span>
                </span>
                <ActionForm action={acceptInvitationAction.bind(null, i.id)}>
                  <SubmitButton size="sm" pendingLabel="Joining…">
                    Accept
                  </SubmitButton>
                </ActionForm>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
