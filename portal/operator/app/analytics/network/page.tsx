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
  ReferenceLine,
  Cell,
} from "recharts";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { PharmacyScorecard, NetworkAdequacySummary } from "@shared/types/analytics";
import { cn } from "@shared/lib/format";

const TIER_BADGE: Record<string, string> = {
  preferred: "bg-teal-900/40 text-teal-300",
  standard: "bg-blue-900/40 text-blue-300",
  out_of_network: "bg-slate-700 text-slate-400",
};

const REJECT_COLOR = (rate: number) => {
  if (rate <= 5) return "#10B981";
  if (rate <= 10) return "#F59E0B";
  return "#EF4444";
};

const columns: ColDef<PharmacyScorecard>[] = [
  {
    accessorKey: "pharmacy_name",
    header: "Pharmacy",
    cell: (c) => <span className="font-medium text-white">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "npi",
    header: "NPI",
    cell: (c) => <span className="font-mono text-xs text-slate-400">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "network_tier",
    header: "Tier",
    cell: (c) => (
      <span className={cn(
        "text-xs px-2 py-0.5 rounded capitalize",
        TIER_BADGE[c.getValue() as string] ?? "bg-slate-700 text-slate-400"
      )}>
        {(c.getValue() as string).replace("_", " ")}
      </span>
    ),
  },
  {
    accessorKey: "claim_volume",
    header: "Claims",
    cell: (c) => <span className="text-slate-300 tabular-nums">{(c.getValue() as number).toLocaleString()}</span>,
  },
  {
    accessorKey: "avg_cost_per_claim",
    header: "Avg Cost/Claim",
    cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" />,
  },
  {
    accessorKey: "reject_rate",
    header: "Reject Rate",
    cell: (c) => {
      const rate = c.getValue() as number;
      return (
        <span className={cn(
          "text-sm font-medium tabular-nums",
          rate <= 5 ? "text-green-400" : rate <= 10 ? "text-yellow-400" : "text-red-400"
        )}>
          {rate.toFixed(1)}%
        </span>
      );
    },
  },
  {
    accessorKey: "mac_ratio",
    header: "MAC Ratio",
    cell: (c) => {
      const ratio = c.getValue() as number;
      return (
        <span className={cn(
          "text-sm tabular-nums",
          ratio >= 1.0 ? "text-green-400" : ratio >= 0.9 ? "text-yellow-400" : "text-red-400"
        )}>
          {ratio.toFixed(2)}x
        </span>
      );
    },
  },
  {
    accessorKey: "generic_dispense_rate",
    header: "Generic Rate",
    cell: (c) => {
      const gdr = c.getValue() as number;
      return (
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 rounded-full bg-navy-700 w-20">
            <div
              className={cn("h-full rounded-full", gdr >= 80 ? "bg-green-400" : gdr >= 70 ? "bg-yellow-400" : "bg-red-400")}
              style={{ width: `${Math.min(gdr, 100)}%` }}
            />
          </div>
          <span className="text-xs text-slate-400 w-10 text-right">{gdr.toFixed(0)}%</span>
        </div>
      );
    },
  },
];

