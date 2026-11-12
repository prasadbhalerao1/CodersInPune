// The public origin, for absolute URLs in metadata, the sitemap and llms.txt.
export const SITE_URL = (
  process.env.NEXT_PUBLIC_SITE_URL ?? "https://relay-continuity-nine.vercel.app"
).replace(/\/$/, "");

export const REPO_URL = "https://github.com/prasadbhalerao1/CodersInPune";

export const SITE_DESCRIPTION =
  "Relay is an organisational continuity platform: it records who is accountable for what, rebuilds the context behind that work from GitHub, Linear and Notion with cited evidence, forecasts what an absence would break, and moves ownership through reviewed, audited handovers.";
