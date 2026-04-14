"use client";

import React, { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ChevronLeft, Shield } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { useAuth } from "@shared/hooks/use-auth";
import type { Member, MemberAccumulator } from "@shared/types/directories";
import { Permission } from "@shared/types/auth";
import { cn, formatDate } from "@shared/lib/format";

// Cache-Control: no-store applied via page metadata for PHI compliance
export const dynamic = "force-dynamic";

interface ClaimRecord {
  id: string;
  date_of_service: string;
  pharmacy_name: string;
  drug_name: string;
  billed_amount: string;
  paid_amount: string;
  copay: string;
  status: string;
}

const claimColumns: ColDef<ClaimRecord>[] = [
  { accessorKey: "date_of_service", header: "DOS", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "pharmacy_name", header: "Pharmacy" },
  { accessorKey: "drug_name", header: "Drug" },
  { accessorKey: "billed_amount", header: "Billed", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "paid_amount", header: "Paid", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "copay", header: "Copay", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "status", header: "Status", cell: (c) => <span className="text-xs capitalize text-slate-300">{c.getValue() as string}</span> },
];

function AccumulatorBars({ acc }: { acc: MemberAccumulator }) {
  const deductiblePct = Math.min(
    100,
    (parseFloat(acc.deductible_applied) / parseFloat(acc.deductible_limit)) * 100
  );
  const oopPct = Math.min(
    100,
    (parseFloat(acc.oop_applied) / parseFloat(acc.oop_limit)) * 100
  );

  return (
    <div className="space-y-4">
      {[
        {
          label: "Deductible",
          applied: acc.deductible_applied,
          limit: acc.deductible_limit,
          pct: deductiblePct,
          color: "bg-teal-500",
        },
        {
          label: "Out-of-Pocket Maximum",
          applied: acc.oop_applied,
          limit: acc.oop_limit,
          pct: oopPct,
          color: deductiblePct >= 100 ? "bg-green-500" : "bg-blue-500",
        },
      ].map(({ label, applied, limit, pct, color }) => (
        <div key={label}>
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-xs text-slate-400">{label}</span>
            <span className="text-xs text-slate-400">
              <DollarDisplay amount={applied} size="sm" showScale={false} /> / <DollarDisplay amount={limit} size="sm" showScale={false} />
            </span>
          </div>
          <div className="h-2.5 rounded-full bg-navy-700 overflow-hidden">
            <div
              className={cn("h-full rounded-full transition-all duration-500", color)}
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-xs text-slate-500 mt-0.5">{Math.round(pct)}% used</p>
        </div>
      ))}
      <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
        <span>Benefit Phase:</span>
        <span className="capitalize text-teal-300">
          {acc.benefit_phase.replace(/_/g, " ")}
        </span>
      </div>
    </div>
  );
}

export default function MemberDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { hasPermission } = useAuth();
  const canViewFullPHI = hasPermission(Permission.DirectoriesFull);

  const { data: member, isLoading } = useQuery<Member>({
    queryKey: ["member", id],
    queryFn: () => apiGet<Member>(`${API_URLS.memberManagement}/api/v1/members/${id}`),
    staleTime: 30_000,
  });

  // PHI access audit beacon
  useEffect(() => {
    if (member) {
      void fetch(
        `${API_URLS.memberManagement}/api/v1/members/${id}/audit-access`,
        { method: "POST" }
      );
    }
  }, [id, member]);

  const { data: claims = [], isLoading: claimsLoading } = useQuery<ClaimRecord[]>({
    queryKey: ["member-claims", id],
    queryFn: () =>
      apiGet<ClaimRecord[]>(
        buildUrl(`${API_URLS.memberManagement}/api/v1/members/${id}/claims`, { limit: 50 })
      ),
    enabled: !!member,
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-48 rounded-lg" />
          <Skeleton className="h-48 rounded-lg" />
        </div>
      </div>
    );
  }

  if (!member) return <div className="p-6"><p className="text-slate-400">Member not found.</p></div>;

  const displayName = canViewFullPHI ? (member.full_name ?? member.masked_name) : member.masked_name;
  const displayDOB = canViewFullPHI ? (member.date_of_birth ?? member.masked_dob) : member.masked_dob;

  return (
    <div className="p-6 space-y-6">
      {/* PHI notice */}
      {!canViewFullPHI && (
        <div className="rounded-lg border border-yellow-700/20 bg-yellow-900/5 p-3 flex items-center gap-2 text-xs text-yellow-300">
          <Shield className="w-4 h-4 flex-shrink-0" />
          PHI is masked based on your role. Contact your administrator for full access.
        </div>
      )}

      <div className="flex items-center gap-4">
        <button onClick={() => router.back()} className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 transition-colors">
          <ChevronLeft className="w-4 h-4" /> Back
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-white">{displayName}</h1>
          <p className="text-slate-400 text-sm">Member ID: {member.member_id}</p>
        </div>
        <span className={cn(
          "text-sm px-3 py-1 rounded-lg capitalize",
          member.coverage_status === "active" ? "bg-green-900/40 text-green-300" : "bg-red-900/40 text-red-300"
        )}>
          {member.coverage_status}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Demographics */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Demographics</h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-500">Date of Birth</span>
                <span className="text-slate-300">{formatDate(displayDOB ?? "")}</span>
              </div>
              {member.gender && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Gender</span>
                  <span className="text-slate-300 capitalize">{member.gender}</span>
                </div>
              )}
            </div>
          </div>
        </ErrorBoundary>

        {/* Coverage Card */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Coverage</h3>
            <div className="space-y-2 text-xs">
              {member.plan_name && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Plan</span>
                  <span className="text-slate-300">{member.plan_name}</span>
                </div>
              )}
              {member.group_id && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Group ID</span>
                  <span className="text-slate-300 font-mono">{member.group_id}</span>
                </div>
              )}
              {member.coverage_effective_date && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Effective</span>
                  <span className="text-slate-300">{formatDate(member.coverage_effective_date)}</span>
                </div>
              )}
              {member.coverage_term_date && (
                <div className="flex justify-between">
                  <span className="text-slate-500">Term Date</span>
                  <span className="text-red-400">{formatDate(member.coverage_term_date)}</span>
                </div>
              )}
            </div>
          </div>
        </ErrorBoundary>

        {/* Accumulators */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">
              Accumulators ({member.accumulator?.benefit_year ?? new Date().getFullYear()})
            </h3>
            {member.accumulator ? (
              <AccumulatorBars acc={member.accumulator} />
            ) : (
              <p className="text-xs text-slate-500 italic">No accumulator data available.</p>
            )}
          </div>
        </ErrorBoundary>
      </div>

      {/* Claims History */}
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Claims History</h3>
          <DataTable
            columns={claimColumns}
            data={claims}
            isLoading={claimsLoading}
            emptyTitle="No claims found"
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
