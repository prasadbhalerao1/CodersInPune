import type { Metadata } from "next";
import Link from "next/link";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { explainRunError, RunStateBadge } from "@/components/ai";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { setAiEnabledAction, setBudgetAction, setCapabilityAction } from "./actions";

export const metadata: Metadata = { title: "Agents" };

const PROVIDER = { gemini: "Gemini", groq: "Groq", ollama: "Ollama (local)", fake: "Test model" };

export default async function AgentsPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/agents">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const selected = typeof query.run === "string" ? query.run : undefined;
  const [workspace, overview, runs, detail] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.aiOverview(workspaceId)),
    attempt(api.aiRuns(workspaceId)),
    selected ? attempt(api.aiRun(workspaceId, selected)) : null,
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!overview.ok) return <ApiErrorNotice error={overview.error} />;
  const o = overview.data;
  const admin = canManage(workspace.data);
  const used = o.monthly_token_budget
    ? Math.min(100, Math.round((o.tokens_this_month / o.monthly_token_budget) * 100))
    : 100;
  const base = `/w/${workspaceId}/agents`;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title="Agents"
        actions={
          admin ? (
            <ActionForm action={setAiEnabledAction.bind(null, workspaceId, !o.enabled)}>
              <SubmitButton
                size="sm"
                variant={o.enabled ? "outline" : "default"}
                pendingLabel="Saving…"
                confirm={
                  o.enabled
                    ? "Switch off all AI for this workspace? Rule-based analysis keeps working."
                    : undefined
                }
              >
                {o.enabled ? "Switch off AI" : "Switch on AI"}
              </SubmitButton>
            </ActionForm>
          ) : undefined
        }
      />
      <div className="flex max-w-5xl flex-col gap-8 p-6">
        <p className="text-muted-foreground max-w-2xl text-sm">
          Relay&apos;s AI capabilities only read the evidence a run was allowed to see and only
          produce proposals: none of them can change anything. People review every suggestion.
        </p>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-lg border p-4 text-sm">
            <p className="text-muted-foreground text-xs">Status</p>
            <p className="mt-1 flex flex-wrap items-center gap-2 font-medium">
              {!o.configured ? (
                <Badge tone="muted">No model configured</Badge>
              ) : o.enabled ? (
                <Badge>On</Badge>
              ) : (
                <Badge tone="warning">Switched off</Badge>
              )}
            </p>
          </div>
          <div className="rounded-lg border p-4 text-sm">
            <p className="text-muted-foreground text-xs">Model providers, in order</p>
            <p className="mt-1 font-medium">
              {o.providers.length
                ? o.providers.map((p) => PROVIDER[p as keyof typeof PROVIDER] ?? p).join(" → ")
                : "None"}
            </p>
            {o.providers.includes("gemini") ? (
              <p className="text-muted-foreground text-xs">
                {o.gemini_keys} Gemini key{o.gemini_keys === 1 ? "" : "s"}: rotates when one runs
                out of quota
              </p>
            ) : null}
          </div>
          <div className="rounded-lg border p-4 text-sm">
            <p className="text-muted-foreground text-xs">Tokens this month</p>
            <p className="mt-1 font-medium tabular-nums">
              {o.tokens_this_month.toLocaleString()} / {o.monthly_token_budget.toLocaleString()}
            </p>
            <div className="bg-muted mt-2 h-1.5 rounded-full" aria-hidden>
              <div
                className={cn("h-1.5 rounded-full", used >= 90 ? "bg-red-600" : "bg-foreground")}
                style={{ width: `${used}%` }}
              />
            </div>
            {admin ? (
              <ActionForm
                action={setBudgetAction.bind(null, workspaceId)}
                className="mt-3 flex-row items-center"
              >
                <input
                  name="monthly_token_budget"
                  type="number"
                  min={0}
                  step={1000}
                  defaultValue={o.monthly_token_budget}
                  aria-label="Monthly token budget"
                  className={cn(inputClass, "h-8")}
                />
                <SubmitButton size="sm" variant="outline" pendingLabel="…">
                  Set
                </SubmitButton>
              </ActionForm>
            ) : null}
          </div>
        </div>
        {!o.configured ? (
          <p className="text-muted-foreground text-xs">
            Set RELAY_LLM_PROVIDERS (and RELAY_GEMINI_KEY_1…4, RELAY_GROQ_API_KEY or
            RELAY_OLLAMA_MODEL) on the server to turn on AI. Rule-based analysis, interviews and
            capsules work without it.
          </p>
        ) : null}

        <Section
          title="Capabilities"
          description="Each is narrow, versioned and read-only. Acceptance shows how useful its suggestions are."
        >
          <ul className="divide-y rounded-lg border">
            {o.capabilities.map((c) => {
              const reviewed = c.accepted + c.rejected;
              return (
                <li key={c.name} className="flex flex-wrap items-start gap-4 px-4 py-3 text-sm">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2 font-medium">
                      {c.title}
                      <span className="text-muted-foreground text-xs font-normal">
                        v{c.version}
                      </span>
                      {!c.enabled ? <Badge tone="muted">Off</Badge> : null}
                    </p>
                    <p className="text-muted-foreground">{c.description}</p>
                    <p className="text-muted-foreground mt-1 text-xs">
                      Read-only tools: {c.tools.join(", ")} · budget{" "}
                      {c.token_budget.toLocaleString()} tokens · {c.timeout_seconds}s limit
                    </p>
                  </div>
                  <div className="text-muted-foreground w-40 text-xs tabular-nums">
                    {reviewed
                      ? `${Math.round((c.accepted / reviewed) * 100)}% accepted (${c.accepted}/${reviewed})`
                      : "No reviewed proposals"}
                    {c.pending ? <span className="block">{c.pending} pending</span> : null}
                  </div>
                  {admin ? (
                    <ActionForm
                      action={setCapabilityAction.bind(null, workspaceId, c.name, !c.enabled)}
                    >
                      <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                        {c.enabled ? "Turn off" : "Turn on"}
                      </SubmitButton>
                    </ActionForm>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </Section>

        <Section
          title="Recent runs"
          description="Identifiers and metrics only; prompts are never stored."
        >
          {!runs.ok ? (
            <ApiErrorNotice error={runs.error} />
          ) : runs.data.length === 0 ? (
            <EmptyState title="No runs yet" description="Analyse a case to start one." />
          ) : (
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full text-sm">
                <thead className="text-muted-foreground text-left text-xs">
                  <tr className="border-b">
                    <th className="px-3 py-2 font-medium">Run</th>
                    <th className="px-3 py-2 font-medium">State</th>
                    <th className="px-3 py-2 font-medium">Model</th>
                    <th className="px-3 py-2 text-right font-medium">Tokens</th>
                    <th className="px-3 py-2 text-right font-medium">Time</th>
                    <th className="px-3 py-2 font-medium">Started</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {runs.data.map((r) => (
                    <tr key={r.id} className={cn(r.id === selected && "bg-muted/40")}>
                      <td className="px-3 py-2">
                        <Link
                          href={`${base}?run=${r.id}`}
                          className="underline-offset-2 hover:underline"
                        >
                          {r.capability.replaceAll("_", " ")}
                        </Link>
                        {r.case_id ? (
                          <Link
                            href={`/w/${workspaceId}/cases/${r.case_id}`}
                            className="text-muted-foreground ml-2 text-xs hover:underline"
                          >
                            case
                          </Link>
                        ) : null}
                      </td>
                      <td className="px-3 py-2">
                        <RunStateBadge state={r.state} />
                      </td>
                      <td className="text-muted-foreground px-3 py-2 text-xs">
                        {r.provider
                          ? `${r.provider}${r.key_index !== null ? ` #${r.key_index + 1}` : ""}`
                          : r.ai === "on"
                            ? "—"
                            : "rules only"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {(r.input_tokens + r.output_tokens).toLocaleString()}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {(r.duration_ms / 1000).toFixed(1)}s
                      </td>
                      <td className="text-muted-foreground px-3 py-2 text-xs">
                        {formatDateTime(r.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        {detail ? (
          !detail.ok ? (
            <ApiErrorNotice error={detail.error} />
          ) : (
            <Section title="Run events" description={`Run ${detail.data.id}`}>
              {explainRunError(detail.data.error_code) ? (
                <p className="text-sm text-red-700 dark:text-red-300">
                  {explainRunError(detail.data.error_code)}
                </p>
              ) : null}
              <ol className="divide-y rounded-lg border text-sm">
                {detail.data.events.map((e, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-3 px-4 py-2">
                    <Badge
                      tone={
                        e.level === "error" ? "danger" : e.level === "warning" ? "warning" : "muted"
                      }
                    >
                      {e.step.replaceAll("_", " ")}
                    </Badge>
                    <span className="font-medium">{e.code.replaceAll("_", " ")}</span>
                    <span className="text-muted-foreground min-w-0 flex-1 truncate text-xs">
                      {Object.entries(e.detail)
                        .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
                        .join(" · ")}
                    </span>
                    <span className="text-muted-foreground text-xs">
                      {formatDateTime(e.created_at)}
                    </span>
                  </li>
                ))}
              </ol>
            </Section>
          )
        ) : null}
      </div>
    </div>
  );
}
