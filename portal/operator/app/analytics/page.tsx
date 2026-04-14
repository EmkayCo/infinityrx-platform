"use client";

import React, { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { TrendingUp, DollarSign, Flag, Activity } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { useSSE } from "@shared/hooks/use-sse";
import type { LiveMetrics } from "@shared/types/analytics";
import { cn } from "@shared/lib/format";
import { useRouter } from "next/navigation";

function AnimatedCounter({ value, prev }: { value: number; prev: number }) {
  const [display, setDisplay] = useState(prev);
  const diff = value - prev;

  useEffect(() => {
    if (diff === 0) return;
    const steps = 20;
    const step = diff / steps;
    let count = 0;
    const timer = setInterval(() => {
      count++;
      setDisplay((d) => d + step);
      if (count >= steps) {
        clearInterval(timer);
        setDisplay(value);
      }
    }, 30);
    return () => clearInterval(timer);
  }, [value, diff]);

  return <span className="tabular-nums">{Math.round(display).toLocaleString()}</span>;
}

export default function AnalyticsDashboardPage() {
  const router = useRouter();
  const [prevMetrics, setPrevMetrics] = useState<LiveMetrics | null>(null);

  const { data: initialMetrics } = useQuery<LiveMetrics>({
    queryKey: ["live-metrics"],
    queryFn: () =>
      apiGet<LiveMetrics>(buildUrl(`${API_URLS.dataiq}/api/v1/metrics/live`)),
    staleTime: 10_000,
    refetchInterval: 10_000,
  });

  const { data: sseMetrics } = useSSE<LiveMetrics>(
    `${API_URLS.dataiq}/api/v1/metrics/stream`
  );

  const metrics = sseMetrics ?? initialMetrics;

  useEffect(() => {
    if (metrics) {
      setPrevMetrics(metrics);
    }
  }, [metrics]);

  const navCards = [
    { label: "Drug Trends", path: "/analytics/drug-trend", color: "text-teal-400" },
    { label: "Network Analytics", path: "/analytics/network", color: "text-blue-400" },
    { label: "Member Analytics", path: "/analytics/member", color: "text-purple-400" },
    { label: "Financial Analytics", path: "/analytics/financial", color: "text-green-400" },
    { label: "Data Quality", path: "/analytics/data-quality", color: "text-yellow-400" },
  ];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Analytics Dashboard</h1>
        <div className="flex items-center gap-2 mt-1">
          <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
          <p className="text-slate-400 text-sm">Live metrics</p>
        </div>
      </div>

      {/* Live Counters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-slate-400">Claims / Hour</span>
              <Activity className="w-4 h-4 text-teal-400 animate-pulse" />
            </div>
            {!metrics ? (
              <Skeleton className="h-10 w-32" />
            ) : (
              <div className="text-3xl font-bold text-teal-400">
                <AnimatedCounter value={metrics.claims_per_hour} prev={prevMetrics?.claims_per_hour ?? metrics.claims_per_hour} />
              </div>
            )}
            {metrics?.claims_per_hour_delta !== undefined && (
              <p className={cn("text-xs mt-1", metrics.claims_per_hour_delta >= 0 ? "text-green-400" : "text-red-400")}>
                {metrics.claims_per_hour_delta >= 0 ? "▲" : "▼"} {Math.abs(metrics.claims_per_hour_delta)} vs prior hour
              </p>
            )}
          </div>
        </ErrorBoundary>

        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-slate-400">Dollars Flowing</span>
              <DollarSign className="w-4 h-4 text-green-400" />
            </div>
            {!metrics ? (
              <Skeleton className="h-10 w-40" />
            ) : (
              <DollarDisplay amount={metrics.dollars_flowing} size="xl" />
            )}
          </div>
        </ErrorBoundary>

        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-slate-400">Flags / Day</span>
              <Flag className="w-4 h-4 text-red-400" />
            </div>
            {!metrics ? (
              <Skeleton className="h-10 w-20" />
            ) : (
              <div className="text-3xl font-bold text-red-400">
                <AnimatedCounter value={metrics.flags_per_day} prev={prevMetrics?.flags_per_day ?? metrics.flags_per_day} />
              </div>
            )}
          </div>
        </ErrorBoundary>
      </div>

      {/* Navigation to sub-pages */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {navCards.map((card) => (
          <button
            key={card.path}
            onClick={() => router.push(card.path)}
            className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5 hover:border-teal-600/40 hover:bg-navy-700/20 transition-colors text-left group"
          >
            <TrendingUp className={cn("w-5 h-5 mb-3 transition-transform group-hover:scale-110", card.color)} />
            <p className="text-sm font-medium text-white">{card.label}</p>
            <p className="text-xs text-slate-400 mt-0.5">→ View</p>
          </button>
        ))}
      </div>
    </div>
  );
}
