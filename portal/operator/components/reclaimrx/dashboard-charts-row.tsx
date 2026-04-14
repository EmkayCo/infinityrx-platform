"use client";

import React from "react";
import dynamic from "next/dynamic";
import { Clock } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";

// next/dynamic({ ssr: false }) is only legal from client components in
// Next 16. This wrapper is the client boundary that hosts both lazy
// recharts leaves.
const ReclaimRxSeverityPie = dynamic(
  () =>
    import("@/components/charts/reclaimrx-severity-pie").then(
      (m) => m.ReclaimRxSeverityPie
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);

const ReclaimRxTrendLine = dynamic(
  () =>
    import("@/components/charts/reclaimrx-trend-line").then(
      (m) => m.ReclaimRxTrendLine
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);

interface Props {
  severityData: { name: string; value: number }[];
  trendData: { date: string; count: number }[];
}

export function ReclaimRxDashboardChartsRow({ severityData, trendData }: Props) {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <h3 className="text-sm font-semibold text-slate-300 mb-4">
            Severity Breakdown
          </h3>
          <ReclaimRxSeverityPie data={severityData} />
        </div>
      </ErrorBoundary>

      <ErrorBoundary>
        <div className="lg:col-span-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-300">
              Flag Trend — Last 90 Days
            </h3>
            <Clock className="w-4 h-4 text-slate-500" />
          </div>
          <ReclaimRxTrendLine data={trendData} />
        </div>
      </ErrorBoundary>
    </div>
  );
}
