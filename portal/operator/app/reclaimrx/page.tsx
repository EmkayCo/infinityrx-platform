import React from "react";
import Link from "next/link";
import { AlertTriangle, TrendingUp, ShieldAlert } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { FWADashboardStats } from "@shared/types/reclaimrx";
import { cn } from "@shared/lib/format";
import { TopFlaggedEntitiesCard } from "@/components/reclaimrx/top-flagged-entities-card";
import { ReclaimRxDashboardChartsRow } from "@/components/reclaimrx/dashboard-charts-row";

function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
  color: string;
}) {
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

// Server Component. Fetches the FWA dashboard stats at request time.
// Under the hood this routes through mockResponse → getInvestigations()
// → loadAgg("investigations"), which now reads the aggregated JSON from
// disk directly during SSR (no self-HTTP-loop).
export default async function ReclaimRxPage() {
  const stats = await apiGet<FWADashboardStats>(
    buildUrl(`${API_URLS.reclaimrx}/api/v1/fwa/dashboard`)
  );

  const severityData = stats?.severity_breakdown
    ? Object.entries(stats.severity_breakdown).map(
        ([name, value]) => ({ name, value })
      )
    : [];

  return (
    <ErrorBoundary>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">FWA Dashboard</h1>
            <p className="text-slate-400 text-sm mt-1">
              Fraud, waste, and abuse flag monitoring
            </p>
          </div>
          <Link
            href="/reclaimrx/investigations"
            className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors"
          >
            Investigation Queue →
          </Link>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="New Flags Today"
            value={stats.new_flags_today ?? 0}
            icon={AlertTriangle}
            color="text-red-400"
          />
          <StatCard
            label="New Flags This Week"
            value={stats.new_flags_this_week ?? 0}
            icon={ShieldAlert}
            color="text-orange-400"
          />
          <StatCard
            label="Critical Flags"
            value={stats.severity_breakdown?.critical ?? 0}
            icon={AlertTriangle}
            color="text-red-500"
          />
          <StatCard
            label="High Severity"
            value={stats.severity_breakdown?.high ?? 0}
            icon={TrendingUp}
            color="text-orange-400"
          />
        </div>

        {/* Charts row — client boundary (recharts needs browser DOM) */}
        <ReclaimRxDashboardChartsRow
          severityData={severityData}
          trendData={stats.trend_90d ?? []}
        />

        {/* Top Flagged Entities */}
        <ErrorBoundary>
          <TopFlaggedEntitiesCard entities={stats.top_flagged_entities ?? []} />
        </ErrorBoundary>
      </div>
    </ErrorBoundary>
  );
}
