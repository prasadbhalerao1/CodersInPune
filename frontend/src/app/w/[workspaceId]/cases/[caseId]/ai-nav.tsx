import Link from "next/link";

import { PageHeader } from "@/components/page";

import { CaseTabs } from "./workflow";

const TABS = [
  { key: "analysis", label: "Analysis", path: "/analysis" },
  { key: "interview", label: "Interview", path: "/interview" },
  { key: "capsules", label: "Handover capsules", path: "/capsules" },
] as const;

/** Header for a case's intelligence pages: breadcrumb back to the case, then tabs. */
export function CaseAiHeader({
  workspaceId,
  caseId,
  caseTitle,
  current,
  actions,
}: {
  workspaceId: string;
  caseId: string;
  caseTitle: string;
  current: (typeof TABS)[number]["key"];
  actions?: React.ReactNode;
}) {
  const base = `/w/${workspaceId}/cases/${caseId}`;
  return (
    <>
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Link href={base} className="text-muted-foreground hover:text-foreground truncate">
              {caseTitle}
            </Link>
            <span className="text-muted-foreground">/</span>
            <span>{TABS.find((t) => t.key === current)?.label}</span>
          </span>
        }
        actions={actions}
      />
      <CaseTabs workspaceId={workspaceId} caseId={caseId} current={current} />
    </>
  );
}
