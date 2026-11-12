import type { Metadata } from "next";
import Link from "next/link";

import {
  ActionForm,
  DateTimeInput,
  Field,
  inputClass,
  SubmitButton,
} from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { PageHeader } from "@/components/page";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { CaseType } from "@/lib/types";
import { cn } from "@/lib/utils";

import { createCaseAction, requestCoverAction } from "../actions";
import { CASE_TYPES, PRIORITY_LABEL } from "../labels";

export const metadata: Metadata = { title: "New case" };

const isCaseType = (value: unknown): value is CaseType =>
  typeof value === "string" && value in CASE_TYPES;

export default async function NewCasePage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/cases/new">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const type = isCaseType(query.type) ? query.type : null;
  // Members request cover for their own absence; a manager activates it.
  const request = query.request === "1" && type === "coverage";
  const base = `/w/${workspaceId}/cases/new`;

  if (!type) {
    return (
      <div className="flex flex-1 flex-col">
        <PageHeader title="New case" />
        <div className="grid max-w-5xl gap-4 p-6 md:grid-cols-3">
          {(Object.keys(CASE_TYPES) as CaseType[]).map((t) => (
            <Link
              key={t}
              href={`${base}?type=${t}`}
              className="hover:border-foreground/25 rounded-lg border p-4 transition-colors"
            >
              <p className="text-sm font-medium">{CASE_TYPES[t].label}</p>
              <p className="text-muted-foreground mt-1 text-xs">{CASE_TYPES[t].description}</p>
            </Link>
          ))}
        </div>
      </div>
    );
  }

  const needsPerson = type === "coverage" || type === "departure" || type === "onboarding";
  const showPerson = needsPerson || type === "project_handover";
  const [people, members, assets] = await Promise.all([
    showPerson ? attempt(api.listPeople(workspaceId)) : null,
    attempt(api.members(workspaceId)),
    type === "project_handover" ? attempt(api.assets(workspaceId, { status: "active" })) : null,
  ]);
  for (const r of [people, members, assets]) {
    if (r && !r.ok) return <ApiErrorNotice error={r.error} />;
  }
  const personLabel = {
    coverage: "Who is away",
    departure: "Who is leaving",
    onboarding: "Who is joining (or taking on new work)",
    project_handover: "Outgoing project lead (optional)",
    transfer: "",
  }[type];

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title={CASE_TYPES[type].label} />
      <div className="flex max-w-xl flex-col gap-4 p-6">
        <p className="text-muted-foreground text-sm">{CASE_TYPES[type].description}</p>
        {request ? (
          <p className="text-muted-foreground text-sm">
            This creates a request. A case manager reviews and activates it before anything changes.
          </p>
        ) : null}
        <ActionForm
          action={
            request
              ? requestCoverAction.bind(null, workspaceId)
              : createCaseAction.bind(null, workspaceId, type)
          }
        >
          <Field label="Title" htmlFor="title">
            <input
              id="title"
              name="title"
              required
              maxLength={200}
              className={inputClass}
              placeholder={type === "coverage" ? "Asha on leave" : "Platform handover"}
            />
          </Field>
          {assets?.ok ? (
            <Field label="Project" htmlFor="project">
              <select id="project" name="project_asset_id" defaultValue="" className={inputClass}>
                <option value="">No project asset (add responsibilities by hand)</option>
                {assets.data.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} · {a.asset_type.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </Field>
          ) : null}
          {people?.ok ? (
            <Field label={personLabel} htmlFor="person">
              <select
                id="person"
                name="affected_person_id"
                required={needsPerson}
                defaultValue={
                  typeof query.person === "string" && people.data.some((p) => p.id === query.person)
                    ? query.person
                    : ""
                }
                className={inputClass}
              >
                <option value="" disabled={needsPerson}>
                  {people.data.length ? "Choose a person…" : "Add people first"}
                </option>
                {people.data.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name}
                  </option>
                ))}
              </select>
            </Field>
          ) : null}
          <div className={cn("grid gap-3", type === "coverage" && "sm:grid-cols-2")}>
            <Field
              label={type === "coverage" ? "Coverage starts" : "Effective from (defaults to now)"}
              htmlFor="starts"
            >
              <DateTimeInput id="starts" name="starts_at" />
            </Field>
            {type === "coverage" ? (
              <Field label="Expected return" htmlFor="ends">
                <DateTimeInput id="ends" name="ends_at" />
              </Field>
            ) : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Priority" htmlFor="priority">
              <select id="priority" name="priority" defaultValue="normal" className={inputClass}>
                {Object.entries(PRIORITY_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Case due (optional)" htmlFor="due">
              <DateTimeInput id="due" name="due_at" />
            </Field>
            <Field label="Accountable manager (optional)" htmlFor="accountable">
              <select
                id="accountable"
                name="accountable_manager_user_id"
                defaultValue=""
                className={inputClass}
              >
                <option value="">Not set</option>
                {members?.ok
                  ? members.data
                      .filter((m) => m.status === "active")
                      .map((m) => (
                        <option key={m.user_id} value={m.user_id}>
                          {m.name}
                        </option>
                      ))
                  : null}
              </select>
            </Field>
            <Field label="Time zone" htmlFor="tz">
              <input
                id="tz"
                name="time_zone"
                defaultValue="UTC"
                maxLength={64}
                placeholder="e.g. Asia/Kolkata"
                className={inputClass}
              />
            </Field>
          </div>
          <Field label="Reason (optional)" htmlFor="reason">
            <textarea
              id="reason"
              name="reason"
              rows={3}
              maxLength={4000}
              className={`${inputClass} h-auto py-2`}
            />
          </Field>
          {type === "coverage" || type === "departure" ? (
            <p className="text-muted-foreground text-xs">
              Relay will add every responsibility this person currently owns. You choose a recipient
              for each.
            </p>
          ) : type === "onboarding" ? (
            <p className="text-muted-foreground text-xs">
              Add the responsibilities they will take on; each is planned with them as the
              recipient, plus access and readiness checks.
            </p>
          ) : type === "project_handover" ? (
            <p className="text-muted-foreground text-xs">
              Relay adds the responsibilities that steward the project. Decisions, open work and
              knowledge come with them in the case analysis and handover capsule.
            </p>
          ) : null}
          <details className="text-sm">
            <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-xs">
              A similar case is already open?
            </summary>
            <Field
              label="Why a separate case is needed (only if Relay reports a similar open case)"
              htmlFor="dup"
            >
              <input
                id="dup"
                name="duplicate_override_reason"
                maxLength={4000}
                className={inputClass}
              />
            </Field>
          </details>
          <div className="flex gap-2">
            <SubmitButton>Create case</SubmitButton>
            <Link href={base} className="text-muted-foreground self-center text-sm hover:underline">
              Change case type
            </Link>
          </div>
        </ActionForm>
      </div>
    </div>
  );
}
