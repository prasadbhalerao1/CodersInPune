import type { SearchHit, SearchKind } from "@/lib/types";

/** Group labels shared by the command menu and the search page. */
export const KIND_GROUP: Record<SearchKind, string> = {
  responsibility: "Responsibilities",
  case: "Continuity cases",
  person: "People",
  team: "Teams",
  department: "Departments",
  asset: "Assets",
  knowledge: "Knowledge",
  risk: "Risks",
  github: "GitHub",
  linear: "Linear",
};

/** Where a hit opens inside Relay (workspace-relative). External records open their URL. */
export function hitPath(hit: SearchHit): string {
  switch (hit.kind) {
    case "responsibility":
    case "knowledge":
      return `/responsibilities/${hit.id}`;
    case "case":
      return `/cases/${hit.id}`;
    case "person":
      return `/people/${hit.id}`;
    case "team":
      return `/teams/${hit.id}`;
    case "department":
      return `/departments/${hit.id}`;
    case "asset":
      return `/assets/${hit.id}`;
    case "risk":
      return `/risks/${encodeURIComponent(hit.id)}`;
    case "github":
    case "linear":
      return `/search?q=${encodeURIComponent(hit.title)}&kind=${hit.kind}`;
  }
}
