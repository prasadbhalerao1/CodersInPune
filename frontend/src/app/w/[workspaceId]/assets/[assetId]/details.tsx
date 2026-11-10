import Link from "next/link";

import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { Section } from "@/components/page";
import { Badge, CriticalityBadge } from "@/components/ui/badge";
import type { AssetDetail, CaseSummary, KnowledgeView } from "@/lib/types";

import { linkAssetTargetAction, unlinkAssetTargetAction, updateAssetAction } from "../actions";
import { fieldLabel, LIFECYCLE_LABEL } from "../labels";

export function AssetFacts({ asset: a }: { asset: AssetDetail }) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {a.criticality ? <CriticalityBadge value={a.criticality} /> : null}
      <Badge tone={a.lifecycle === "active" ? "muted" : "warning"}>
        {LIFECYCLE_LABEL[a.lifecycle]}
      </Badge>
      {a.source_state === "unavailable" ? (
        <Badge tone="warning">
          {a.external_source ? `${a.external_source} source unavailable` : "Source unavailable"}
        </Badge>
      ) : null}
      {a.external_source && a.external_id ? (
        <span className="text-muted-foreground text-xs">
          {a.external_source} · {a.external_id}
        </span>
      ) : null}
      {a.tags.map((t) => (
        <span key={t} className="text-muted-foreground text-xs">
          #{t}
        </span>
      ))}
    </div>
  );
}

export function AssetMetadata({
  workspaceId,
  asset: a,
  manage,
}: {
  workspaceId: string;
  asset: AssetDetail;
  manage: boolean;
}) {
  const filled = a.metadata_fields.filter((f) => a.metadata[f]);
  return (
    <Section title="Details" description="Fields for this kind of asset.">
      {filled.length ? (
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 rounded-lg border p-4 text-sm">
          {filled.map((f) => (
            <div key={f} className="contents">
              <dt className="text-muted-foreground">{fieldLabel(f)}</dt>
              <dd className="min-w-0 truncate">{a.metadata[f]}</dd>
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-muted-foreground text-sm">Nothing recorded yet.</p>
      )}
      {manage ? (
        <details>
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-sm">
            Edit details
          </summary>
          <ActionForm
            action={updateAssetAction.bind(null, workspaceId, a.id, a.metadata_fields)}
            className="mt-2 rounded-lg border p-4"
          >
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Criticality" htmlFor="a-crit">
                <select
                  id="a-crit"
                  name="criticality"
                  defaultValue={a.criticality ?? ""}
                  className={inputClass}
                >
                  <option value="">Not set</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="standard">Standard</option>
                  <option value="low">Low</option>
                </select>
              </Field>
              <Field label="Lifecycle" htmlFor="a-life">
                <select
                  id="a-life"
                  name="lifecycle"
                  defaultValue={a.lifecycle}
                  className={inputClass}
                >
                  {Object.entries(LIFECYCLE_LABEL).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Tags (comma separated)" htmlFor="a-tags">
                <input
                  id="a-tags"
                  name="tags"
                  defaultValue={a.tags.join(", ")}
                  className={inputClass}
                />
              </Field>
              <Field label="External source" htmlFor="a-src">
                <select
                  id="a-src"
                  name="external_source"
                  defaultValue={a.external_source ?? ""}
                  className={inputClass}
                >
                  <option value="">None</option>
                  <option value="github">GitHub</option>
                  <option value="linear">Linear</option>
                  <option value="notion">Notion</option>
                  <option value="manual">Manual</option>
                </select>
              </Field>
              <Field label="External ID" htmlFor="a-ext">
                <input
                  id="a-ext"
                  name="external_id"
                  defaultValue={a.external_id ?? ""}
                  maxLength={200}
                  className={inputClass}
                />
              </Field>
              <Field label="Source" htmlFor="a-state">
                <select
                  id="a-state"
                  name="source_state"
                  defaultValue={a.source_state}
                  className={inputClass}
                >
                  <option value="available">Available</option>
                  <option value="unavailable">Unavailable</option>
                </select>
              </Field>
              {a.metadata_fields.map((f) => (
                <Field key={f} label={fieldLabel(f)} htmlFor={`meta-${f}`}>
                  <input
                    id={`meta-${f}`}
                    name={`meta_${f}`}
                    defaultValue={a.metadata[f] ?? ""}
                    maxLength={300}
                    className={inputClass}
                  />
                </Field>
              ))}
            </div>
            <SubmitButton size="sm" pendingLabel="Saving…">
              Save
            </SubmitButton>
          </ActionForm>
        </details>
      ) : null}
    </Section>
  );
}

const KIND_LABEL = { knowledge: "Knowledge", case: "Case", task: "Task" } as const;

export function AssetLinks({
  workspaceId,
  asset: a,
  manage,
  cases,
  knowledge,
}: {
  workspaceId: string;
  asset: AssetDetail;
  manage: boolean;
  cases: CaseSummary[];
  knowledge: KnowledgeView[];
}) {
  const href = (l: AssetDetail["links"][number]) =>
    l.kind === "knowledge"
      ? `/w/${workspaceId}/knowledge#${l.target_id}`
      : l.kind === "case"
        ? `/w/${workspaceId}/cases/${l.target_id}`
        : `/w/${workspaceId}/cases/${l.case_id}/tasks/${l.target_id}`;
  return (
    <Section
      title="Linked work and knowledge"
      description="Knowledge, cases and tasks about this asset."
    >
      {a.links.length ? (
        <ul className="divide-y rounded-lg border text-sm">
          {a.links.map((l) => (
            <li key={l.id} className="flex items-center gap-3 px-4 py-2.5">
              <Badge tone="muted">{KIND_LABEL[l.kind]}</Badge>
              <Link
                href={href(l)}
                className="min-w-0 flex-1 truncate underline-offset-2 hover:underline"
              >
                {l.title}
              </Link>
              <span className="text-muted-foreground text-xs">{l.status.replaceAll("_", " ")}</span>
              {manage ? (
                <ActionForm action={unlinkAssetTargetAction.bind(null, workspaceId, a.id, l.id)}>
                  <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                    Unlink
                  </SubmitButton>
                </ActionForm>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground text-sm">Nothing linked yet.</p>
      )}
      {manage ? (
        <ActionForm
          action={linkAssetTargetAction.bind(null, workspaceId, a.id)}
          className="flex-row items-end gap-2"
        >
          <select name="target" defaultValue="" aria-label="Link to" className={inputClass}>
            <option value="">Link a case or knowledge…</option>
            <optgroup label="Cases">
              {cases.map((c) => (
                <option key={c.id} value={`case:${c.id}`}>
                  {c.title}
                </option>
              ))}
            </optgroup>
            <optgroup label="Knowledge">
              {knowledge.map((k) => (
                <option key={k.id} value={`knowledge:${k.id}`}>
                  {k.title}
                </option>
              ))}
            </optgroup>
          </select>
          <SubmitButton size="sm" variant="outline" pendingLabel="…">
            Link
          </SubmitButton>
        </ActionForm>
      ) : null}
      {a.dependents.length ? (
        <p className="text-sm">
          <span className="text-muted-foreground">Relied on by: </span>
          {a.dependents.map((r, i) => (
            <span key={r.id}>
              {i ? ", " : ""}
              <Link
                href={`/w/${workspaceId}/responsibilities/${r.id}`}
                className="underline-offset-2 hover:underline"
              >
                {r.name}
              </Link>
            </span>
          ))}
        </p>
      ) : null}
    </Section>
  );
}
