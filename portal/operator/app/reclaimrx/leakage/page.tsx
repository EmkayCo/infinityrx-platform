"use client";

import React, { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { LeakageFlag, LeakageCategory } from "@shared/types/reclaimrx";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { FilterPanel, type FilterField, type FilterValues } from "@/components/ui/filter-panel";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@shared/lib/format";

const CATEGORY_LABELS: Record<LeakageCategory, string> = {
  pharmacy_misuse: "Pharmacy Misuse",
  accumulator: "Accumulator",
  maximizer: "Maximizer",
  three_forty_b_overlap: "340B Overlap",
  alternative_funding: "Alt. Funding",
  prescriber_anomaly: "Prescriber Anomaly",
  patient_anomaly: "Patient Anomaly",
};

const CATEGORY_COLORS: Record<LeakageCategory, string> = {
  pharmacy_misuse: "bg-red-100 text-red-700",
  accumulator: "bg-amber-100 text-amber-700",
  maximizer: "bg-orange-100 text-orange-700",
  three_forty_b_overlap: "bg-purple-100 text-purple-700",
  alternative_funding: "bg-blue-100 text-blue-700",
  prescriber_anomaly: "bg-teal-100 text-teal-700",
  patient_anomaly: "bg-gray-100 text-gray-600",
};

const STATUS_MAP: Record<string, "active" | "inactive" | "warning" | "error" | "info" | "pending"> = {
  new: "warning",
  under_investigation: "active",
  confirmed: "error",
  dismissed: "inactive",
};

const FILTER_FIELDS: FilterField[] = [
  {
    id: "category",
    label: "Leakage Category",
    type: "multi-select",
    options: (Object.entries(CATEGORY_LABELS) as [LeakageCategory, string][]).map(
      ([value, label]) => ({ value, label })
    ),
  },
  {
    id: "entity_type",
    label: "Entity Type",
    type: "select",
    options: [
      { value: "pharmacy", label: "Pharmacy" },
      { value: "prescriber", label: "Prescriber" },
      { value: "patient", label: "Patient" },
    ],
  },
  {
    id: "status",
    label: "Status",
    type: "multi-select",
    options: [
      { value: "new", label: "New" },
      { value: "under_investigation", label: "Under Investigation" },
      { value: "confirmed", label: "Confirmed" },
      { value: "dismissed", label: "Dismissed" },
    ],
  },
  {
    id: "program",
    label: "Program",
    type: "text",
    placeholder: "Filter by program name",
  },
];

const COLUMNS: Column<LeakageFlag>[] = [
  {
    id: "id",
    header: "Flag ID",
    accessor: (r) => r.id.slice(0, 8),
    pinned: true,
    cell: (v) => <span className="font-mono text-xs text-ifx-blue">{v as string}</span>,
  },
  {
    id: "category",
    header: "Category",
    accessor: (r) => r.category,
    cell: (v, row) => (
      <span
        className={cn(
          "text-xs px-2 py-0.5 rounded-full font-medium",
          CATEGORY_COLORS[row.category] ?? "bg-gray-100 text-gray-600"
        )}
      >
        {CATEGORY_LABELS[row.category] ?? row.category}
      </span>
    ),
    sortable: true,
  },
  {
    id: "entity_name",
    header: "Entity",
    accessor: (r) => r.entity_name,
    sortable: true,
  },
  {
    id: "entity_type",
    header: "Type",
    accessor: (r) => r.entity_type,
    cell: (v) => <span className="capitalize text-xs text-ifx-gray-400">{v as string}</span>,
  },
  {
    id: "program_name",
    header: "Program",
    accessor: (r) => r.program_name ?? "—",
    sortable: true,
  },
  {
    id: "estimated_leakage",
    header: "Est. Leakage",
    accessor: (r) => r.estimated_leakage,
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
      const label = s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
      const variant = STATUS_MAP[s] ?? "pending";
      const variantMap: Record<string, import("@/components/ui/status-badge").StatusVariant> = {
        active: "success",
        inactive: "neutral",
        warning: "warning",
        error: "error",
        info: "info",
        pending: "warning",
      };
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
    id: "date_flagged",
    header: "Flagged",
    accessor: (r) => r.date_flagged.slice(0, 10),
    format: "date",
    sortable: true,
  },
];

export default function LeakageMonitorPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialCategory = searchParams.get("category");

  const [filterValues, setFilterValues] = useState<FilterValues>(
    initialCategory ? { category: [initialCategory] } : {}
  );

  const { data: flags = [], isLoading } = useQuery<LeakageFlag[]>({
    queryKey: ["leakage-flags"],
    queryFn: () =>
      apiGet<LeakageFlag[]>(buildUrl(`${API_URLS.reclaimrx}/api/v1/reclaimrx/leakage`)),
    staleTime: 60_000,
  });

  const filtered = useMemo(() => {
    return flags.filter((flag) => {
      const catFilter = filterValues.category as string[] | undefined;
      if (catFilter && catFilter.length > 0 && !catFilter.includes(flag.category)) return false;
      const typeFilter = filterValues.entity_type as string | undefined;
      if (typeFilter && flag.entity_type !== typeFilter) return false;
      const statusFilter = filterValues.status as string[] | undefined;
      if (statusFilter && statusFilter.length > 0 && !statusFilter.includes(flag.status)) return false;
      const programFilter = filterValues.program as string | undefined;
      if (programFilter && !flag.program_name?.toLowerCase().includes(programFilter.toLowerCase()))
        return false;
      return true;
    });
  }, [flags, filterValues]);

  const totalLeakage = useMemo(
    () =>
      filtered.reduce((sum, f) => sum + parseFloat(f.estimated_leakage || "0"), 0),
    [filtered]
  );

  return (
    <div className="flex gap-0 h-full min-h-0">
      {/* Filter Panel */}
      <FilterPanel
        filters={FILTER_FIELDS}
        values={filterValues}
        onChange={setFilterValues}
        onClear={() => setFilterValues({})}
        collapsible
        className="border-r border-ifx-gray-100 shrink-0"
      />

      {/* Main content */}
      <div className="flex-1 p-6 space-y-4 overflow-auto">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-500" />
              <h1 className="text-xl font-bold text-ifx-gray-900">Leakage Monitor</h1>
            </div>
            <p className="text-sm text-ifx-gray-400 mt-0.5">
              {filtered.length} flags · Est. total:{" "}
              <span className="font-semibold text-red-600">
                ${(totalLeakage / 1000).toFixed(0)}K
              </span>
            </p>
          </div>
        </div>

        <div className="bg-white rounded-lg ifx-card-shadow">
          <ConfigurableDataTable
            tableId="leakage-monitor"
            columns={COLUMNS}
            data={filtered}
            loading={isLoading}
            searchable
            exportable
            pagination={{ pageSize: 25, pageSizeOptions: [25, 50, 100] }}
            emptyMessage="No leakage flags match your filters."
            onRowClick={(row) => {
              if (row.investigation_id) {
                router.push(`/reclaimrx/investigations/${row.investigation_id}`);
              } else {
                router.push(`/reclaimrx/wizard?category=${row.category}&entity=${row.entity_id}`);
              }
            }}
          />
        </div>
      </div>
    </div>
  );
}
