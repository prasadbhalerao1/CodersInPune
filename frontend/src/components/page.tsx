import type { ReactNode } from "react";

export function PageHeader({
  title,
  actions,
  description,
}: {
  title: ReactNode;
  actions?: ReactNode;
  /** One line under the title saying what the page is for. */
  description?: ReactNode;
}) {
  return (
    <header className="bg-background/85 sticky top-0 z-10 flex min-h-14 shrink-0 items-center justify-between gap-4 border-b px-6 py-3 backdrop-blur">
      <div className="min-w-0">
        <h1 className="truncate text-[15px] font-semibold">{title}</h1>
        {description ? (
          <p className="text-muted-foreground mt-0.5 truncate text-[13px]">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </header>
  );
}

/** A bordered surface for grouped content. */
export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={`bg-card rounded-lg border shadow-xs ${className ?? ""}`}>{children}</div>;
}

/** A labelled figure: the number is the point, the hint says what it means. */
export function Stat({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "default" | "danger" | "warning" | "success";
}) {
  const colour = {
    default: "text-foreground",
    danger: "text-destructive",
    warning: "text-amber-700 dark:text-amber-300",
    success: "text-emerald-700 dark:text-emerald-300",
  }[tone];
  return (
    <div className="bg-card flex flex-col gap-1 rounded-lg border px-4 py-3 shadow-xs">
      <span className="text-muted-foreground text-xs font-medium">{label}</span>
      <span className={`tabular text-2xl leading-none font-semibold ${colour}`}>{value}</span>
      {hint ? <span className="text-muted-foreground text-xs">{hint}</span> : null}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="bg-card/50 flex flex-col items-center rounded-lg border border-dashed px-6 py-12 text-center">
      <p className="font-medium">{title}</p>
      <p className="text-muted-foreground mt-1 max-w-sm text-sm">{description}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function Section({
  title,
  description,
  children,
  aside,
}: {
  title: ReactNode;
  description?: string;
  children: ReactNode;
  aside?: ReactNode;
}) {
  return (
    <section
      className="flex flex-col gap-3"
      data-section={typeof title === "string" ? title : undefined}
    >
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold">{title}</h2>
          {description ? <p className="text-muted-foreground text-xs">{description}</p> : null}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}

export const formatDateTime = (iso: string) =>
  new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(iso),
  );
