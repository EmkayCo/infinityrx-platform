"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
import { LayoutGrid, Table2 } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { cn } from "@shared/lib/format";
import { InvestigationsTable } from "@/components/reclaimrx/investigations-table";

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

type ViewMode = "kanban" | "table";

export default function InvestigationsPage() {
  const [view, setView] = useState<ViewMode>("kanban");

  return (
    <ErrorBoundary>
      <div className="flex flex-col h-full">
        {/* View toggle toolbar */}
        <div className="flex items-center gap-1 px-6 pt-4 pb-0">
          <button
            onClick={() => setView("kanban")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
              view === "kanban"
                ? "bg-ifx-navy text-white"
                : "text-ifx-gray-400 hover:bg-ifx-gray-50"
            )}
            aria-pressed={view === "kanban"}
          >
            <LayoutGrid className="w-4 h-4" />
            Kanban
          </button>
          <button
            onClick={() => setView("table")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors",
              view === "table"
                ? "bg-ifx-navy text-white"
                : "text-ifx-gray-400 hover:bg-ifx-gray-50"
            )}
            aria-pressed={view === "table"}
          >
            <Table2 className="w-4 h-4" />
            Table
          </button>
        </div>

        {/* Content area */}
        <div className="flex-1 min-h-0 overflow-auto">
          {view === "kanban" ? (
            <InvestigationsKanban />
          ) : (
            <InvestigationsTable />
          )}
        </div>
      </div>
    </ErrorBoundary>
  );
}
