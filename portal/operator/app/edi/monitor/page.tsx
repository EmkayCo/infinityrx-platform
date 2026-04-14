"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { Activity, Clock, TrendingUp } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { useSSE } from "@shared/hooks/use-sse";
import type { EDIMonitorStats } from "@shared/types/edi";
import { cn } from "@shared/lib/format";

const EdiMonitorRejectionBar = dynamic(
  () =>
    import("@/components/charts/edi-monitor-rejection-bar").then(
      (m) => m.EdiMonitorRejectionBar
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);

const EdiMonitorVolumeTrendLine = dynamic(
  () =>
    import("@/components/charts/edi-monitor-volume-trend-line").then(
      (m) => m.EdiMonitorVolumeTrendLine
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);

function GaugeCard({
  label,
  value,
  unit,
  isLoading,
  color,
}: {
  label: string;
  value: number | null;
  unit: string;
  isLoading?: boolean;
  color: string;
}) {
  if (isLoading) return <Skeleton className="h-24 rounded-lg" />;
  return (
    <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
      <p className="text-xs text-slate-400 mb-2">{label}</p>
      <p className={cn("text-3xl font-bold tabular-nums", color)}>
        {value !== null ? value.toFixed(1) : "—"}
        <span className="text-base font-normal ml-1 text-slate-400">{unit}</span>
      </p>
    </div>
  );
}

export default function EDIMonitorPage() {
  const { data: stats, isLoading } = useQuery<EDIMonitorStats>({
    queryKey: ["edi-monitor-stats"],
    queryFn: () =>
      apiGet<EDIMonitorStats>(buildUrl(`${API_URLS.edi}/api/v1/monitor/stats`)),
    staleTime: 15_000,
    refetchInterval: 15_000,
  });

  // Real-time SSE for live counters
  const { data: liveData } = useSSE<{ transactions_in_flight: number }>(
    `${API_URLS.edi}/api/v1/monitor/stream`
  );

  const inFlight = liveData?.transactions_in_flight ?? stats?.transactions_in_flight ?? 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Transaction Monitor</h1>
          <p className="text-slate-400 text-sm mt-1">Real-time EDI transaction metrics</p>
        </div>
        <div className="flex items-center gap-2 text-sm text-green-400">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          Live
        </div>
      </div>

      {/* Live + key metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-slate-400">In Flight</p>
            <Activity className="w-4 h-4 text-teal-400 animate-pulse" />
          </div>
          <p className="text-3xl font-bold text-teal-400 tabular-nums">{inFlight}</p>
        </div>
        <GaugeCard
          label="Acceptance Rate (24h)"
          value={stats ? stats.acceptance_rate_24h * 100 : null}
          unit="%"
          isLoading={isLoading}
          color="text-green-400"
        />
        <GaugeCard
          label="Acceptance Rate (7d)"
          value={stats ? stats.acceptance_rate_7d * 100 : null}
          unit="%"
          isLoading={isLoading}
          color="text-green-300"
        />
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs text-slate-400">ACK Turnaround (P95)</p>
            <Clock className="w-4 h-4 text-slate-400" />
          </div>
          {isLoading ? (
            <Skeleton className="h-8 w-24" />
          ) : (
            <p className="text-2xl font-bold text-white tabular-nums">
              {stats ? (stats.p95_ack_turnaround_ms / 1000).toFixed(1) : "—"}
              <span className="text-sm font-normal text-slate-400 ml-1">s</span>
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Rejection Codes */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">
              Top 10 Rejection Codes
            </h3>
            {isLoading ? (
              <Skeleton className="h-48" />
            ) : (
              <EdiMonitorRejectionBar data={stats?.top_rejection_codes ?? []} />
            )}
          </div>
        </ErrorBoundary>

        {/* Volume Trend */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-200">Volume Trend (30d)</h3>
              <TrendingUp className="w-4 h-4 text-slate-500" />
            </div>
            {isLoading ? (
              <Skeleton className="h-48" />
            ) : (
              <EdiMonitorVolumeTrendLine data={stats?.volume_trend_30d ?? []} />
            )}
          </div>
        </ErrorBoundary>
      </div>
    </div>
  );
}
