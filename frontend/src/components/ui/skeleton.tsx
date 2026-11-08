import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("bg-muted animate-pulse rounded-md", className)} />;
}

// Shaped like the real content so the layout doesn't jump when data streams in.
export function PageSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" className="flex flex-1 flex-col">
      <div className="flex h-14 items-center border-b px-6">
        <Skeleton className="h-5 w-40" />
      </div>
      <div className="flex flex-col gap-4 p-6">
        <Skeleton className="h-9 w-full max-w-xl" />
        <div className="divide-y rounded-lg border">
          {Array.from({ length: rows }, (_, i) => (
            <div key={i} className="flex items-center gap-4 px-4 py-3">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-4 w-16" />
              <Skeleton className="ml-auto h-4 w-24" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function CardsSkeleton() {
  return (
    <div role="status" aria-label="Loading" className="flex flex-1 flex-col">
      <div className="flex h-14 items-center border-b px-6">
        <Skeleton className="h-5 w-32" />
      </div>
      <div className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} className="rounded-lg border p-4">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="mt-3 h-7 w-12" />
          </div>
        ))}
      </div>
      <div className="grid gap-4 px-6 lg:grid-cols-2">
        <Skeleton className="h-64 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    </div>
  );
}
