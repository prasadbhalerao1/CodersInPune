import { Badge } from "@/components/ui/badge";
import type { CapsuleStatus } from "@/lib/types";

const LABEL: Record<CapsuleStatus, { label: string; tone: "warning" | "neutral" | "muted" }> = {
  draft: { label: "Draft: needs approval", tone: "warning" },
  approved: { label: "Approved: awaiting acknowledgement", tone: "neutral" },
  acknowledged: { label: "Acknowledged", tone: "neutral" },
  superseded: { label: "Superseded", tone: "muted" },
};

export function CapsuleStatusBadge({ value }: { value: CapsuleStatus }) {
  return <Badge tone={LABEL[value].tone}>{LABEL[value].label}</Badge>;
}
