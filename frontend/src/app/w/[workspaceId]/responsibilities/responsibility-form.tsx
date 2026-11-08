import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import type { ActionState } from "@/lib/action-state";
import type { Criticality, ResponsibilityDetail } from "@/lib/types";

const CRITICALITIES: Criticality[] = ["critical", "high", "standard", "low"];

export function ResponsibilityForm({
  action,
  initial,
  submitLabel,
}: {
  action: (state: ActionState, formData: FormData) => Promise<ActionState>;
  initial?: ResponsibilityDetail;
  submitLabel: string;
}) {
  return (
    <ActionForm action={action} className="max-w-xl">
      {initial ? <input type="hidden" name="version" value={initial.version} /> : null}
      <Field label="Name" htmlFor="name">
        <input
          id="name"
          name="name"
          required
          maxLength={200}
          defaultValue={initial?.name}
          placeholder="Payments on-call"
          className={inputClass}
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Category" htmlFor="category">
          <input
            id="category"
            name="category"
            maxLength={200}
            defaultValue={initial?.category ?? ""}
            placeholder="Operations"
            className={inputClass}
          />
        </Field>
        <Field label="Criticality" htmlFor="criticality">
          <select
            id="criticality"
            name="criticality"
            defaultValue={initial?.criticality ?? "standard"}
            className={inputClass}
          >
            {CRITICALITIES.map((c) => (
              <option key={c} value={c}>
                {c[0].toUpperCase() + c.slice(1)}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Description" htmlFor="description">
        <textarea
          id="description"
          name="description"
          maxLength={4000}
          rows={4}
          defaultValue={initial?.description ?? ""}
          className={`${inputClass} h-auto py-2`}
        />
      </Field>
      <div>
        <SubmitButton>{submitLabel}</SubmitButton>
      </div>
    </ActionForm>
  );
}
