"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  RadialBarChart,
  RadialBar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { DataQualityScore } from "@shared/types/analytics";
import { cn } from "@shared/lib/format";

const SCORE_COLOR = (score: number) => {
  if (score >= 90) return "text-green-400";
  if (score >= 75) return "text-yellow-400";
  return "text-red-400";
};

const SEVERITY_BADGE: Record<string, string> = {
  high: "bg-red-900/40 text-red-300",
  medium: "bg-yellow-900/40 text-yellow-300",
  low: "bg-slate-700 text-slate-400",
};

export default function DataQualityPage() {
  const { data: quality, isLoading } = useQuery<DataQualityScore>({
    queryKey: ["data-quality"],
    queryFn: () =>
      apiGet<DataQualityScore>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/data-quality`)),
    staleTime: 120_000,
  });

  const radialData = quality
    ? [{ value: quality.overall_score, fill: quality.overall_score >= 90 ? "#10B981" : quality.overall_score >= 75 ? "#F59E0B" : "#EF4444" }]
    : [];

  const components = quality
    ? [
        { label: "Accuracy", score: quality.accuracy_score },
        { label: "Completeness", score: quality.completeness_score },
        { label: "Timeliness", score: quality.timeliness_score },
        { label: "Consistency", score: quality.consistency_score },
      ]
    : [];

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Data Quality Score</h1>
        <p className="text-slate-400 text-sm mt-1">Platform-wide data integrity metrics</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Big gauge */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5 flex flex-col items-center justify-center">
            {isLoading ? (
              <Skeleton className="w-40 h-40 rounded-full" />
            ) : (
              <>
                <ResponsiveContainer width={180} height={180}>
                  <RadialBarChart
                    cx="50%"
                    cy="50%"
                    innerRadius="60%"
                    outerRadius="100%"
                    startAngle={90}
                    endAngle={-270}
                    data={radialData}
                  >
                    <RadialBar
                      dataKey="value"
                      cornerRadius={10}
                      background={{ fill: "#1B3A5C" }}
                    />
                  </RadialBarChart>
                </ResponsiveContainer>
                <div className="-mt-16 text-center">
                  <p className={cn("text-4xl font-bold tabular-nums", SCORE_COLOR(quality?.overall_score ?? 0))}>
                    {quality?.overall_score ?? 0}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">Overall Score</p>
                </div>
              </>
            )}
          </div>
        </ErrorBoundary>

        {/* Component scores */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Components</h3>
            {isLoading ? (
              <Skeleton className="h-40" />
            ) : (
              <div className="space-y-4">
                {components.map(({ label, score }) => (
                  <div key={label}>
                    <div className="flex justify-between mb-1.5">
                      <span className="text-xs text-slate-400">{label}</span>
                      <span className={cn("text-xs font-bold", SCORE_COLOR(score))}>{score}</span>
                    </div>
                    <div className="h-2 rounded-full bg-navy-700">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all",
                          score >= 90 ? "bg-green-400" : score >= 75 ? "bg-yellow-400" : "bg-red-400"
                        )}
                        style={{ width: `${score}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </ErrorBoundary>

        {/* 90-day trend */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">90-Day Trend</h3>
            {isLoading ? <Skeleton className="h-40" /> : (
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={quality?.trend_90d ?? []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: "#94A3B8" }} tickFormatter={(v: string) => v.slice(5)} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#94A3B8" }} />
                  <Tooltip contentStyle={{ background: "#1E293B", border: "1px solid #334155", borderRadius: 8 }} />
                  <Line type="monotone" dataKey="score" stroke="#00B4D8" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </ErrorBoundary>
      </div>

      {/* Issues */}
      {quality?.component_issues && quality.component_issues.length > 0 && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Active Issues</h3>
            <div className="space-y-2">
              {quality.component_issues.map((issue, i) => (
                <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-navy-900/40">
                  <span className={cn("text-xs px-2 py-0.5 rounded flex-shrink-0 mt-0.5", SEVERITY_BADGE[issue.severity])}>
                    {issue.severity}
                  </span>
                  <div>
                    <p className="text-sm text-slate-200">{issue.component}: {issue.issue}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{issue.record_count.toLocaleString()} records affected</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </ErrorBoundary>
      )}
    </div>
  );
}
