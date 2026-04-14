"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Upload, CheckCircle } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { ExportMenu } from "@shared/components/export-menu";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { useAuth } from "@shared/hooks/use-auth";
import type { Member, CoverageStatus } from "@shared/types/directories";
import { Permission } from "@shared/types/auth";
import { cn, formatDate } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const COVERAGE_BADGE: Record<CoverageStatus, string> = {
  active: "bg-green-900/40 text-green-300",
  terminated: "bg-red-900/40 text-red-300",
  cobra: "bg-blue-900/40 text-blue-300",
  suspended: "bg-orange-900/40 text-orange-300",
  pending: "bg-yellow-900/40 text-yellow-300",
};

export default function MembersPage() {
  const router = useRouter();
  const { hasPermission } = useAuth();
  const canSearchByName = hasPermission(Permission.DirectoriesFull);
  const [search, setSearch] = useState("");

  const { data: members = [], isLoading } = useQuery<Member[]>({
    queryKey: ["members", search],
    queryFn: () =>
      apiGet<Member[]>(
        buildUrl(`${API_URLS.memberManagement}/api/v1/members`, {
          q: search || undefined,
          limit: 100,
        })
      ),
    staleTime: 30_000,
    enabled: search.length > 2 || search.length === 0,
  });

  const columns: ColDef<Member>[] = [
    {
      accessorKey: "member_id",
      header: "Member ID",
      cell: (c) => <span className="font-mono text-xs text-teal-400">{c.getValue() as string}</span>,
    },
    {
      accessorKey: "masked_name",
      header: "Name",
      cell: (c) => {
        const row = c.row.original;
        const name = canSearchByName ? (row.full_name ?? row.masked_name) : row.masked_name;
        return <span className="font-medium text-white">{name}</span>;
      },
    },
    {
      accessorKey: "masked_dob",
      header: "DOB",
      cell: (c) => {
        const row = c.row.original;
        const dob = canSearchByName ? (row.date_of_birth ?? row.masked_dob) : row.masked_dob;
        return <span className="text-slate-400 text-sm">{formatDate(dob ?? "")}</span>;
      },
    },
    {
      accessorKey: "coverage_status",
      header: "Coverage",
      cell: (c) => (
        <span
          className={cn(
            "text-xs px-2 py-0.5 rounded capitalize",
            COVERAGE_BADGE[c.getValue() as CoverageStatus]
          )}
        >
          {c.getValue() as string}
        </span>
      ),
    },
    {
      accessorKey: "plan_name",
      header: "Plan",
      cell: (c) => (
        <span className="text-xs text-slate-400">{(c.getValue() as string) ?? "—"}</span>
      ),
    },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Member Management</h1>
          <p className="text-slate-400 text-sm mt-1">{members.length} members</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => router.push("/directories/members/eligibility")}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 text-sm transition-colors"
          >
            <CheckCircle className="w-4 h-4" />
            Eligibility Check
          </button>
          <button
            onClick={() => router.push("/directories/members/enroll")}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors"
          >
            <Upload className="w-4 h-4" />
            Enroll Members
          </button>
          <ExportMenu onExportCsv={() => {/* export */}} />
        </div>
      </div>

      {!canSearchByName && (
        <div className="rounded-lg border border-yellow-700/20 bg-yellow-900/5 p-3 text-xs text-yellow-300">
          Name search is restricted. Searching by member ID only.
        </div>
      )}

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="search"
          placeholder={canSearchByName ? "Search ID, name, or DOB..." : "Search member ID..."}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
        />
      </div>

      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <DataTable
            columns={columns}
            data={members}
            isLoading={isLoading}
            emptyTitle="No members found"
            emptyDescription="Search by member ID, name, or date of birth."
            onRowClick={(r: Member) => router.push(`/directories/members/${r.id}`)}
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
