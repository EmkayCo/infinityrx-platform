"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, AlertTriangle } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { DollarDisplay } from "@shared/components/dollar-display";
import { ExportMenu } from "@shared/components/export-menu";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Drug } from "@shared/types/directories";
import { useRouter } from "next/navigation";

const columns: ColDef<Drug>[] = [
  {
    accessorKey: "ndc",
    header: "NDC",
    cell: (c) => <span className="font-mono text-xs text-teal-400">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "brand_name",
    header: "Brand",
    cell: (c) => <span className="font-medium text-white">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "generic_name",
    header: "Generic",
    cell: (c) => <span className="text-slate-300 text-sm">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "strength",
    header: "Strength",
    cell: (c) => <span className="text-xs text-slate-400">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "dosage_form",
    header: "Form",
    cell: (c) => <span className="text-xs text-slate-400 capitalize">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "therapeutic_class",
    header: "Therapeutic Class",
    cell: (c) => <span className="text-xs text-slate-300">{c.getValue() as string}</span>,
  },
  {
    id: "awp",
    header: "AWP",
    cell: (c) => <DollarDisplay amount={c.row.original.current_pricing?.awp} size="sm" />,
  },
  {
    id: "wac",
    header: "WAC",
    cell: (c) => <DollarDisplay amount={c.row.original.current_pricing?.wac} size="sm" />,
  },
  {
    accessorKey: "rems_required",
    header: "REMS",
    cell: (c) => c.getValue() ? (
      <span className="text-xs px-2 py-0.5 rounded bg-orange-900/40 text-orange-300">REMS</span>
    ) : null,
  },
];

// Price change alerts widget
function PriceAlerts() {
  return (
    <div className="rounded-lg border border-orange-700/20 bg-orange-900/5 p-4 flex items-center gap-3">
      <AlertTriangle className="w-5 h-5 text-orange-400 flex-shrink-0" />
      <p className="text-sm text-slate-300">
        Price change alerts are monitored daily. Check the drug detail page for price change history.
      </p>
    </div>
  );
}

export default function DrugsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");

  const { data: drugs = [], isLoading } = useQuery<Drug[]>({
    queryKey: ["drugs", search],
    queryFn: () =>
      apiGet<Drug[]>(
        buildUrl(`${API_URLS.drugDatabase}/api/v1/drugs`, {
          q: search || undefined,
          limit: 100,
        })
      ),
    staleTime: 60_000,
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Drug Database</h1>
          <p className="text-slate-400 text-sm mt-1">{drugs.length} drugs</p>
        </div>
        <ExportMenu onExportCsv={() => {/* export */}} />
      </div>

      <PriceAlerts />

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="search"
          placeholder="Search NDC, drug name, therapeutic class..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
        />
      </div>

      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <DataTable
            columns={columns}
            data={drugs}
            isLoading={isLoading}
            emptyTitle="No drugs found"
            emptyDescription="Try searching by NDC, brand name, or generic name."
            onRowClick={(r: Drug) => router.push(`/directories/drugs/${r.ndc}`)}
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
