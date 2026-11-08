import { signOutAction } from "@/app/actions";
import type { RelayApiError } from "@/lib/relay-api";

const MESSAGES: Record<string, string> = {
  invalid_token: "Relay could not verify your session.",
  unauthenticated: "Relay could not verify your session.",
  forbidden: "You don't have permission to do this.",
  membership_inactive: "Your access to this workspace is no longer active.",
  user_not_provisioned: "You don't have access to this workspace.",
  auth_unavailable: "Sign-in verification is temporarily unavailable. Try again shortly.",
};

// Shows API failures without leaking server details. A 401 here means the API rejected a
// session the frontend considered valid, so offer a clean sign-out instead of looping.
export function ApiErrorNotice({ error }: { error: RelayApiError }) {
  const message = (error.code && MESSAGES[error.code]) ?? "Something went wrong. Please try again.";
  return (
    <div role="alert" className="m-6 max-w-xl rounded-lg border p-4 text-sm">
      <p className="font-medium">{message}</p>
      {error.status === 401 ? (
        <form action={signOutAction} className="mt-3">
          <button type="submit" className="underline">
            Sign out and sign in again
          </button>
        </form>
      ) : null}
    </div>
  );
}
