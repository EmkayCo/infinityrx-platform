"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from "recharts";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { SiteOfCareAnalysis } from "@shared/types/medical-claims";
import { cn } from "@shared/lib/format";

const POS_COLORS: Record<string, string> = {
  "11": "#10B981",  // Office — green
  "22": "#00B4D8",  // Outpatient Hospital — teal
  "23": "#EF4444",  // ER — red
  "21": "#F59E0B",  // Inpatient — yellow
  "24": "#8B5CF6",  // ASC — purple
  "12": "#6B7280",  // Home — gray
};

const POS_DEFAULT_COLOR = "#475569";

const columns: ColDef<SiteOfCareAnalysis>[] = [
  {
    accessorKey: "pos_description",
    header: "Place of Service",
    cell: (c) => (
      <div>
        <span className="font-medium text-white">{c.getValue() as string}</span>
        <span className="text-xs text-slate-500 ml-2">POS {c.row.original.place_of_service}</span>
      </div>
    ),
  },
  {
    accessorKey: "claim_count",
    header: "Claims",
    cell: (c) => <span className="text-slate-300 tabular-nums">{(c.getValue() as number).toLocaleString()}</span>,
  },
  {
    accessorKey: "total_billed",
    header: "Total Billed",
    cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" />,
  },
  {
    accessorKey: "total_paid",
    header: "Total Paid",
    cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" />,
  },
  {
    accessorKey: "avg_paid",
    header: "Avg Paid",
    cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" />,
  },
  {
    accessorKey: "total_paid",
    header: "Paid vs Billed",
    id: "ratio",
    cell: (c) => {
      const row = c.row.original;
      const billed = parseFloat(row.total_billed);
      const paid = parseFloat(row.total_paid);
      const ratio = billed > 0 ? (paid / billed) * 100 : 0;
      return (
        <div className="flex items-center gap-2">
          <div className="w-20 h-1.5 rounded-full bg-navy-700">
            <div
              className={cn(
                "h-full rounded-full",
                ratio >= 80 ? "bg-green-400" : ratio >= 60 ? "bg-yellow-400" : "bg-red-400"
              )}
              style={{ width: `${Math.min(ratio, 100)}%` }}
            />
          </div>
          <span className={cn(
            "text-xs tabular-nums",
            ratio >= 80 ? "text-green-400" : ratio >= 60 ? "text-yellow-400" : "text-red-400"
          )}>
            {ratio.toFixed(0)}%
          </span>
        </div>
      );
    },
  },
];

export default function SiteOfCarePage() {
  const { data: siteData = [], isLoading } = useQuery<SiteOfCareAnalysis[]>({
    queryKey: ["site-of-care-analysis"],
    queryFn: () =>
      apiGet<SiteOfCareAnalysis[]>(buildUrl(`${API_URLS.medicalClaims}/api/v1/analytics/site-of-care`)),
    staleTime: 120_000,
  });

  const totalClaims = siteData.reduce((acc, s) => acc + s.claim_count, 0);
  const totalBilled = siteData.reduce((acc, s) => acc + parseFloat(s.total_billed), 0);
  const totalPaid = siteData.reduce((acc, s) => acc + parseFloat(s.total_paid), 0);

  const chartData = siteData.map((s) => ({
    pos: s.pos_description,
    billed: parseFloat(s.total_billed),
    paid: parseFloat(s.total_paid),
    claims: s.claim_count,
    pos_code: s.place_of_service,
  }));

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Site of Care Analysis</h1>
        <p className="text-slate-400 text-sm mt-1">Cost and utilization by place of service</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <p className="text-xs text-slate-400 mb-1">Total Claims</p>
          {isLoading ? <Skeleton className="h-8 w-24" /> : (
            <p className="text-2xl font-bold text-white tabular-nums">{totalClaims.toLocaleString()}</p>
          )}
        </div>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <p className="text-xs text-slate-400 mb-1">Total Billed</p>
          {isLoading ? <Skeleton className="h-8 w-32" /> : (
            <DollarDisplay amount={totalBilled.toFixed(2)} size="lg" />
          )}
        </div>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <p className="text-xs text-slate-400 mb-1">Total Paid</p>
          {isLoading ? <Skeleton className="h-8 w-32" /> : (
            <DollarDisplay amount={totalPaid.toFixed(2)} size="lg" />
          )}
        </div>
      </div>

      {/* Cost Comparison Chart */}
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Billed vs Paid by Site of Care</h3>
          {isLoading ? <Skeleton className="h-64" /> : (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={chartData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  type="number"
                  tick={{ fontSize: 10, fill: "#94A3B8" }}
                  tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}K`}
                />
                <YAxis type="category" dataKey="pos" tick={{ fontSize: 10, fill: "#94A3B8" }} width={140} />
                <Tooltip
                  formatter={(v: number) => [`$${v.toLocaleString("en-US", { minimumFractionDigits: 2 })}`]}
                  contentStyle={{ background: "#1E293B", border: "1px solid #334155", borderRadius: 8 }}
                />
                <Legend />
                <Bar dataKey="billed" name="Billed" fill="#475569" radius={[0, 3, 3, 0]} />
                <Bar dataKey="paid" name="Paid" radius={[0, 3, 3, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={POS_COLORS[entry.pos_code] ?? POS_DEFAULT_COLOR} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </ErrorBoundary>

      {/* Site breakdown: claim volume share */}
      {!isLoading && siteData.length > 0 && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Claim Volume Share</h3>
            <div className="space-y-3">
              {siteData
                .slice()
                .sort((a, b) => b.claim_count - a.claim_count)
                .map((s) => {
                  const pct = totalClaims > 0 ? (s.claim_count / totalClaims) * 100 : 0;
                  return (
                    <div key={s.place_of_service}>
                      <div className="flex justify-between items-center mb-1">
                        <span className="text-xs text-slate-300">{s.pos_description}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-xs text-slate-400 tabular-nums">{s.claim_count.toLocaleString()} claims</span>
                          <span className="text-xs font-semibold text-slate-300 w-10 text-right">{pct.toFixed(1)}%</span>
                        </div>
                      </div>
                      <div className="h-1.5 rounded-full bg-navy-700">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${pct}%`,
                            backgroundColor: POS_COLORS[s.place_of_service] ?? POS_DEFAULT_COLOR,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </ErrorBoundary>
      )}

      {/* Data Table */}
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Site of Care Detail</h3>
          <DataTable
            columns={columns}
            data={siteData}
            isLoading={isLoading}
            emptyTitle="No site of care data"
            emptyDescription="Data will appear once medical claims have been processed."
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
