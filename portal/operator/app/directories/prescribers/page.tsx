"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, AlertTriangle } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { ExportMenu } from "@shared/components/export-menu";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Prescriber, DEAStatus, LicenseStatus } from "@shared/types/directories";
import { cn } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const DEA_BADGE: Record<DEAStatus, string> = {
  active: "bg-green-900/40 text-green-300",
  expired: "bg-red-900/40 text-red-300",
  revoked: "bg-red-900/40 text-red-400",
  none: "bg-slate-700 text-slate-500",
};

const LICENSE_BADGE: Record<LicenseStatus, string> = {
  active: "bg-green-900/40 text-green-300",
  expired: "bg-red-900/40 text-red-300",
  suspended: "bg-orange-900/40 text-orange-300",
  revoked: "bg-red-900/40 text-red-400",
};

const columns: ColDef<Prescriber>[] = [
  {
    accessorKey: "npi",
    header: "NPI",
    cell: (c) => <span className="font-mono text-xs text-teal-400">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "full_name",
    header: "Name",
    cell: (c) => <span className="font-medium text-white">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "specialty",
    header: "Specialty",
    cell: (c) => <span className="text-sm text-slate-300">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "dea_status",
    header: "DEA Status",
    cell: (c) => (
      <span className={cn("text-xs px-2 py-0.5 rounded capitalize", DEA_BADGE[c.getValue() as DEAStatus])}>
        {c.getValue() as string}
      </span>
    ),
  },
  {
    accessorKey: "state_license_status",
    header: "License",
    cell: (c) => (
      <span className={cn("text-xs px-2 py-0.5 rounded capitalize", LICENSE_BADGE[c.getValue() as LicenseStatus])}>
        {c.getValue() as string}
      </span>
    ),
  },
  {
    accessorKey: "credential_alerts",
    header: "Alerts",
    cell: (c) => {
      const alerts = c.getValue() as string[];
      return alerts.length > 0 ? (
        <span className="flex items-center gap-1 text-xs text-orange-400">
          <AlertTriangle className="w-3 h-3" />
          {alerts.length} alert{alerts.length > 1 ? "s" : ""}
        </span>
      ) : (
        <span className="text-xs text-slate-500">—</span>
      );
    },
  },
];

export default function PrescribersPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");

  const { data: prescribers = [], isLoading } = useQuery<Prescriber[]>({
    queryKey: ["prescribers", search],
    queryFn: () =>
      apiGet<Prescriber[]>(
        buildUrl(`${API_URLS.prescriberDirectory}/api/v1/prescribers`, {
          q: search || undefined,
          limit: 100,
        })
      ),
    staleTime: 60_000,
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Prescriber Directory</h1>
          <p className="text-slate-400 text-sm mt-1">{prescribers.length} prescribers</p>
        </div>
        <ExportMenu onExportCsv={() => {/* export */}} />
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="search"
          placeholder="Search NPI, name, specialty..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
        />
      </div>

      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <DataTable
            columns={columns}
            data={prescribers}
            isLoading={isLoading}
            emptyTitle="No prescribers found"
            onRowClick={(r: Prescriber) => router.push(`/directories/prescribers/${r.npi}`)}
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
