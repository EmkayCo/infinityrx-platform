"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { FilterPanel, type FilterField, type FilterValues } from "@/components/ui/filter-panel";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { Skeleton } from "@shared/components/skeleton";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";

const AnalyticsStateChoropleth = dynamic(
  () => import("@/components/charts/analytics/state-choropleth").then((m) => m.AnalyticsStateChoropleth),
  { ssr: false, loading: () => <Skeleton className="h-80" /> }
);

interface GeographyData {
  states: {
    state_abbr: string; state_name: string; claim_count: number;
    spend: string; pharmacy_count: number; avg_benefit: string; abandonment_rate: number;
  }[];
  total_states_active: number;
}

type MetricOption = "claim_count" | "spend";

const FILTERS: FilterField[] = [
  { id: "date_from", label: "Date From", type: "date" },
  { id: "date_to", label: "Date To", type: "date" },
  { id: "drug", label: "Drug / NDC", type: "text" },
  { id: "plan", label: "Plan / BIN", type: "text" },
  { id: "group", label: "Group", type: "text" },
];

const STATE_COLUMNS: Column<GeographyData["states"][number]>[] = [
  { id: "state_name", header: "State", accessor: (r) => r.state_name, defaultVisible: true, sortable: true },
  { id: "state_abbr", header: "Abbr", accessor: (r) => r.state_abbr, defaultVisible: true },
  { id: "claim_count", header: "Claim Count", accessor: (r) => r.claim_count, format: "number", defaultVisible: true, sortable: true, align: "right" },
  { id: "spend", header: "Total Spend", accessor: (r) => r.spend, format: "currency", defaultVisible: true, sortable: true, align: "right" },
  { id: "pharmacy_count", header: "Pharmacies", accessor: (r) => r.pharmacy_count, format: "number", defaultVisible: true, align: "right" },
  { id: "avg_benefit", header: "Avg Benefit", accessor: (r) => r.avg_benefit, format: "currency", defaultVisible: true, align: "right" },
  { id: "abandonment_rate", header: "Abandonment", accessor: (r) => r.abandonment_rate, defaultVisible: true, align: "right",
    cell: (v) => `${(Number(v) * 100).toFixed(1)}%` },
];

export default function GeographicAnalysisPage() {
  const [filters, setFilters] = useState<FilterValues>({});
  const [metric, setMetric] = useState<MetricOption>("claim_count");
  const [selectedState, setSelectedState] = useState<string | null>(null);

  const { data, isLoading } = useQuery<GeographyData>({
    queryKey: ["analytics-geography-summary", filters],
    queryFn: () => apiGet<GeographyData>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/geography/summary`)),
    staleTime: 120_000,
  });

  const tableData = data ? (
    selectedState
      ? data.states.filter((s) => s.state_abbr === selectedState)
      : data.states
  ).sort((a, b) => b.claim_count - a.claim_count) : [];

  return (
    <div className="flex gap-4">
      <FilterPanel filters={FILTERS} values={filters} onChange={setFilters} onClear={() => setFilters({})} />

      <div className="flex-1 min-w-0 space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">Analytics</span>
            <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Geographic Analysis</h1>
            <p className="mt-1 text-sm text-ifx-gray-400">
              State-level claim distribution. Click a state to filter the table below.
              {data && ` · ${data.total_states_active} active states`}
            </p>
          </div>

          {/* Metric selector */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-ifx-gray-700">Map metric:</label>
            <select
              value={metric}
              onChange={(e) => setMetric(e.target.value as MetricOption)}
              className="rounded-md border border-ifx-gray-100 bg-white px-2 py-1.5 text-xs text-ifx-gray-700 focus:outline-none focus:ring-2 focus:ring-ifx-blue"
            >
              <option value="claim_count">Claim Count</option>
              <option value="spend">Spend ($)</option>
            </select>
          </div>
        </div>

        {/* Full-width interactive map */}
        <ErrorBoundary>
          <div className="rounded-lg bg-white ifx-card-shadow p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-ifx-gray-900">US State Heat Map</h3>
              {selectedState && (
                <button type="button" onClick={() => setSelectedState(null)} className="text-xs text-ifx-blue hover:underline">
                  Clear filter: {selectedState}
                </button>
              )}
            </div>
            {isLoading ? <Skeleton className="h-80" /> : data ? (
              <AnalyticsStateChoropleth
                data={data.states}
                metric={metric}
                onStateClick={(abbr) => setSelectedState(abbr === selectedState ? null : abbr)}
              />
            ) : null}
          </div>
        </ErrorBoundary>

        {/* State table */}
        <div className="rounded-lg bg-white ifx-card-shadow p-5">
          <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">
            State Breakdown
            {selectedState && ` — ${selectedState}`}
          </h3>
          {isLoading ? <Skeleton className="h-64" /> : data ? (
            <ConfigurableDataTable
              tableId="analytics-geography-states"
              columns={STATE_COLUMNS}
              data={tableData}
              searchable
              exportable
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
