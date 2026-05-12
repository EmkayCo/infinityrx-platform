"use client";

// Loading skeletons for paysync pages.
//
// Uses tailwind animate-pulse + rounded blocks to approximate page
// layout while data fetches. Avoids layout shift on completion.

import { cn } from "@shared/lib/format";

export function TableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="rounded-lg border bg-card" aria-busy="true" aria-label="Loading">
      <div className="border-b bg-muted/30 px-4 py-2.5">
        <div className="h-3 w-32 animate-pulse rounded bg-muted" />
      </div>
      <div className="divide-y">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-3 px-4 py-2.5">
            <div className="h-3 w-1/4 animate-pulse rounded bg-muted" />
            <div className="h-3 w-1/6 animate-pulse rounded bg-muted" />
            <div className="h-3 w-1/5 animate-pulse rounded bg-muted" />
            <div className="ml-auto h-3 w-16 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
    </div>
  );
}

export function KpiRowSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className={cn(
      "grid gap-3",
      count === 4 ? "grid-cols-2 md:grid-cols-4" :
      count === 3 ? "md:grid-cols-3" : "md:grid-cols-2",
    )} aria-busy="true" aria-label="Loading metrics">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-lg border bg-card p-3">
          <div className="h-2.5 w-20 animate-pulse rounded bg-muted" />
          <div className="mt-2 h-6 w-16 animate-pulse rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}

export function CardGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3"
         aria-busy="true" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-lg border bg-card p-4">
          <div className="h-3 w-24 animate-pulse rounded bg-muted" />
          <div className="mt-3 h-3 w-3/4 animate-pulse rounded bg-muted" />
          <div className="mt-2 h-2.5 w-1/2 animate-pulse rounded bg-muted" />
        </div>
      ))}
    </div>
  );
}
