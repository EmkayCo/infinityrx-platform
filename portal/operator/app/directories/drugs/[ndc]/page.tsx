"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ChevronLeft } from "lucide-react";
import dynamic from "next/dynamic";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Drug, DrugInteraction, TherapeuticEquivalent } from "@shared/types/directories";
import { cn, formatDate } from "@shared/lib/format";

const DirectoriesDrugPriceHistoryLine = dynamic(
  () =>
    import("@/components/charts/directories-drug-price-history-line").then(
      (m) => m.DirectoriesDrugPriceHistoryLine
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);

const SEVERITY_COLORS = {
  contraindicated: "bg-red-900/60 text-red-300",
  major: "bg-red-900/30 text-red-300",
  moderate: "bg-yellow-900/30 text-yellow-300",
  minor: "bg-slate-700 text-slate-400",
};

const interactionColumns: ColDef<DrugInteraction>[] = [
  { accessorKey: "interacting_drug_name", header: "Drug", cell: (c) => <span className="font-medium text-white text-sm">{c.getValue() as string}</span> },
  {
    accessorKey: "severity",
    header: "Severity",
    cell: (c) => (
      <span className={cn("text-xs px-2 py-0.5 rounded capitalize", SEVERITY_COLORS[c.getValue() as keyof typeof SEVERITY_COLORS])}>
        {c.getValue() as string}
      </span>
    ),
  },
  { accessorKey: "description", header: "Description", cell: (c) => <span className="text-xs text-slate-400">{c.getValue() as string}</span> },
];

const equivColumns: ColDef<TherapeuticEquivalent>[] = [
  { accessorKey: "drug_name", header: "Drug", cell: (c) => <span className="font-medium text-white text-sm">{c.getValue() as string}</span> },
  { accessorKey: "ndc", header: "NDC", cell: (c) => <span className="font-mono text-xs text-teal-400">{c.getValue() as string}</span> },
  { accessorKey: "manufacturer", header: "Manufacturer", cell: (c) => <span className="text-slate-300 text-sm">{c.getValue() as string}</span> },
  { accessorKey: "awp", header: "AWP", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
];

export default function DrugDetailPage() {
  const { ndc } = useParams<{ ndc: string }>();
  const router = useRouter();

  const { data: drug, isLoading } = useQuery<Drug>({
    queryKey: ["drug", ndc],
    queryFn: () => apiGet<Drug>(`${API_URLS.drugDatabase}/api/v1/drugs/${ndc}`),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-3 gap-4"><Skeleton className="h-24 rounded-lg" /><Skeleton className="h-24 rounded-lg" /><Skeleton className="h-24 rounded-lg" /></div>
      </div>
    );
  }

  if (!drug) return <div className="p-6"><p className="text-slate-400">Drug not found.</p></div>;

  const priceHistory = drug.pricing_history.map((p) => ({
    date: formatDate(p.recorded_at),
    AWP: parseFloat(p.awp),
    WAC: parseFloat(p.wac),
    NADAC: p.nadac ? parseFloat(p.nadac) : null,
  }));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => router.back()} className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 transition-colors">
          <ChevronLeft className="w-4 h-4" /> Back
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-white">{drug.brand_name}</h1>
            {drug.rems_required && (
              <span className="text-xs px-2 py-1 rounded bg-orange-900/40 text-orange-300 border border-orange-700/30">
                REMS: {drug.rems_program}
              </span>
            )}
            {drug.is_controlled && (
              <span className="text-xs px-2 py-1 rounded bg-red-900/40 text-red-300">
                Schedule {drug.schedule}
              </span>
            )}
          </div>
          <p className="text-slate-400 text-sm mt-1">
            {drug.generic_name} · {drug.strength} {drug.dosage_form} · NDC: {drug.ndc}
          </p>
        </div>
      </div>

      {/* Pricing Panel */}
      <ErrorBoundary>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "AWP", amount: drug.current_pricing.awp },
            { label: "WAC", amount: drug.current_pricing.wac },
            { label: "NADAC", amount: drug.current_pricing.nadac },
            { label: "MAC", amount: drug.current_pricing.mac },
          ].map(({ label, amount }) => (
            <div key={label} className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-4">
              <p className="text-xs text-slate-400 mb-1">{label}</p>
              {amount ? (
                <DollarDisplay amount={amount} size="lg" />
              ) : (
                <p className="text-slate-500 text-sm">—</p>
              )}
            </div>
          ))}
        </div>
      </ErrorBoundary>

      {/* Price History Chart */}
      {priceHistory.length > 0 && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Price Change History</h3>
            <DirectoriesDrugPriceHistoryLine data={priceHistory} />
          </div>
        </ErrorBoundary>
      )}

      {/* Drug details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">
              Drug Interactions ({drug.interactions.length})
            </h3>
            <DataTable
              columns={interactionColumns}
              data={drug.interactions}
              emptyTitle="No known interactions"
            />
          </div>
        </ErrorBoundary>

        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">
              Therapeutic Equivalents ({drug.therapeutic_equivalents.length})
            </h3>
            <DataTable
              columns={equivColumns}
              data={drug.therapeutic_equivalents}
              emptyTitle="No therapeutic equivalents"
            />
          </div>
        </ErrorBoundary>
      </div>
    </div>
  );
}
