"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { ExportMenu } from "@shared/components/export-menu";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { RecoveryRecord } from "@shared/types/reclaimrx";
import { cn, formatDate } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const STATUS_BADGE: Record<string, string> = {
  new: "bg-slate-700 text-slate-300",
  assigned: "bg-blue-900/40 text-blue-300",
  evidence: "bg-yellow-900/40 text-yellow-300",
  demand: "bg-orange-900/40 text-orange-300",
  resolved: "bg-green-900/40 text-green-300",
};

const columns: ColDef<RecoveryRecord>[] = [
  {
    accessorKey: "investigation_id",
    header: "Investigation ID",
    cell: (c) => (
      <span className="font-mono text-xs text-teal-400">
        {(c.getValue() as string).slice(0, 8)}
      </span>
    ),
  },
  {
    accessorKey: "entity_name",
    header: "Entity",
    cell: (c) => <span className="font-medium text-white">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "flag_type",
    header: "Flag Type",
    cell: (c) => (
      <span className="text-xs text-slate-300 capitalize">
        {(c.getValue() as string).replace(/_/g, " ")}
      </span>
    ),
  },
  {
    accessorKey: "estimated",
    header: "Estimated",
    cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" />,
  },
  {
    accessorKey: "demanded",
    header: "Demanded",
    cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" />,
  },
  {
    accessorKey: "collected",
    header: "Collected",
    cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" />,
  },
  {
    accessorKey: "delta",
    header: "Delta",
    cell: (c) => {
      const val = parseFloat(c.getValue() as string);
      return (
        <span className={cn("text-sm font-mono", val < 0 ? "text-red-400" : "text-green-400")}>
          {val >= 0 ? "+" : ""}
          <DollarDisplay amount={c.getValue() as string} size="sm" showScale={false} />
        </span>
      );
    },
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: (c) => (
      <span
        className={cn(
          "text-xs px-2 py-0.5 rounded capitalize",
          STATUS_BADGE[c.getValue() as string] ?? "bg-slate-700 text-slate-400"
        )}
      >
        {c.getValue() as string}
      </span>
    ),
  },
  {
    accessorKey: "updated_at",
    header: "Last Updated",
    cell: (c) => (
      <span className="text-xs text-slate-400">{formatDate(c.getValue() as string)}</span>
    ),
  },
];

export default function RecoveryPage() {
  const router = useRouter();

  const { data: records = [], isLoading } = useQuery<RecoveryRecord[]>({
    queryKey: ["recovery-records"],
    queryFn: () =>
      apiGet<RecoveryRecord[]>(
        buildUrl(`${API_URLS.reclaimrx}/api/v1/recovery`)
      ),
    staleTime: 60_000,
  });

  // Compute totals
  const totals = records.reduce(
    (acc, r) => ({
      estimated: acc.estimated + parseFloat(r.estimated || "0"),
      demanded: acc.demanded + parseFloat(r.demanded || "0"),
      collected: acc.collected + parseFloat(r.collected || "0"),
    }),
    { estimated: 0, demanded: 0, collected: 0 }
  );

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Recovery Tracking</h1>
          <p className="text-slate-400 text-sm mt-1">
            {records.length} investigations tracked
          </p>
        </div>
        <ExportMenu
          onExportCsv={() => {/* export */}}
          onExportExcel={() => {/* export */}}
        />
      </div>

      {/* Summary totals */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total Estimated", amount: totals.estimated.toFixed(2) },
          { label: "Total Demanded", amount: totals.demanded.toFixed(2) },
          { label: "Total Collected", amount: totals.collected.toFixed(2) },
        ].map(({ label, amount }) => (
          <div
            key={label}
            className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-4"
          >
            <p className="text-xs text-slate-400 mb-1">{label}</p>
            <DollarDisplay amount={amount} size="lg" />
          </div>
        ))}
      </div>

      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <DataTable
            columns={columns}
            data={records}
            isLoading={isLoading}
            emptyTitle="No recovery records"
            emptyDescription="Completed investigations with recovery amounts will appear here."
            onRowClick={(r: RecoveryRecord) =>
              router.push(`/reclaimrx/investigations/${r.investigation_id}`)
            }
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
