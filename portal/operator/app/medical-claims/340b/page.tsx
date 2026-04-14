"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { ThreeFourtyBSummary, MedicalClaim } from "@shared/types/medical-claims";
import { formatDate } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const recentColumns: ColDef<MedicalClaim>[] = [
  { accessorKey: "claim_number", header: "Claim #", cell: (c) => <span className="font-mono text-xs text-teal-400">{c.getValue() as string}</span> },
  { accessorKey: "hcpcs_code", header: "HCPCS", cell: (c) => <span className="font-mono text-xs font-bold">{c.getValue() as string}</span> },
  { accessorKey: "drug_name", header: "Drug" },
  { accessorKey: "provider_name", header: "Provider" },
  { accessorKey: "date_of_service", header: "DOS", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "billed_amount", header: "Billed", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "paid_amount", header: "Paid", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
];

export default function ThreeFourtyBPage() {
  const router = useRouter();

  const { data: summary, isLoading } = useQuery<ThreeFourtyBSummary>({
    queryKey: ["340b-summary"],
    queryFn: () =>
      apiGet<ThreeFourtyBSummary>(buildUrl(`${API_URLS.medicalClaims}/api/v1/340b/summary`)),
    staleTime: 60_000,
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <ShieldCheck className="w-6 h-6 text-purple-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">340B Summary</h1>
          <p className="text-slate-400 text-sm mt-1">Covered entity compliance and program totals</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-lg" />)
        ) : summary ? (
          <>
            <div className="rounded-lg border border-purple-700/20 bg-purple-900/5 p-5">
              <p className="text-xs text-slate-400 mb-1">Flagged Claims</p>
              <p className="text-2xl font-bold text-white">{summary.flagged_count}</p>
            </div>
            <div className="rounded-lg border border-purple-700/20 bg-purple-900/5 p-5">
              <p className="text-xs text-slate-400 mb-1">Entity Matches</p>
              <p className="text-2xl font-bold text-white">{summary.entity_match_count}</p>
            </div>
            <div className="rounded-lg border border-purple-700/20 bg-purple-900/5 p-5">
              <p className="text-xs text-slate-400 mb-1">Total Program Amount</p>
              <DollarDisplay amount={summary.total_program_amount} size="lg" />
            </div>
            <div className="rounded-lg border border-purple-700/20 bg-purple-900/5 p-5">
              <p className="text-xs text-slate-400 mb-1">Potential Savings</p>
              <DollarDisplay amount={summary.potential_savings} size="lg" />
            </div>
          </>
        ) : null}
      </div>

      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Recent 340B Claims</h3>
          <DataTable
            columns={recentColumns}
            data={summary?.recent_claims ?? []}
            isLoading={isLoading}
            emptyTitle="No 340B claims found"
            onRowClick={(r: MedicalClaim) => router.push(`/medical-claims/claims/${r.id}`)}
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
