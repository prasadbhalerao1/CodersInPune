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
        description="Ask anything about this workspace. Answers come only from records you can open, and cite each one."
      />
      <div className="mx-auto w-full max-w-4xl p-6">
        <AskRelay workspaceId={workspaceId} />
      </div>
    </div>
  );
}
