import { EXPLAIN, type Explanation } from "@/lib/explain";
import { REPO_URL, SITE_URL } from "@/lib/site";

/**
 * The whole product guide as plain text for AI crawlers and assistants: every feature and
 * number with its definition, formula, inputs and source file. Built from the same registry
 * the in-app ⓘ and /docs use, so it never drifts.
 */
export function GET() {
  const parts = [
    "# Relay: full product guide",
    "",
    "Relay keeps work moving when people move on: who is accountable for what, the evidence",
    "behind it from GitHub, Linear and Notion, what an absence would break, and reviewed,",
    "audited handovers. AI drafts with citations it cannot invent; people decide.",
    "",
    "Relay is a working multi-tenant SaaS: real WorkOS sign-in, real GitHub, Linear, Notion and",
    "Slack connections, Postgres with row-level security. The pre-seeded sample organisation only",
    "spares evaluators from connecting their own tools; real workspaces use the same code paths.",
    "",
    `Live product: ${SITE_URL} · Guide: ${SITE_URL}/docs · Source: ${REPO_URL}`,
    "",
  ];
  for (const [key, e] of Object.entries(EXPLAIN) as [string, Explanation][]) {
    parts.push(`## ${e.title}`, "", e.summary, "");
    if (e.formula) parts.push(`How it is calculated: ${e.formula}`, "");
    if (e.inputs.length) parts.push(`What it uses: ${e.inputs.join("; ")}.`, "");
    if (e.reading) parts.push(`How to read it: ${e.reading}`, "");
    parts.push(`Source: ${REPO_URL}/blob/main/${e.source.split(" ")[0]}`);
    parts.push(`Anchor: ${SITE_URL}/docs#${key}`, "");
  }
  return new Response(parts.join("\n"), {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
