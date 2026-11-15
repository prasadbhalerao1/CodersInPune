import { AlertTriangle, Clock, Lock, LogIn, WifiOff } from "lucide-react";
import Link from "next/link";

import { signOutAction } from "@/app/actions";
import { RetryButton } from "@/components/retry-button";
import type { RelayApiError } from "@/lib/relay-api";

const MESSAGES: Record<string, string> = {
  invalid_token: "Relay could not verify your session.",
  unauthenticated: "Relay could not verify your session.",
  forbidden: "You don't have permission to see this.",
  membership_inactive: "Your access to this workspace is no longer active.",
  user_not_provisioned: "You don't have access to this workspace.",
  auth_unavailable: "Sign-in verification is temporarily unavailable.",
  service_unavailable: "Relay can't reach its server right now.",
};

type Kind = "session" | "access" | "busy" | "offline" | "failed";

function kindOf(error: RelayApiError): Kind {
  if (error.status === 401) return "session";
  if (error.status === 403) return "access";
  if (error.status === 429) return "busy";
  if (error.status === 503 || error.code === "service_unavailable") return "offline";
  return "failed";
}

const COPY: Record<Kind, { icon: typeof Lock; title: string; body: string }> = {
  session: {
    icon: LogIn,
    title: "Your session needs a refresh",
    body: "Sign out and back in; you'll land where you were.",
  },
  access: {
    icon: Lock,
    title: "You don't have access to this",
    body: "Relay only shows what your role allows. An owner or admin of this workspace can grant access.",
  },
  busy: {
    icon: Clock,
    title: "Too many requests at once",
    body: "Wait a few seconds and try again. Nothing was changed.",
  },
  offline: {
    icon: WifiOff,
    title: "Relay's server isn't answering",
    body: "This is usually temporary, for example while the server starts up. Nothing was changed.",
  },
  failed: {
    icon: AlertTriangle,
    title: "This couldn't be loaded",
    body: "Something went wrong on our side. Nothing was changed; trying again usually works.",
  },
};

/**
 * An API failure inside a page, explained by what the person can do next. Never shows server
 * details. A 401 here means the API rejected a session the frontend considered valid, so it
 * offers a clean sign-out instead of a retry loop.
 */
export function ApiErrorNotice({ error }: { error: RelayApiError }) {
  const kind = kindOf(error);
  const { icon: Icon, title, body } = COPY[kind];
  const detail = error.code ? MESSAGES[error.code] : undefined;
  return (
    <div role="alert" className="error-notice m-6 flex max-w-xl gap-3 rounded-lg border p-4">
      <span className="bg-muted text-muted-foreground flex size-8 shrink-0 items-center justify-center rounded-md">
        <Icon aria-hidden className="size-4" />
      </span>
      <div className="flex min-w-0 flex-col gap-1 text-sm">
        <p className="font-medium">{title}</p>
        <p className="text-muted-foreground">{detail && kind !== "failed" ? detail : body}</p>
        {detail && kind !== "failed" && detail !== body ? (
          <p className="text-muted-foreground">{body}</p>
        ) : null}
        <div className="mt-2 flex flex-wrap items-center gap-4">
          {kind === "session" ? (
            <form action={signOutAction}>
              <button type="submit" className="font-medium underline underline-offset-2">
                Sign out and sign in again
              </button>
            </form>
          ) : kind === "access" ? (
            <Link href="/workspaces" className="font-medium underline underline-offset-2">
              Your workspaces
            </Link>
          ) : (
            <RetryButton />
          )}
          {error.status >= 500 ? (
            <span className="text-muted-foreground text-xs">Error {error.status}</span>
          ) : null}
        </div>
      </div>
    </div>
  );
}
