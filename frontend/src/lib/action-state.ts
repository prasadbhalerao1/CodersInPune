export type ActionState = { error?: string };

/** The form's idempotency key (see ActionForm): one per submission intent, kept on retry. */
export function idempotencyKey(fd: FormData): string | null {
  const key = fd.get("idempotency_key");
  return typeof key === "string" && /^[A-Za-z0-9_-]{8,128}$/.test(key) ? key : null;
}
