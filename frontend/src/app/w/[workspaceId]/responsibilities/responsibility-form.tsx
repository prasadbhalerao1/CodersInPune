import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import type { ActionState } from "@/lib/action-state";
import type {
  Criticality,
  PersonView,
  ResponsibilityDetail,
  ResponsibilityTypeView,
} from "@/lib/types";

const CRITICALITIES: Criticality[] = ["critical", "high", "standard", "low"];

export function ResponsibilityForm({
  action,
  initial,
  submitLabel,
  types,
  people,
}: {
  action: (state: ActionState, formData: FormData) => Promise<ActionState>;
  initial?: ResponsibilityDetail;
  submitLabel: string;
  types: ResponsibilityTypeView[];
  people: PersonView[];
}) {
  return (
    <ActionForm action={action} className="max-w-2xl">
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
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Type" htmlFor="type_id">
          <select
            id="type_id"
            name="type_id"
            defaultValue={initial?.type_id ?? ""}
            className={inputClass}
          >
            <option value="">No type</option>
            {types.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
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
        <Field label="Review every (days)" htmlFor="review_cadence_days">
          <input
            id="review_cadence_days"
            name="review_cadence_days"
            type="number"
            min={7}
            max={730}
            defaultValue={initial?.review_cadence_days ?? ""}
            placeholder={
              initial ? `Default: ${initial.effective_review_days}` : "From type or tier"
            }
            className={inputClass}
          />
        </Field>
      </div>
      {initial?.category ? <input type="hidden" name="category" value={initial.category} /> : null}
      <Field label="Description" htmlFor="description">
        <textarea
          id="description"
          name="description"
          maxLength={4000}
          rows={3}
          defaultValue={initial?.description ?? ""}
          className={`${inputClass} h-auto py-2`}
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Escalation path" htmlFor="escalation_path">
          <input
            id="escalation_path"
            name="escalation_path"
            maxLength={4000}
            defaultValue={initial?.escalation_path ?? ""}
            placeholder="Page on-call, then the engineering manager"
            className={inputClass}
          />
        </Field>
        <Field label="Escalation contact" htmlFor="escalation_contact">
          <input
            id="escalation_contact"
            name="escalation_contact"
            maxLength={200}
            defaultValue={initial?.escalation_contact ?? ""}
            placeholder="#payments-oncall or +91…"
            className={inputClass}
          />
        </Field>
      </div>
      <Field
        label="Accountable contact (needed for team-owned critical responsibilities)"
        htmlFor="accountable_person_id"
      >
        <select
          id="accountable_person_id"
          name="accountable_person_id"
          defaultValue={initial?.accountable_person_id ?? ""}
          className={inputClass}
        >
          <option value="">None</option>
          {people.map((p) => (
            <option key={p.id} value={p.id}>
              {p.display_name}
            </option>
          ))}
        </select>
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Required procedures (one per line)" htmlFor="procedures">
          <textarea
            id="procedures"
            name="procedures"
            rows={3}
            defaultValue={initial?.procedures.join("\n") ?? ""}
            placeholder="Month-end close"
            className={`${inputClass} h-auto py-2`}
          />
        </Field>
        <Field label="Access prerequisites (one per line)" htmlFor="access_prerequisites">
          <textarea
            id="access_prerequisites"
            name="access_prerequisites"
            rows={3}
            defaultValue={initial?.access_prerequisites.join("\n") ?? ""}
            placeholder="Stripe admin"
            className={`${inputClass} h-auto py-2`}
          />
        </Field>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" name="restricted" defaultChecked={initial?.restricted} />
        <span>
          Restricted
          <span className="text-muted-foreground block text-xs">
            Only owners and admins, current holders and people you grant access can see it — it is
            also left out of counts and search for everyone else.
          </span>
        </span>
      </label>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          name="needs_verification"
          defaultChecked={initial?.needs_verification}
        />
        Needs human verification
      </label>
      <div>
        <SubmitButton>{submitLabel}</SubmitButton>
      </div>
    </ActionForm>
  );
}
