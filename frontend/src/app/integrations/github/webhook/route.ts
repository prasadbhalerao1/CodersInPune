/**
 * Production webhook route: GitHub posts here (the only public origin) and Relay forwards
 * the raw body and GitHub's headers, unchanged, to the API, which verifies the HMAC
 * signature and handles duplicates and replays. Nothing is parsed or trusted here.
 */
const FORWARDED = [
  "x-hub-signature-256",
  "x-github-event",
  "x-github-delivery",
  "x-github-hook-installation-target-id",
  "content-type",
  "user-agent",
];
const MAX_BYTES = 5 * 1024 * 1024; // GitHub caps payloads at 25 MB; Relay needs far less

export async function POST(request: Request): Promise<Response> {
  const base = process.env.RELAY_API_URL?.replace(/\/$/, "");
  if (!base) return new Response("Not configured", { status: 503 });
  const body = await request.arrayBuffer();
  if (body.byteLength > MAX_BYTES) return new Response("Payload too large", { status: 413 });
  const headers = new Headers();
  for (const name of FORWARDED) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const response = await fetch(`${base}/integrations/github/webhook`, {
    method: "POST",
    headers,
    body,
    cache: "no-store",
  });
  return new Response(response.body, { status: response.status });
}
