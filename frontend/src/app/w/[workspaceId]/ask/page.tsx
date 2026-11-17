import type { Metadata } from "next";

import { Explain } from "@/components/explain";
import { PageHeader } from "@/components/page";

import { AskRelay } from "./ask-relay";

export const metadata: Metadata = { title: "Ask Relay" };

export default async function AskPage({ params }: PageProps<"/w/[workspaceId]/ask">) {
  const { workspaceId } = await params;
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            Ask Relay <Explain what="ask_relay" align="start" />
          </span>
        }
        description="Your assistant for this workspace. It knows its owners, people, handovers and risks, and cites every fact."
      />
      <div className="mx-auto w-full max-w-4xl p-4 md:p-6">
        <AskRelay workspaceId={workspaceId} />
      </div>
    </div>
  );
}
