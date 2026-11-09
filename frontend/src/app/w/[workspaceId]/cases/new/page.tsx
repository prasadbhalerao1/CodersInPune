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

import { createCaseAction } from "../actions";
import { CASE_TYPES } from "../labels";

export const metadata: Metadata = { title: "New case" };

const isCaseType = (value: unknown): value is CaseType =>
  typeof value === "string" && value in CASE_TYPES;

export default async function NewCasePage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/cases/new">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const type = isCaseType(query.type) ? query.type : null;
  const base = `/w/${workspaceId}/cases/new`;

  if (!type) {
    return (
      <div className="flex flex-1 flex-col">
        <PageHeader title="New case" />
        <div className="grid max-w-4xl gap-4 p-6 md:grid-cols-3">
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

  const needsPerson = type !== "transfer";
  const people = needsPerson ? await attempt(api.listPeople(workspaceId)) : null;
  if (people && !people.ok) return <ApiErrorNotice error={people.error} />;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title={CASE_TYPES[type].label} />
      <div className="flex max-w-xl flex-col gap-4 p-6">
        <p className="text-muted-foreground text-sm">{CASE_TYPES[type].description}</p>
        <ActionForm action={createCaseAction.bind(null, workspaceId, type)}>
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
          {people?.ok ? (
            <Field label={type === "coverage" ? "Who is away" : "Who is leaving"} htmlFor="person">
              <select
                id="person"
                name="affected_person_id"
                required
                defaultValue=""
                className={inputClass}
              >
                <option value="" disabled>
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
          <Field label="Reason (optional)" htmlFor="reason">
            <textarea
              id="reason"
              name="reason"
              rows={3}
              maxLength={4000}
              className={`${inputClass} h-auto py-2`}
            />
          </Field>
          {needsPerson ? (
            <p className="text-muted-foreground text-xs">
              Relay will add every responsibility this person currently owns. You choose a recipient
              for each.
            </p>
          ) : null}
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
