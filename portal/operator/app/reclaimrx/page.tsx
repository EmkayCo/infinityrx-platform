import React from "react";
import Link from "next/link";
import { ShieldCheck, AlertTriangle, TrendingUp, DollarSign } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { GTNSummary, GTNTrendPoint } from "@shared/types/reclaimrx";
import { KpiCardRow } from "@/components/ui/kpi-card-row";
import { GTNDashboardCharts } from "@/components/reclaimrx/gtn-dashboard-charts";

function fmtPct(s: string): string {
  return `${(parseFloat(s) * 100).toFixed(1)}%`;
}

export default async function GTNDashboardPage() {
  const [summary, trend] = await Promise.all([
    apiGet<GTNSummary>(buildUrl(`${API_URLS.reclaimrx}/api/v1/reclaimrx/gtn-summary`)),
    apiGet<GTNTrendPoint[]>(buildUrl(`${API_URLS.reclaimrx}/api/v1/reclaimrx/gtn-trend`)),
  ]);

  const gtnCurrent = parseFloat(summary?.gtn_ratio ?? "0");
  const gtnPrev = parseFloat(summary?.gtn_ratio_prev ?? "0");
  const gtnDelta = ((gtnCurrent - gtnPrev) / gtnPrev) * 100;

  const recoveryRate = parseFloat(summary?.recovery_rate ?? "0");

  return (
    <ErrorBoundary>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-6 h-6 text-ifx-blue" />
              <h1 className="text-2xl font-bold text-ifx-gray-900">GTN Protection Dashboard</h1>
            </div>
            <p className="text-ifx-gray-400 text-sm mt-1">
              Gross-to-net performance across all manufacturer copay programs — YTD
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/reclaimrx/wizard"
              className="px-4 py-2 rounded-lg bg-ifx-navy hover:bg-ifx-navy-dark text-white text-sm font-medium transition-colors"
            >
              + New Case
            </Link>
            <Link
              href="/reclaimrx/leakage"
              className="px-4 py-2 rounded-lg border border-ifx-gray-100 bg-white hover:bg-ifx-gray-50 text-ifx-gray-700 text-sm font-medium transition-colors"
            >
              Leakage Monitor
            </Link>
          </div>
        </div>

        {/* KPI Cards */}
        <KpiCardRow
          columns={6}
          cards={[
            {
              label: "Total Copay Spend",
              value: summary?.total_copay_spend ?? "0",
              format: "currency-compact",
              href: "/claims",
              accentColor: "var(--ifx-blue, #324AB2)",
              icon: <DollarSign className="w-4 h-4" />,
            },
            {
              label: "Identified Leakage",
              value: summary?.identified_leakage ?? "0",
              format: "currency-compact",
              href: "/reclaimrx/leakage",
              accentColor: "var(--ifx-error, #EF4444)",
              icon: <AlertTriangle className="w-4 h-4" />,
            },
            {
              label: "GTN Ratio",
              value: fmtPct(summary?.gtn_ratio ?? "0"),
              format: "raw",
              trend: {
                value: Math.abs(gtnDelta),
                direction: gtnDelta >= 0 ? "up" : "down",
                label: "vs prior period",
              },
              href: "/reclaimrx/leakage",
              accentColor: gtnCurrent >= 0.85 ? "var(--ifx-success, #10B981)" : "var(--ifx-warning, #F59E0B)",
              icon: <TrendingUp className="w-4 h-4" />,
            },
            {
              label: "Active Investigations",
              value: summary?.active_investigations ?? 0,
              format: "number",
              href: "/reclaimrx/investigations",
              accentColor: "var(--ifx-warning, #F59E0B)",
            },
            {
              label: "Recovered YTD",
              value: summary?.recovered ?? "0",
              format: "currency-compact",
              href: "/reclaimrx/recovery",
              accentColor: "var(--ifx-success, #10B981)",
            },
            {
              label: "Recovery Rate",
              value: fmtPct(summary?.recovery_rate ?? "0"),
              format: "raw",
              href: "/reclaimrx/recovery",
              accentColor:
                recoveryRate >= 0.5
                  ? "var(--ifx-success, #10B981)"
                  : "var(--ifx-error, #EF4444)",
            },
          ]}
        />

        {/* Charts — client boundary */}
        <GTNDashboardCharts
          trendData={trend ?? []}
          leakageByCategory={summary?.leakage_by_category ?? []}
          leakageByProgram={summary?.leakage_by_program ?? []}
          topFlaggedPharmacies={summary?.top_flagged_pharmacies ?? []}
        />
      </div>
    </ErrorBoundary>
  );
}
