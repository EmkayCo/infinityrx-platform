"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { ExportMenu } from "@shared/components/export-menu";
import { KpiCardRow } from "@/components/ui/kpi-card-row";
import type { RecoveryRecord } from "@shared/types/reclaimrx";
import { cn, formatDate } from "@shared/lib/format";

const STATUS_BADGE: Record<string, string> = {
  new: "bg-gray-100 text-gray-600",
  assigned: "bg-blue-100 text-blue-700",
  evidence: "bg-yellow-100 text-yellow-700",
  demand: "bg-orange-100 text-orange-700",
  resolved: "bg-green-100 text-green-700",
};

const columns: ColDef<RecoveryRecord>[] = [
  {
    accessorKey: "investigation_id",
    header: "Investigation ID",
    cell: (c) => (
      <span className="font-mono text-xs text-ifx-blue">
        {(c.getValue() as string).slice(0, 8)}
      </span>
    ),
  },
  {
    accessorKey: "entity_name",
    header: "Entity",
    cell: (c) => (
      <span className="font-medium text-ifx-gray-700">{c.getValue() as string}</span>
    ),
  },
  {
    accessorKey: "flag_type",
    header: "Flag Type",
    cell: (c) => (
      <span className="text-xs text-ifx-gray-400 capitalize">
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
        <span
          className={cn(
            "text-sm font-mono",
            val < 0 ? "text-red-500" : "text-green-600"
          )}
        >
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
          "text-xs px-2 py-0.5 rounded-full capitalize",
          STATUS_BADGE[c.getValue() as string] ?? "bg-gray-100 text-gray-600"
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
      <span className="text-xs text-ifx-gray-400">{formatDate(c.getValue() as string)}</span>
    ),
  },
];

interface Props {
  records: RecoveryRecord[];
}

export function RecoveryInteractive({ records }: Props) {
  const router = useRouter();

  const totals = records.reduce(
    (acc, r) => ({
      estimated: acc.estimated + parseFloat(r.estimated || "0"),
      demanded: acc.demanded + parseFloat(r.demanded || "0"),
      collected: acc.collected + parseFloat(r.collected || "0"),
    }),
    { estimated: 0, demanded: 0, collected: 0 }
  );

  const recoveryRate =
    totals.estimated > 0 ? (totals.collected / totals.estimated) * 100 : 0;

  const pending = totals.demanded - totals.collected;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ifx-gray-900">Recovery Tracking</h1>
          <p className="text-ifx-gray-400 text-sm mt-1">
            {records.length} investigations tracked
          </p>
        </div>
        <ExportMenu
          onExportCsv={() => {
            /* export */
          }}
          onExportExcel={() => {
            /* export */
          }}
        />
      </div>

      {/* KPI Cards */}
      <KpiCardRow
        columns={5}
        cards={[
          {
            label: "Total Identified",
            value: totals.estimated.toFixed(2),
            format: "currency-compact",
            accentColor: "var(--ifx-blue, #324AB2)",
          },
          {
            label: "Total Recovered",
            value: totals.collected.toFixed(2),
            format: "currency-compact",
            accentColor: "var(--ifx-success, #10B981)",
          },
          {
            label: "Recovery Rate",
            value: recoveryRate.toFixed(1) + "%",
            format: "raw",
            accentColor:
              recoveryRate >= 50
                ? "var(--ifx-success, #10B981)"
                : "var(--ifx-error, #EF4444)",
          },
          {
            label: "Pending Recovery",
            value: Math.max(0, pending).toFixed(2),
            format: "currency-compact",
            accentColor: "var(--ifx-warning, #F59E0B)",
          },
          {
            label: "Avg Time to Recover",
            value: "34d",
            format: "raw",
            accentColor: "var(--ifx-gray-300, #9BA3B5)",
          },
        ]}
      />

      {/* Table */}
      <div className="bg-white rounded-lg ifx-card-shadow p-5">
        <DataTable
          columns={columns}
          data={records}
          emptyTitle="No recovery records"
          emptyDescription="Completed investigations with recovery amounts will appear here."
          onRowClick={(r: RecoveryRecord) =>
            router.push(`/reclaimrx/investigations/${r.investigation_id}`)
          }
        />
      </div>
    </div>
  );
}
