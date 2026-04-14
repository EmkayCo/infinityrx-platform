"use client";

import React from "react";
import dynamic from "next/dynamic";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";

// InvestigationsKanban pulls in @dnd-kit/core + @dnd-kit/utilities (~60KB).
// Lazy-load so the route-level bundle stays small.
const InvestigationsKanban = dynamic(
  () =>
    import("@/components/reclaimrx/investigations-kanban").then(
      (m) => m.InvestigationsKanban
    ),
  {
    ssr: false,
    loading: () => (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="flex gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="flex-1 h-96 rounded-xl" />
          ))}
        </div>
      </div>
    ),
  }
);

export default function InvestigationsPage() {
  return (
    <ErrorBoundary>
      <InvestigationsKanban />
    </ErrorBoundary>
  );
}
