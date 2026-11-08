import { cn } from "@/lib/utils";
import type { CaseStatus, Criticality, RiskStatus, Role, Severity } from "@/lib/types";

// Colour carries meaning only: red = act now, amber = attention, neutral otherwise.
const TONES = {
  danger: "bg-red-50 text-red-700 ring-red-600/15 dark:bg-red-950/40 dark:text-red-300",
  warning: "bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-950/40 dark:text-amber-300",
  neutral: "bg-muted text-foreground/80 ring-border",
  muted: "bg-transparent text-muted-foreground ring-border",
} as const;

type Tone = keyof typeof TONES;

export function Badge({
  tone = "neutral",
  className,
  children,
}: {
  tone?: Tone;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-1.5 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const CRITICALITY_TONE: Record<Criticality, Tone> = {
  critical: "danger",
  high: "warning",
  standard: "neutral",
  low: "muted",
};

export function CriticalityBadge({ value }: { value: Criticality }) {
  return <Badge tone={CRITICALITY_TONE[value]}>{value[0].toUpperCase() + value.slice(1)}</Badge>;
}

const SEVERITY_TONE: Record<Severity, Tone> = { high: "danger", medium: "warning", low: "muted" };

export function SeverityBadge({ value }: { value: Severity }) {
  return <Badge tone={SEVERITY_TONE[value]}>{value[0].toUpperCase() + value.slice(1)}</Badge>;
}

export const ROLE_LABEL: Record<Role, string> = {
  primary: "Primary",
  co_owner: "Co-owner",
  backup: "Backup",
  temporary: "Covering",
};

export function RoleBadge({ value }: { value: Role }) {
  const tone = value === "primary" ? "neutral" : value === "temporary" ? "warning" : "muted";
  return <Badge tone={tone}>{ROLE_LABEL[value]}</Badge>;
}

const STATUS: Record<CaseStatus, { label: string; tone: Tone; dot: string }> = {
  draft: { label: "Draft", tone: "muted", dot: "bg-muted-foreground/50" },
  planning: { label: "Planning", tone: "neutral", dot: "bg-amber-500" },
  executing: { label: "In progress", tone: "neutral", dot: "bg-sky-600" },
  completed: { label: "Completed", tone: "neutral", dot: "bg-emerald-600" },
  cancelled: { label: "Cancelled", tone: "muted", dot: "bg-muted-foreground/40" },
};

export function CaseStatusBadge({ value }: { value: CaseStatus }) {
  const s = STATUS[value];
  return (
    <Badge tone={s.tone} className="gap-1.5">
      <span aria-hidden className={cn("size-1.5 rounded-full", s.dot)} />
      {s.label}
    </Badge>
  );
}

const RISK_STATUS: Record<RiskStatus, { label: string; tone: Tone }> = {
  open: { label: "Open", tone: "neutral" },
  acknowledged: { label: "Acknowledged", tone: "muted" },
  accepted: { label: "Accepted", tone: "muted" },
  resolved: { label: "Resolved", tone: "muted" },
};

export function RiskStatusBadge({ value }: { value: RiskStatus }) {
  return <Badge tone={RISK_STATUS[value].tone}>{RISK_STATUS[value].label}</Badge>;
}

export function EmergencyBadge() {
  return (
    <Badge tone="danger" className="gap-1.5">
      <span aria-hidden className="size-1.5 rounded-full bg-red-600" />
      Emergency
    </Badge>
  );
}
