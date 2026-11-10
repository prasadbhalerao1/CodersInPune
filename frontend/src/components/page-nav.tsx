import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

/** Next/first links for keyset-paged lists. Renders nothing when there's a single page. */
export function PageNav({
  base,
  query,
  after,
  next,
}: {
  base: string;
  /** The current filters, without `after`. */
  query: Record<string, string | undefined>;
  after: string | undefined;
  next: string | null | undefined;
}) {
  if (!after && !next) return null;
  const href = (cursor?: string) => {
    const params = new URLSearchParams(
      Object.entries({ ...query, after: cursor }).filter((e): e is [string, string] =>
        Boolean(e[1]),
      ),
    ).toString();
    return params ? `${base}?${params}` : base;
  };
  return (
    <nav aria-label="Pages" className="flex items-center justify-between gap-3 pt-2 text-sm">
      {after ? (
        <Link href={href()} className={buttonVariants({ variant: "ghost", size: "sm" })}>
          ← First page
        </Link>
      ) : (
        <span />
      )}
      {next ? (
        <Link href={href(next)} className={buttonVariants({ variant: "outline", size: "sm" })}>
          Next page →
        </Link>
      ) : null}
    </nav>
  );
}
