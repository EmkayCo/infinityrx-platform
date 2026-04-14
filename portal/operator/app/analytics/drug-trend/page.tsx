"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { DrugTrendPoint, GenericBrandBreakdown } from "@shared/types/analytics";
import { cn } from "@shared/lib/format";

const AnalyticsDrugTrendSpendLine = dynamic(
  () =>
    import("@/components/charts/analytics-drug-trend-spend-line").then(
      (m) => m.AnalyticsDrugTrendSpendLine
    ),
  { ssr: false, loading: () => <Skeleton className="h-64" /> }
);

const AnalyticsDrugTrendBrandGenericPie = dynamic(
  () =>
    import("@/components/charts/analytics-drug-trend-brand-generic-pie").then(
      (m) => m.AnalyticsDrugTrendBrandGenericPie
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);

const AnalyticsDrugTrendTopDrugsBar = dynamic(
  () =>
    import("@/components/charts/analytics-drug-trend-top-drugs-bar").then(
      (m) => m.AnalyticsDrugTrendTopDrugsBar
    ),
  { ssr: false, loading: () => <Skeleton className="h-80" /> }
);

type DrugTab = "spend_trend" | "brand_generic" | "glp1" | "biosimilar" | "top_drugs";

const TABS: { id: DrugTab; label: string }[] = [
  { id: "spend_trend", label: "Spend Trend" },
  { id: "brand_generic", label: "Brand vs Generic" },
  { id: "glp1", label: "GLP-1 Tracker" },
  { id: "biosimilar", label: "Biosimilar Adoption" },
  { id: "top_drugs", label: "Top by Spend" },
];

interface TopDrug {
  drug_name: string;
  ndc: string;
  total_spend: string;
  claim_count: number;
  category: string;
}

export default function DrugTrendPage() {
  const [activeTab, setActiveTab] = useState<DrugTab>("spend_trend");

  const { data: spendTrend = [], isLoading: spendLoading } = useQuery<DrugTrendPoint[]>({
    queryKey: ["drug-spend-trend"],
    queryFn: () =>
      apiGet<DrugTrendPoint[]>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/drug/spend-trend`)),
    staleTime: 120_000,
    enabled: activeTab === "spend_trend",
  });

  const { data: breakdown, isLoading: breakdownLoading } = useQuery<GenericBrandBreakdown>({
    queryKey: ["brand-generic-breakdown"],
    queryFn: () =>
      apiGet<GenericBrandBreakdown>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/drug/brand-generic`)),
    staleTime: 120_000,
    enabled: activeTab === "brand_generic" || activeTab === "glp1" || activeTab === "biosimilar",
  });

  const { data: topDrugs = [], isLoading: topLoading } = useQuery<TopDrug[]>({
    queryKey: ["top-drugs-by-spend"],
    queryFn: () =>
      apiGet<TopDrug[]>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/drug/top-by-spend`, { limit: 20 })),
    staleTime: 120_000,
    enabled: activeTab === "top_drugs",
  });

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Drug Trend Dashboards</h1>
        <p className="text-slate-400 text-sm mt-1">Drug spend analysis and utilization trends</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-ifx-border-dark">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors",
              activeTab === tab.id
                ? "border-teal-500 text-teal-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Spend Trend */}
      {activeTab === "spend_trend" && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Drug Spend Trend</h3>
            {spendLoading ? <Skeleton className="h-64" /> : (
              <AnalyticsDrugTrendSpendLine data={spendTrend} />
            )}
          </div>
        </ErrorBoundary>
      )}

      {/* Brand vs Generic */}
      {activeTab === "brand_generic" && (
        <ErrorBoundary>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-4">Brand vs Generic Split</h3>
              {breakdownLoading ? <Skeleton className="h-48" /> : breakdown ? (
                <>
                  <AnalyticsDrugTrendBrandGenericPie breakdown={breakdown} />
                  <div className="grid grid-cols-2 gap-3 mt-3">
                    <div>
                      <p className="text-xs text-slate-400">Brand Spend</p>
                      <DollarDisplay amount={breakdown.brand_spend} size="md" />
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Generic Spend</p>
                      <DollarDisplay amount={breakdown.generic_spend} size="md" />
                    </div>
                  </div>
                </>
              ) : null}
            </div>

            <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-4">Specialty Segments</h3>
              {breakdown && (
                <div className="space-y-4">
                  <div>
                    <p className="text-xs text-slate-400 mb-1">GLP-1 Spend</p>
                    <DollarDisplay amount={breakdown.glp1_spend} size="lg" />
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Biosimilar Spend</p>
                    <DollarDisplay amount={breakdown.biosimilar_spend} size="lg" />
                  </div>
                </div>
              )}
            </div>
          </div>
        </ErrorBoundary>
      )}

      {/* GLP-1 */}
      {activeTab === "glp1" && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-200">GLP-1 Tracker</h3>
              {breakdown && <DollarDisplay amount={breakdown.glp1_spend} size="lg" />}
            </div>
            <p className="text-sm text-slate-400">
              GLP-1 agonist spend tracking (semaglutide, tirzepatide, liraglutide, etc.)
            </p>
            {breakdownLoading && <Skeleton className="h-40 mt-4" />}
          </div>
        </ErrorBoundary>
      )}

      {/* Biosimilar */}
      {activeTab === "biosimilar" && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-200">Biosimilar Adoption</h3>
              {breakdown && <DollarDisplay amount={breakdown.biosimilar_spend} size="lg" />}
            </div>
            <p className="text-sm text-slate-400">
              Biosimilar utilization and spend tracking vs reference biologic.
            </p>
            {breakdownLoading && <Skeleton className="h-40 mt-4" />}
          </div>
        </ErrorBoundary>
      )}

      {/* Top Drugs */}
      {activeTab === "top_drugs" && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Top 20 Drugs by Spend</h3>
            {topLoading ? <Skeleton className="h-80" /> : (
              <AnalyticsDrugTrendTopDrugsBar data={topDrugs} />
            )}
          </div>
        </ErrorBoundary>
      )}
    </div>
  );
}
