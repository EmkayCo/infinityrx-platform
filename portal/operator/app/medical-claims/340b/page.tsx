import React from "react";
import { ShieldCheck } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DollarDisplay } from "@shared/components/dollar-display";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { ThreeFourtyBSummary } from "@shared/types/medical-claims";
import { ThreeFourtyBInteractive } from "@/components/medical-claims/threesixtyfourb-interactive";

// Server Component — fetches the summary at request time and pre-renders
// the KPI cards. Only the claims table (which navigates on row click)
// needs client interactivity, so it's the single leaf component.
export default async function ThreeFourtyBPage() {
  const summary = await apiGet<ThreeFourtyBSummary>(
    buildUrl(`${API_URLS.medicalClaims}/api/v1/340b/summary`)
  );

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
      </div>

      <ErrorBoundary>
        <ThreeFourtyBInteractive summary={summary} />
      </ErrorBoundary>
    </div>
  );
}
