"use server";

import { refresh, revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import type { ActionState } from "@/lib/action-state";
import { api, RelayApiError } from "@/lib/relay-api";
import type { AnswerView, CapsuleView } from "@/lib/types";

async function mutate(workspaceId: string, run: () => Promise<unknown>): Promise<ActionState> {
  try {
    await run();
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  refresh();
  return {};
}

const text = (fd: FormData, name: string) => String(fd.get(name) ?? "").trim();

export async function analyseCaseAction(workspaceId: string, caseId: string): Promise<ActionState> {
  return mutate(workspaceId, () => api.send(workspaceId, "POST", `/cases/${caseId}/analysis`));
}

export async function cancelRunAction(workspaceId: string, runId: string): Promise<ActionState> {
  return mutate(workspaceId, () => api.send(workspaceId, "POST", `/ai/runs/${runId}/cancel`));
}

export async function reviewClaimAction(
  workspaceId: string,
  claimId: string,
  status: "accepted" | "rejected" | "unreviewed",
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/ai/claims/${claimId}`, { review_status: status }),
  );
}

export async function acceptProposalAction(
  workspaceId: string,
  proposalId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const title = text(fd, "title");
  const detail = fd.has("detail") ? text(fd, "detail") : undefined;
  const edit = fd.get("edited") === "1" ? { title: title || undefined, detail } : undefined;
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/ai/proposals/${proposalId}/accept`, edit),
  );
}

export async function rejectProposalAction(
  workspaceId: string,
  proposalId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/ai/proposals/${proposalId}/reject`, {
      reason: text(fd, "reason") || null,
    }),
  );
}

export async function generateInterviewAction(
  workspaceId: string,
  caseId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () => api.send(workspaceId, "POST", `/cases/${caseId}/interview`));
}

export async function answerQuestionAction(
  workspaceId: string,
  questionId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  const status = text(fd, "status") || "answered";
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/ai/questions/${questionId}`, {
      status,
      answer: status === "answered" ? text(fd, "answer") : null,
    }),
  );
}

export async function reviewQuestionAction(
  workspaceId: string,
  questionId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/ai/questions/${questionId}/review`),
  );
}

export async function questionToKnowledgeAction(
  workspaceId: string,
  questionId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/ai/questions/${questionId}/to-knowledge`),
  );
}

export async function generateCapsuleAction(
  workspaceId: string,
  caseId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  let capsule: CapsuleView;
  try {
    capsule = await api.send<CapsuleView>(workspaceId, "POST", `/cases/${caseId}/capsules`, {
      recipient_user_id: text(fd, "recipient_user_id"),
    });
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
  revalidatePath(`/w/${workspaceId}`, "layout");
  redirect(`/w/${workspaceId}/cases/${caseId}/capsules/${capsule.id}`);
}

export async function editCapsuleAction(
  workspaceId: string,
  capsuleId: string,
  _state: ActionState,
  fd: FormData,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "PATCH", `/ai/capsules/${capsuleId}`, {
      redactions: fd.getAll("redacted").map(String),
      summary: fd.has("summary") ? text(fd, "summary") : undefined,
    }),
  );
}

export async function approveCapsuleAction(
  workspaceId: string,
  capsuleId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/ai/capsules/${capsuleId}/approve`),
  );
}

export async function acknowledgeCapsuleAction(
  workspaceId: string,
  capsuleId: string,
): Promise<ActionState> {
  return mutate(workspaceId, () =>
    api.send(workspaceId, "POST", `/ai/capsules/${capsuleId}/acknowledge`),
  );
}

export type AskState = { answer?: AnswerView; error?: string };

export async function askCapsuleAction(
  workspaceId: string,
  capsuleId: string,
  _state: AskState,
  fd: FormData,
): Promise<AskState> {
  const question = text(fd, "question");
  if (question.length < 3) return { error: "Ask a question of at least a few words." };
  try {
    return { answer: await api.askCapsule(workspaceId, capsuleId, question) };
  } catch (error) {
    if (error instanceof RelayApiError) return { error: error.message };
    throw error;
  }
}
