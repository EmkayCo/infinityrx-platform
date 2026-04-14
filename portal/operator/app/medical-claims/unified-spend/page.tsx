"use client";

import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { Search } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";

const MedicalClaimsUnifiedSpendBar = dynamic(
  () =>
    import("@/components/charts/medical-claims-unified-spend-bar").then(
      (m) => m.MedicalClaimsUnifiedSpendBar
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);
import { apiPost } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { UnifiedDrugSpend } from "@shared/types/medical-claims";

export default function UnifiedSpendPage() {
  const [memberId, setMemberId] = useState("");
  const [result, setResult] = useState<UnifiedDrugSpend | null>(null);

  const search = useMutation({
    mutationFn: (id: string) =>
      apiPost<UnifiedDrugSpend>(
        `${API_URLS.medicalClaims}/api/v1/unified-spend`,
        { member_id: id }
      ),
    onSuccess: setResult,
  });

  const chartData = (result?.period_months ?? []).map((m) => ({
    month: m.month.slice(0, 7),
    Pharmacy: parseFloat(m.pharmacy_spend),
    Medical: parseFloat(m.medical_spend),
  }));

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Unified Drug Spend</h1>
        <p className="text-slate-400 text-sm mt-1">
          Side-by-side pharmacy and medical drug spend by member
        </p>
      </div>

      <div className="flex gap-3 max-w-md">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Enter member ID..."
            value={memberId}
            onChange={(e) => setMemberId(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && memberId && search.mutate(memberId)}
            className="w-full pl-9 pr-4 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          />
        </div>
        <button
          onClick={() => memberId && search.mutate(memberId)}
          disabled={!memberId || search.isPending}
          className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors disabled:opacity-40"
        >
          {search.isPending ? "Loading..." : "Search"}
        </button>
      </div>

      {search.isError && (
        <div className="rounded-lg border border-red-700/30 bg-red-900/10 p-4 text-sm text-red-400">
          Could not find spend data for this member.
        </div>
      )}

      {result && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "Total Pharmacy", amount: result.total_pharmacy },
              { label: "Total Medical", amount: result.total_medical },
              { label: "Combined Total", amount: result.total_combined },
            ].map(({ label, amount }) => (
              <div key={label} className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-4">
                <p className="text-xs text-slate-400 mb-1">{label}</p>
                <DollarDisplay amount={amount} size="lg" />
              </div>
            ))}
          </div>

          {/* Chart */}
          <ErrorBoundary>
            <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-4">
                {result.drug_name} — Monthly Spend
              </h3>
              <MedicalClaimsUnifiedSpendBar data={chartData} />
            </div>
          </ErrorBoundary>
        </>
      )}

      {!result && !search.isPending && (
        <div className="rounded-lg border border-dashed border-ifx-border-dark p-12 text-center">
          <Search className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">
            Enter a member ID to view combined pharmacy and medical drug spend
          </p>
        </div>
      )}
    </div>
  );
}