export default function NetworkAnalyticsPage() {
  const { data: scorecards = [], isLoading: scorecardsLoading } = useQuery<PharmacyScorecard[]>({
    queryKey: ["pharmacy-scorecards"],
    queryFn: () =>
      apiGet<PharmacyScorecard[]>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/network/pharmacy-scorecards`)),
    staleTime: 120_000,
  });

  const { data: adequacy, isLoading: adequacyLoading } = useQuery<NetworkAdequacySummary>({
    queryKey: ["network-adequacy"],
    queryFn: () =>
      apiGet<NetworkAdequacySummary>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/network/adequacy`)),
    staleTime: 120_000,
  });

  // Cost variation: reject rate distribution across pharmacies
  const rejectRateData = scorecards.map((s) => ({
    name: s.pharmacy_name.split(" ")[0],
    reject_rate: s.reject_rate,
    mac_ratio: s.mac_ratio,
    tier: s.network_tier,
  }));

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Network Analytics</h1>
        <p className="text-slate-400 text-sm mt-1">Pharmacy scorecards, network adequacy, and cost variation</p>
      </div>

      {/* Network Adequacy */}
      <ErrorBoundary>
        {adequacyLoading ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
                <Skeleton className="h-8 w-24" />
              </div>
            ))}
          </div>
        ) : adequacy ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "Members w/in 5 mi", value: `${adequacy.coverage_pct_5mi.toFixed(1)}%`, sub: `${adequacy.members_within_5mi.toLocaleString()} members` },
              { label: "Members w/in 10 mi", value: `${adequacy.coverage_pct_10mi.toFixed(1)}%`, sub: `${adequacy.members_within_10mi.toLocaleString()} members` },
              { label: "Total Members", value: adequacy.total_members.toLocaleString(), sub: "enrolled" },
              { label: "Gap Counties", value: adequacy.gap_counties.length.toString(), sub: adequacy.gap_counties.slice(0, 2).join(", ") || "None identified" },
            ].map(({ label, value, sub }) => (
              <div key={label} className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
                <p className="text-xs text-slate-400 mb-1">{label}</p>
                <p className="text-2xl font-bold text-white tabular-nums">{value}</p>
                <p className="text-xs text-slate-500 mt-0.5 truncate">{sub}</p>
              </div>
            ))}
          </div>
        ) : null}
      </ErrorBoundary>

      {/* Reject Rate + MAC Ratio Charts side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Reject Rate by Pharmacy</h3>
            {scorecardsLoading ? <Skeleton className="h-48" /> : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={rejectRateData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#94A3B8" }} />
                  <YAxis tick={{ fontSize: 10, fill: "#94A3B8" }} tickFormatter={(v: number) => `${Number(v)}%`} />
                  <Tooltip
                    formatter={(v) => [`${Number(v).toFixed(1)}%`, "Reject Rate"]}
                    contentStyle={{ background: "#1E293B", border: "1px solid #334155", borderRadius: 8 }}
                  />
                  <ReferenceLine y={10} stroke="#F59E0B" strokeDasharray="5 5" label={{ value: "10% target", fill: "#F59E0B", fontSize: 10 }} />
                  <Bar dataKey="reject_rate" name="Reject Rate" radius={[3, 3, 0, 0]}>
                    {rejectRateData.map((entry, i) => (
                      <Cell key={i} fill={REJECT_COLOR(entry.reject_rate)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </ErrorBoundary>

        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">MAC Ratio Distribution</h3>
            {scorecardsLoading ? <Skeleton className="h-48" /> : (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={rejectRateData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#94A3B8" }} />
                  <YAxis domain={[0, 1.5]} tick={{ fontSize: 10, fill: "#94A3B8" }} tickFormatter={(v: number) => `${Number(v).toFixed(1)}x`} />
                  <Tooltip
                    formatter={(v) => [`${Number(v).toFixed(2)}x`, "MAC Ratio"]}
                    contentStyle={{ background: "#1E293B", border: "1px solid #334155", borderRadius: 8 }}
                  />
                  <ReferenceLine y={1.0} stroke="#10B981" strokeDasharray="5 5" label={{ value: "1.0x parity", fill: "#10B981", fontSize: 10 }} />
                  <Bar dataKey="mac_ratio" name="MAC Ratio" fill="#00B4D8" radius={[3, 3, 0, 0]}>
                    {rejectRateData.map((entry, i) => (
                      <Cell key={i} fill={entry.mac_ratio >= 1.0 ? "#10B981" : entry.mac_ratio >= 0.9 ? "#F59E0B" : "#EF4444"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </ErrorBoundary>
      </div>

      {/* Pharmacy Scorecard Table */}
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Pharmacy Scorecards</h3>
          <DataTable
            columns={columns}
            data={scorecards}
            isLoading={scorecardsLoading}
            emptyTitle="No scorecard data"
            emptyDescription="Scorecard data will appear once claims have been processed."
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
