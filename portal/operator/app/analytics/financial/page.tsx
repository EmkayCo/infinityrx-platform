"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { FinancialMetrics } from "@shared/types/analytics";
import { cn } from "@shared/lib/format";

const AnalyticsFinancialPmpmLine = dynamic(
  () =>
    import("@/components/charts/analytics-financial-pmpm-line").then(
      (m) => m.AnalyticsFinancialPmpmLine
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);

const AnalyticsFinancialCostDriverBar = dynamic(
  () =>
    import("@/components/charts/analytics-financial-cost-driver-bar").then(
      (m) => m.AnalyticsFinancialCostDriverBar
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);

export default function FinancialAnalyticsPage() {
  const { data: metrics, isLoading } = useQuery<FinancialMetrics>({
    queryKey: ["financial-analytics"],
    queryFn: () =>
      apiGet<FinancialMetrics>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/financial`)),
    staleTime: 120_000,
  });

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Financial Analytics</h1>
        <p className="text-slate-400 text-sm mt-1">PMPM trending, cost drivers, and spread analysis</p>
      </div>

      {/* PMPM Cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Current PMPM", amount: metrics?.pmpm, loading: isLoading },
          { label: "Prior Year PMPM", amount: metrics?.pmpm_prior_year, loading: isLoading },
          {
            label: "YoY Change",
            custom: metrics ? (
              <span className={cn(
                "text-2xl font-bold tabular-nums",
                (metrics.pmpm_change_pct ?? 0) > 0 ? "text-red-400" : "text-green-400"
              )}>
                {(metrics.pmpm_change_pct ?? 0) > 0 ? "+" : ""}{(metrics.pmpm_change_pct ?? 0).toFixed(1)}%
              </span>
            ) : null,
            loading: isLoading,
          },
        ].map(({ label, amount, custom, loading }) => (
          <div key={label} className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <p className="text-xs text-slate-400 mb-1">{label}</p>
            {loading ? (
              <Skeleton className="h-8 w-32" />
            ) : custom ? custom : (
              <DollarDisplay amount={amount} size="lg" />
            )}
          </div>
        ))}
      </div>

      {/* PMPM Trend + Spread side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">PMPM Trend with YoY</h3>
            {isLoading ? <Skeleton className="h-48" /> : (
              <AnalyticsFinancialPmpmLine data={metrics?.pmpm_trend ?? []} />
            )}
          </div>
        </ErrorBoundary>

        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Spread Analysis</h3>
            {isLoading ? <Skeleton className="h-48" /> : metrics?.spread_analysis ? (
              <div className="space-y-3">
                {[
                  { label: "Total Billed", amount: metrics.spread_analysis.total_billed },
                  { label: "Total Paid", amount: metrics.spread_analysis.total_paid },
                  { label: "Spread", amount: metrics.spread_analysis.spread },
                ].map(({ label, amount }) => (
                  <div key={label} className="flex justify-between items-center py-2 border-b border-ifx-border-dark/50 last:border-0">
                    <span className="text-sm text-slate-400">{label}</span>
                    <DollarDisplay amount={amount} size="md" />
                  </div>
                ))}
                <div className="flex justify-between items-center pt-1">
                  <span className="text-sm text-slate-400">Spread %</span>
                  <span className="text-base font-bold text-teal-400">
                    {metrics.spread_analysis.spread_pct.toFixed(2)}%
                  </span>
                </div>
              </div>
            ) : null}
          </div>
        </ErrorBoundary>
      </div>

      {/* Cost Driver Decomposition */}
      {metrics?.cost_driver_breakdown && metrics.cost_driver_breakdown.length > 0 && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Cost Driver Decomposition</h3>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <AnalyticsFinancialCostDriverBar data={metrics.cost_driver_breakdown} />
              <div className="space-y-2">
                {metrics.cost_driver_breakdown.map((d) => (
                  <div key={d.category} className="flex items-center gap-3">
                    <span className="text-xs text-slate-400 w-32">{d.category}</span>
                    <div className="flex-1 h-1.5 rounded-full bg-navy-700">
                      <div className="h-full rounded-full bg-teal-500" style={{ width: `${d.pct_of_total}%` }} />
                    </div>
                    <span className="text-xs text-slate-400 w-12 text-right">{d.pct_of_total.toFixed(1)}%</span>
                    <DollarDisplay amount={d.amount} size="sm" showScale={false} />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </ErrorBoundary>
      )}
    </div>
  );
}
