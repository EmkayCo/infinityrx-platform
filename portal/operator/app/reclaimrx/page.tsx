"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { AlertTriangle, TrendingUp, ShieldAlert, Clock } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { ExportMenu } from "@shared/components/export-menu";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { FWADashboardStats, FlagSeverity } from "@shared/types/reclaimrx";
import { cn } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const SEVERITY_COLORS: Record<FlagSeverity, string> = {
  critical: "#EF4444",
  high: "#F97316",
  medium: "#F59E0B",
  low: "#6B7280",
};

function StatCard({
  label,
  value,
  icon: Icon,
  color,
  isLoading,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  color: string;
  isLoading?: boolean;
}) {
  if (isLoading) return <Skeleton className="h-24 rounded-lg" />;
  return (
    <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-slate-400">{label}</span>
        <Icon className={cn("w-5 h-5", color)} />
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  );
}

interface TopEntity {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  flag_count: number;
  estimated_recovery: string;
}

const topEntityColumns: ColDef<TopEntity>[] = [
  { accessorKey: "entity_name", header: "Entity", cell: (c) => <span className="font-medium text-white">{c.getValue() as string}</span> },
  { accessorKey: "entity_type", header: "Type", cell: (c) => <span className="capitalize text-slate-300">{c.getValue() as string}</span> },
  { accessorKey: "flag_count", header: "Flags", cell: (c) => <span className="text-yellow-400 font-semibold">{c.getValue() as number}</span> },
  {
    accessorKey: "estimated_recovery",
    header: "Est. Recovery",
    cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" />,
  },
];

export default function ReclaimRxPage() {
  const router = useRouter();
  const { data: stats, isLoading, error } = useQuery<FWADashboardStats>({
    queryKey: ["fwa-dashboard-stats"],
    queryFn: () =>
      apiGet<FWADashboardStats>(buildUrl(`${API_URLS.reclaimrx}/api/v1/fwa/dashboard`)),
    staleTime: 60_000,
    retry: 2,
  });

  const severityData = stats
    ? Object.entries(stats.severity_breakdown).map(([name, value]) => ({
        name,
        value,
      }))
    : [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">FWA Dashboard</h1>
          <p className="text-slate-400 text-sm mt-1">
            Fraud, waste, and abuse flag monitoring
          </p>
        </div>
        <button
          onClick={() => router.push("/reclaimrx/investigations")}
          className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors"
        >
          Investigation Queue →
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-900/10 p-4 text-sm text-red-400">
          Service temporarily unavailable — showing cached data if available
        </div>
      )}

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="New Flags Today"
          value={stats?.new_flags_today ?? 0}
          icon={AlertTriangle}
          color="text-red-400"
          isLoading={isLoading}
        />
        <StatCard
          label="New Flags This Week"
          value={stats?.new_flags_this_week ?? 0}
          icon={ShieldAlert}
          color="text-orange-400"
          isLoading={isLoading}
        />
        <StatCard
          label="Critical Flags"
          value={stats?.severity_breakdown?.critical ?? 0}
          icon={AlertTriangle}
          color="text-red-500"
          isLoading={isLoading}
        />
        <StatCard
          label="High Severity"
          value={stats?.severity_breakdown?.high ?? 0}
          icon={TrendingUp}
          color="text-orange-400"
          isLoading={isLoading}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Severity Breakdown Pie */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-300 mb-4">
              Severity Breakdown
            </h3>
            {isLoading ? (
              <Skeleton className="h-48" />
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={severityData}
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={80}
                    dataKey="value"
                    label={({ name, percent }) =>
                      `${name} ${Math.round((percent ?? 0) * 100)}%`
                    }
                    labelLine={false}
                  >
                    {severityData.map((entry) => (
                      <Cell
                        key={entry.name}
                        fill={SEVERITY_COLORS[entry.name as FlagSeverity] ?? "#6B7280"}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "#1E293B",
                      border: "1px solid #334155",
                      borderRadius: 8,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </ErrorBoundary>

        {/* Trend Chart */}
        <ErrorBoundary>
          <div className="lg:col-span-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-300">
                Flag Trend — Last 90 Days
              </h3>
              <Clock className="w-4 h-4 text-slate-500" />
            </div>
            {isLoading ? (
              <Skeleton className="h-48" />
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={stats?.trend_90d ?? []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "#94A3B8" }}
                    tickFormatter={(v: string) => v.slice(5)}
                  />
                  <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} />
                  <Tooltip
                    contentStyle={{
                      background: "#1E293B",
                      border: "1px solid #334155",
                      borderRadius: 8,
                    }}
                  />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="count"
                    stroke="#00B4D8"
                    strokeWidth={2}
                    dot={false}
                    name="Flags"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </ErrorBoundary>
      </div>

      {/* Top Flagged Entities */}
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-slate-300">
              Top Flagged Entities
            </h3>
            <ExportMenu
              onExportCsv={() => {/* export logic */}}
            />
          </div>
          <DataTable
            columns={topEntityColumns}
            data={stats?.top_flagged_entities ?? []}
            isLoading={isLoading}
            emptyTitle="No flagged entities"
            emptyDescription="No FWA flags have been detected yet."
            getRowId={(r: TopEntity) => r.entity_id}
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
