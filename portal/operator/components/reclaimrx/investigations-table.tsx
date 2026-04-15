"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Investigation } from "@shared/types/reclaimrx";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@shared/lib/format";

const SEVERITY_CLASSES: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high: "bg-orange-100 text-orange-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-gray-100 text-gray-500",
};

const STATUS_MAP: Record<string, "active" | "inactive" | "warning" | "error" | "info" | "pending"> = {
  new: "warning",
  assigned: "info",
  evidence: "active",
  demand: "error",
  resolved: "inactive",
};

const COLUMNS: Column<Investigation>[] = [
  {
    id: "id",
    header: "Investigation ID",
    accessor: (r) => r.id.slice(0, 8),
    pinned: true,
    cell: (v) => <span className="font-mono text-xs text-ifx-blue">{v as string}</span>,
  },
  {
    id: "entity_name",
    header: "Subject",
    accessor: (r) => r.flag.entity_name,
    sortable: true,
  },
  {
    id: "flag_type",
    header: "Flag Type",
    accessor: (r) => r.flag.flag_type.replace(/_/g, " "),
    cell: (v) => <span className="capitalize text-xs text-ifx-gray-700">{v as string}</span>,
    sortable: true,
  },
  {
    id: "severity",
    header: "Severity",
    accessor: (r) => r.flag.severity,
    cell: (v, row) => (
      <span
        className={cn(
          "text-xs px-2 py-0.5 rounded-full font-medium capitalize",
          SEVERITY_CLASSES[row.flag.severity] ?? "bg-gray-100 text-gray-600"
        )}
      >
        {row.flag.severity}
      </span>
    ),
    sortable: true,
  },
  {
    id: "estimated_recovery",
    header: "Est. Impact",
    accessor: (r) => r.estimated_recovery,
    format: "currency",
    sortable: true,
    align: "right",
  },
  {
    id: "status",
    header: "Status",
    accessor: (r) => r.status,
    cell: (v) => {
      const s = v as string;
      const label = s.charAt(0).toUpperCase() + s.slice(1);
      const variantMap: Record<string, import("@/components/ui/status-badge").StatusVariant> = {
        active: "success",
        inactive: "neutral",
        warning: "warning",
        error: "error",
        info: "info",
        pending: "warning",
      };
      const variant = STATUS_MAP[s] ?? "pending";
      return (
        <StatusBadge
          status={label}
          variant={variantMap[variant]}
        />
      );
    },
    sortable: true,
  },
  {
    id: "assigned_to_name",
    header: "Assigned To",
    accessor: (r) => r.assigned_to_name ?? "—",
    sortable: true,
  },
  {
    id: "days_open",
    header: "Days Open",
    accessor: (r) => r.days_open,
    format: "number",
    sortable: true,
    align: "right",
  },
];

export function InvestigationsTable() {
  const router = useRouter();

  const { data: investigations = [], isLoading } = useQuery<Investigation[]>({
    queryKey: ["investigations"],
    queryFn: () =>
      apiGet<Investigation[]>(buildUrl(`${API_URLS.reclaimrx}/api/v1/investigations`)),
    staleTime: 30_000,
  });

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-ifx-gray-900">Investigation Queue</h1>
          <p className="text-sm text-ifx-gray-400 mt-0.5">
            {investigations.length} active investigations
          </p>
        </div>
      </div>

      <div className="bg-white rounded-lg ifx-card-shadow">
        <ConfigurableDataTable
          tableId="investigations-table"
          columns={COLUMNS}
          data={investigations}
          loading={isLoading}
          searchable
          exportable
          pagination={{ pageSize: 25, pageSizeOptions: [25, 50, 100] }}
          emptyMessage="No investigations found."
          onRowClick={(row) =>
            router.push(`/reclaimrx/investigations/${row.id}`)
          }
        />
      </div>
    </div>
  );
}
