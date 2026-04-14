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
} from "recharts";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { MemberAdherence, HighCostMember } from "@shared/types/analytics";
import { cn } from "@shared/lib/format";

const highCostColumns: ColDef<HighCostMember>[] = [
  { accessorKey: "member_id", header: "Member ID", cell: (c) => <span className="font-mono text-xs text-teal-400">{c.getValue() as string}</span> },
  { accessorKey: "masked_name", header: "Member", cell: (c) => <span className="text-slate-300">{c.getValue() as string}</span> },
  { accessorKey: "primary_condition", header: "Condition", cell: (c) => <span className="text-xs text-slate-400">{(c.getValue() as string) ?? "—"}</span> },
  { accessorKey: "specialty_drug_count", header: "Specialty Drugs", cell: (c) => <span className="text-yellow-400 font-medium">{c.getValue() as number}</span> },
  { accessorKey: "ytd_spend", header: "YTD Spend", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
];

const ADHERENCE_COLOR = (pdc: number, threshold: number) => {
  if (pdc >= threshold) return "#10B981";
  if (pdc >= threshold - 10) return "#F59E0B";
  return "#EF4444";
};

export default function MemberAnalyticsPage() {
  const { data: adherence = [], isLoading: adherenceLoading } = useQuery<MemberAdherence[]>({
    queryKey: ["member-adherence"],
    queryFn: () =>
      apiGet<MemberAdherence[]>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/member/adherence`)),
    staleTime: 120_000,
  });

  const { data: highCost = [], isLoading: highCostLoading } = useQuery<HighCostMember[]>({
    queryKey: ["high-cost-members"],
    queryFn: () =>
      apiGet<HighCostMember[]>(
        buildUrl(`${API_URLS.dataiq}/api/v1/analytics/member/high-cost`, { limit: 25 })
      ),
    staleTime: 60_000,
  });

  const adherenceChartData = adherence.map((a) => ({
    drug_class: a.drug_class,
    PDC: a.pdc_score,
    threshold: a.cms_threshold,
    members: a.member_count,
  }));

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Member Analytics</h1>
        <p className="text-slate-400 text-sm mt-1">Adherence, high-cost claimants, and population health</p>
      </div>

      {/* Adherence Dashboard */}
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">
            Medication Adherence (PDC) by Drug Class
          </h3>
          {adherenceLoading ? (
            <Skeleton className="h-48" />
          ) : (
            <>
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={adherenceChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                  <XAxis dataKey="drug_class" tick={{ fontSize: 10, fill: "#94A3B8" }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#94A3B8" }} tickFormatter={(v: number) => `${v}%`} />
                  <Tooltip
                    formatter={(v: number) => [`${v.toFixed(1)}%`]}
                    contentStyle={{ background: "#1E293B", border: "1px solid #334155", borderRadius: 8 }}
                  />
                  <ReferenceLine y={80} stroke="#F59E0B" strokeDasharray="5 5" label={{ value: "CMS 80%", fill: "#F59E0B", fontSize: 10 }} />
                  <Bar dataKey="PDC" name="PDC Score" radius={[3, 3, 0, 0]}>
                    {adherence.map((a, i) => (
                      <rect key={i} fill={ADHERENCE_COLOR(a.pdc_score, a.cms_threshold)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 flex flex-wrap gap-4">
                {adherence.map((a) => (
                  <div key={a.drug_class} className="text-xs">
                    <span className="text-slate-400">{a.drug_class}:</span>{" "}
                    <span className={cn(
                      "font-semibold",
                      a.pdc_score >= a.cms_threshold ? "text-green-400" : "text-yellow-400"
                    )}>
                      {a.pdc_score.toFixed(1)}%
                    </span>
                    <span className="text-slate-500"> ({a.member_count} members)</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </ErrorBoundary>

      {/* High Cost Members */}
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">
            High-Cost Claimants (Top 25 by YTD Spend)
          </h3>
          <DataTable
            columns={highCostColumns}
            data={highCost}
            isLoading={highCostLoading}
            emptyTitle="No high-cost member data"
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
