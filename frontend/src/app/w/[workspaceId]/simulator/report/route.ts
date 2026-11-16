import { api, RelayApiError } from "@/lib/relay-api";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const cell = (v: unknown) =>
  String(v ?? "")
    .replaceAll("|", "\|")
    .replaceAll("\n", " ");

/**
 * The current what-if scenario as a Markdown report: the score and its working, what is
 * affected, and every cover candidate side by side, so a plan can be compared and shared.
 * Formatting only: every number comes from the API.
 */
export async function GET(
  request: Request,
  { params }: RouteContext<"/w/[workspaceId]/simulator/report">,
) {
  const { workspaceId } = await params;
  const q = new URL(request.url).searchParams;
  const person = q.get("person") ?? "";
  const backup = q.get("backup") || undefined;
  const days = q.get("days") || undefined;
  if (!UUID.test(workspaceId) || !UUID.test(person) || (backup && !UUID.test(backup))) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }
  try {
    const [v, c] = await Promise.all([
      api.simulation(workspaceId, person, backup, days),
      api.simulationCandidates(workspaceId, person, days),
    ]);
    const window = v.days ? `${v.days} days` : "an open-ended period";
    const lines = [
      `# What if ${v.person.name} is unavailable for ${window}?`,
      "",
      `Simulated ${new Date(v.simulated_at).toUTCString()} in Relay. Read-only: nothing was changed.`,
      "",
      `- **Readiness:** ${v.readiness_score} / 100 (today ${v.baseline_score})`,
      `- **Covered by:** ${v.backup ? v.backup.name : "nobody (raw impact)"}`,
      `- **Responsibilities affected:** ${v.affected_responsibilities.length}, ` +
        `${v.uncovered_responsibilities.length} without cover`,
      `- **Open work without cover:** ${v.open_work_without_cover.length} of ${v.open_work_total}`,
      `- **Due in the window:** ${v.due_in_window}`,
      "",
    ];
    if (v.score_parts) {
      const p = v.score_parts;
      lines.push(
        "## How the score is calculated",
        "",
        `Cover ${p.cover_weight}/${p.possible} × 60 + knowledge ${p.knowledge_weight}/${p.possible} × 25 ` +
          `+ second holder ${p.second_holder_weight}/${p.possible} × 15 = **${v.readiness_score}**`,
        "",
        "| Responsibility | Weight | Covered | Knowledge | Second holder |",
        "|---|---:|:-:|:-:|:-:|",
        ...p.rows.map(
          (r) =>
            `| ${cell(r.name)} | ${r.weight} (${r.criticality}) | ${r.covered ? "yes" : "no"} | ` +
            `${r.knowledge ? "yes" : "no"} | ${r.second_holder ? "yes" : "no"} |`,
        ),
        "",
      );
    }
    lines.push(
      "## Affected responsibilities",
      "",
      "| Responsibility | Criticality | Cover | Knowledge (stale) | Why |",
      "|---|---|---|---:|---|",
      ...v.affected_responsibilities.map(
        (r) =>
          `| ${cell(r.name)} | ${r.criticality} | ${cell(r.covered_by?.name ?? r.cover)} | ` +
          `${r.knowledge_total} (${r.knowledge_stale}) | ${cell(r.reasons.join("; "))} |`,
      ),
      "",
      "## Cover candidates compared",
      "",
      "| Candidate | Readiness | Covered | Critical gaps | Knowledge gaps | Load after | Overloaded |",
      "|---|---:|---:|---:|---:|---:|:-:|",
      ...c.candidates.map(
        (x) =>
          `| ${cell(x.person?.name ?? "Nobody")} | ${x.readiness_score} | ${x.covered}/${x.total} | ` +
          `${x.critical_gaps} | ${x.knowledge_gaps} | ${x.load_after ?? "–"} | ${x.overloaded ? "yes" : "no"} |`,
      ),
      "",
      `_${cell(c.basis)}_`,
      "",
    );
    const name = `what-if-${v.person.name.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.md`;
    return new Response(lines.join("\n"), {
      headers: {
        "Content-Type": "text/markdown; charset=utf-8",
        "Content-Disposition": `attachment; filename="${name}"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    if (error instanceof RelayApiError) {
      return Response.json({ detail: error.message }, { status: error.status });
    }
    throw error;
  }
}
