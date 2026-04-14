"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { DollarDisplay } from "@shared/components/dollar-display";
import { ExportMenu } from "@shared/components/export-menu";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { MedicalClaim, MedicalClaimStatus } from "@shared/types/medical-claims";
import { cn, formatDate } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const STATUS_BADGE: Record<MedicalClaimStatus, string> = {
  pending: "bg-yellow-900/40 text-yellow-300",
  approved: "bg-green-900/40 text-green-300",
  denied: "bg-red-900/40 text-red-300",
  adjusted: "bg-blue-900/40 text-blue-300",
  void: "bg-slate-700 text-slate-400",
};

const columns: ColDef<MedicalClaim>[] = [
  {
    accessorKey: "claim_number",
    header: "Claim #",
    cell: (c) => <span className="font-mono text-xs text-teal-400">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "hcpcs_code",
    header: "HCPCS",
    cell: (c) => <span className="font-mono text-xs font-semibold text-white">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "drug_name",
    header: "Drug",
    cell: (c) => <span className="text-sm text-slate-300">{(c.getValue() as string) ?? "—"}</span>,
  },
  {
    accessorKey: "provider_name",
    header: "Provider",
    cell: (c) => <span className="text-sm text-slate-300">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "masked_member_name",
    header: "Member",
    cell: (c) => <span className="text-sm text-slate-400">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "date_of_service",
    header: "DOS",
    cell: (c) => <span className="text-xs text-slate-400">{formatDate(c.getValue() as string)}</span>,
  },
  {
    accessorKey: "billed_amount",
    header: "Billed",
    cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" />,
  },
  {
    accessorKey: "paid_amount",
    header: "Paid",
    cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" />,
  },
  {
    accessorKey: "is_340b",
    header: "340B",
    cell: (c) => c.getValue() ? (
      <span className="text-xs px-1.5 py-0.5 rounded bg-purple-900/40 text-purple-300">340B</span>
    ) : null,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: (c) => (
      <span className={cn("text-xs px-2 py-0.5 rounded capitalize", STATUS_BADGE[c.getValue() as MedicalClaimStatus])}>
        {c.getValue() as string}
      </span>
    ),
  },
];

export default function MedicalClaimsPage() {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = useState<MedicalClaimStatus | "all">("all");
  const [search, setSearch] = useState("");

  const { data: claims = [], isLoading } = useQuery<MedicalClaim[]>({
    queryKey: ["medical-claims", statusFilter, search],
    queryFn: () =>
      apiGet<MedicalClaim[]>(
        buildUrl(`${API_URLS.medicalClaims}/api/v1/claims`, {
          status: statusFilter !== "all" ? statusFilter : undefined,
          q: search || undefined,
          limit: 100,
        })
      ),
    staleTime: 30_000,
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Medical Drug Claims</h1>
          <p className="text-slate-400 text-sm mt-1">{claims.length} claims</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => router.push("/medical-claims/crosswalk")} className="px-3 py-2 rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 text-sm transition-colors">HCPCS→NDC</button>
          <button onClick={() => router.push("/medical-claims/unified-spend")} className="px-3 py-2 rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 text-sm transition-colors">Unified Spend</button>
          <button onClick={() => router.push("/medical-claims/340b")} className="px-3 py-2 rounded-lg border border-purple-700/40 text-purple-300 hover:bg-purple-900/20 text-sm transition-colors">340B</button>
          <ExportMenu onExportCsv={() => {/* export */}} onExportExcel={() => {/* export */}} />
        </div>
      </div>

      <div className="flex gap-3">
        <input
          type="search"
          placeholder="Search HCPCS, provider, claim #..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 max-w-sm px-3 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as MedicalClaimStatus | "all")}
          className="px-3 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm focus:outline-none"
        >
          <option value="all">All Statuses</option>
          {(["pending", "approved", "denied", "adjusted", "void"] as MedicalClaimStatus[]).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <DataTable
            columns={columns}
            data={claims}
            isLoading={isLoading}
            emptyTitle="No claims found"
            onRowClick={(r: MedicalClaim) => router.push(`/medical-claims/claims/${r.id}`)}
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
