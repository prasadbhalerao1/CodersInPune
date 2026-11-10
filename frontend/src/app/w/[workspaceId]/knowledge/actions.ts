"use server";

import { refresh, revalidatePath } from "next/cache";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";

const text = (fd: FormData, key: string) => String(fd.get(key) ?? "").trim();
const optional = (fd: FormData, key: string) => text(fd, key) || undefined;

async function mutate(workspaceId: string, run: () => Promise<unknown>): Promise<ActionState> {
  try {
    await run();
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  refresh(); // re-render the current route; data is never cached
  return {};
}

export async function addKnowledgeAction(
  workspaceId: string,
  responsibilityId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  if (!optional(fd, "body") && !optional(fd, "url")) {
    return { error: "Add a link or write the content." };
  }
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/responsibilities/${responsibilityId}/knowledge`, {
      kind: text(fd, "kind") || "note",
      title: text(fd, "title"),
      body: optional(fd, "body"),
      url: optional(fd, "url"),
      visibility: text(fd, "visibility") || "workspace",
    }),
  );
}

export async function reviewKnowledgeAction(
  workspaceId: string,
  itemId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () => api.send(workspaceId, "POST", `/knowledge/${itemId}/review`));
}

export async function archiveKnowledgeAction(
  workspaceId: string,
  itemId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/knowledge/${itemId}`, { status: "archived" }),
  );
}

export async function recordHandoverAction(
  workspaceId: string,
  caseId: string,
  responsibilityId: string,
  outcome: "handed_over" | "missing",
  knowledgeItemId: string | null,
  _state: ActionState,
  fd?: FormData,
): Promise<ActionState> {
  const note = fd ? optional(fd, "note") : undefined;
  if (outcome === "missing" && !note) return { error: "Describe what is missing." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/cases/${caseId}/knowledge`, {
      responsibility_id: responsibilityId,
      outcome,
      knowledge_item_id: knowledgeItemId ?? undefined,
      note,
    }),
  );
}

export async function disputeKnowledgeAction(
  workspaceId: string,
  itemId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const reason = String(fd.get("reason") ?? "").trim();
  if (!reason) return { error: "Say what is wrong." };
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/knowledge/${itemId}/dispute`, { reason }),
  );
}

export async function knowledgeFeedbackAction(
  workspaceId: string,
  itemId: string,
  kind: "stale" | "authoritative",
  _state: ActionState,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/knowledge/${itemId}/feedback`, { kind }),
  );
}

export async function updateKnowledgeAction(
  workspaceId: string,
  itemId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const nullable = (key: string) => optional(fd, key) ?? null;
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/knowledge/${itemId}`, {
      title: text(fd, "title"),
      body: text(fd, "body"),
      change_note: nullable("change_note"),
      steward_user_id: nullable("steward_user_id"),
      valid_until: nullable("valid_until"),
      applies_to: text(fd, "applies_to"),
      decision_rationale: text(fd, "decision_rationale"),
      decision_approver: nullable("decision_approver"),
      superseded_by_id: nullable("superseded_by_id"),
    }),
  );
}
