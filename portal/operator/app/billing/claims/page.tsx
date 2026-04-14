// Claims Review page — real InfinityRx data via /api/claims pagination + virtual scroll.
"use client";

import React, { useState, useRef, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { toast } from "sonner";
import { DollarDisplay } from "@shared/components/dollar-display";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { SkeletonTable } from "@shared/components/skeleton";
import { ExportMenu } from "@shared/components/export-menu";
import { formatDate } from "@shared/lib/format";

interface RealClaim {
  claim_id: string;
  status: "P" | "R";
  client_name: string;
  group_number: string;
  ndc: string;
  service_provider_id: string;
  date_of_service: string;
  quantity: number;
  days_supply: number;
  total_client_billed: string;
  pharmacy_ingredient_cost_paid: string;
  copay: string;
  claim_processing_fee: string;
  transaction_fees: string;
  network_reimbursement_id: string;
  primary_chain_code: string;
  prescriber_npi: string;
  cycle_id: string;
}

interface ClaimsResponse {
  rows: RealClaim[];
  total: number;
  page: number;
  size: number;
}

interface Filters {
  status: string;
  client: string;
  nrid: string;
  dos_from: string;
  dos_to: string;
  q: string;
  page: number;
}

const NRID_OPTIONS = [
  { value: "", label: "All NRIDs" },
  { value: "INFINITY", label: "INFINITY (Echo Health)" },
  { value: "IFXMANUAL", label: "IFXMANUAL (CheckIssuing)" },
  { value: "PHXCOM30", label: "PHXCOM30 (Phoenix)" },
  { value: "PHXCOM90", label: "PHXCOM90 (Phoenix)" },
  { value: "COMM30", label: "COMM30 (Phoenix)" },
  { value: "COMM90", label: "COMM90 (Phoenix)" },
];

const STATUS_BADGE: Record<string, string> = {
  P: "bg-teal-500/20 text-teal-300",
  R: "bg-red-500/20 text-red-400",
};

function buildQueryUrl(filters: Filters): string {
  const params = new URLSearchParams();
  params.set("page", String(filters.page));
  params.set("size", "200");
  if (filters.status) params.set("status", filters.status);
  if (filters.client) params.set("client", filters.client);
  if (filters.nrid) params.set("nrid", filters.nrid);
  if (filters.dos_from) params.set("dos_from", filters.dos_from);
  if (filters.dos_to) params.set("dos_to", filters.dos_to);
  if (filters.q) params.set("q", filters.q);
  return `/api/claims?${params.toString()}`;
}

const COL_WIDTHS = [140, 60, 130, 80, 110, 100, 90, 50, 50, 80, 95, 70, 60, 70, 80, 80];
const COL_HEADERS = [
  "Claim ID", "Status", "Client", "Group", "NDC", "Pharmacy NPI",
  "DOS", "Qty", "Days", "Billed", "Pharmacy Paid", "Copay", "CPFee", "TxFee", "NRID", "Chain",
];

export default function ClaimsPage() {
  const [filters, setFilters] = useState<Filters>({
    status: "",
    client: "",
    nrid: "",
    dos_from: "",
    dos_to: "",
    q: "",
    page: 1,
  });
  const [qInput, setQInput] = useState("");
  const queryClient = useQueryClient();
  const parentRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, isFetching } = useQuery<ClaimsResponse>({
    queryKey: ["real-claims", filters],
    queryFn: async () => {
      const res = await fetch(buildQueryUrl(filters));
      if (!res.ok) throw new Error(`API error ${res.status}`);
      return res.json() as Promise<ClaimsResponse>;
    },
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });

  const rows = data?.rows ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.ceil(total / 200);

  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 36,
    overscan: 20,
  });

  const handleFilterChange = useCallback(
    (key: keyof Filters, value: string | number) => {
      setFilters((prev) => ({ ...prev, [key]: value, page: 1 }));
    },
    []
  );

  const handleSearch = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      setFilters((prev) => ({ ...prev, q: qInput, page: 1 }));
    },
    [qInput]
  );

  const handleExportCsv = () => {
    const csvRows = rows.map((c) => [
      c.claim_id,
      c.status,
      c.client_name,
      c.group_number,
      c.ndc,
      c.service_provider_id,
      c.date_of_service,
      c.quantity,
      c.days_supply,
      c.total_client_billed,
      c.pharmacy_ingredient_cost_paid,
      c.copay,
      c.claim_processing_fee,
      c.transaction_fees,
      c.network_reimbursement_id,
      c.primary_chain_code,
    ]);
    const header = COL_HEADERS.join(",");
    const csv = [header, ...csvRows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "claims.csv";
    a.click();
    toast.success("CSV export started");
  };

  return (
    <div className="p-6 space-y-4 h-full flex flex-col">
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Claims Review</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            {total > 0
              ? `${total.toLocaleString()} claims${isFetching ? " (refreshing…)" : ""}`
              : isLoading
              ? "Loading…"
              : "No claims match filters"}
          </p>
        </div>
        <ExportMenu onExportCsv={handleExportCsv} />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 shrink-0">
        {/* Status */}
        <select
          value={filters.status}
          onChange={(e) => handleFilterChange("status", e.target.value)}
          className="px-3 py-1.5 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          <option value="P">Paid (P)</option>
          <option value="R">Reversal (R)</option>
        </select>

        {/* NRID */}
        <select
          value={filters.nrid}
          onChange={(e) => handleFilterChange("nrid", e.target.value)}
          className="px-3 py-1.5 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          aria-label="Filter by NRID"
        >
          {NRID_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        {/* DOS from */}
        <input
          type="date"
          value={filters.dos_from}
          onChange={(e) => handleFilterChange("dos_from", e.target.value)}
          className="px-3 py-1.5 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          aria-label="Date of service from"
        />
        <span className="text-slate-500 text-sm">to</span>
        <input
          type="date"
          value={filters.dos_to}
          onChange={(e) => handleFilterChange("dos_to", e.target.value)}
          className="px-3 py-1.5 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          aria-label="Date of service to"
        />

        {/* Free-text search */}
        <form onSubmit={handleSearch} className="flex items-center gap-2">
          <input
            type="text"
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder="Search claim ID, NDC, pharmacy…"
            className="px-3 py-1.5 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-teal-500/40 w-56"
            aria-label="Search claims"
          />
          <button
            type="submit"
            className="px-3 py-1.5 text-sm rounded-md bg-teal-600 hover:bg-teal-500 text-white transition-colors"
          >
            Search
          </button>
          {filters.q && (
            <button
              type="button"
              onClick={() => {
                setQInput("");
                setFilters((prev) => ({ ...prev, q: "", page: 1 }));
              }}
              className="text-xs text-slate-400 hover:text-slate-200"
            >
              Clear
            </button>
          )}
        </form>
      </div>

      {/* Table */}
      <ErrorBoundary>
        {isLoading ? (
          <SkeletonTable rows={12} cols={COL_HEADERS.length} />
        ) : (
          <div className="flex-1 min-h-0 rounded-lg border border-ifx-border-dark overflow-hidden">
            {/* Header */}
            <div className="flex border-b border-ifx-border-dark bg-navy-900/80 sticky top-0 z-10">
              {COL_HEADERS.map((h, i) => (
                <div
                  key={h}
                  className="px-3 py-2 text-xs font-medium text-slate-400 uppercase tracking-wide shrink-0"
                  style={{ width: COL_WIDTHS[i] }}
                >
                  {h}
                </div>
              ))}
            </div>

            {/* Virtual scroll body */}
            <div
              ref={parentRef}
              className="overflow-auto bg-navy-900"
              style={{ height: "calc(100vh - 360px)" }}
            >
              <div
                style={{
                  height: rowVirtualizer.getTotalSize(),
                  position: "relative",
                }}
              >
                {rowVirtualizer.getVirtualItems().map((virtualRow) => {
                  const claim = rows[virtualRow.index];
                  if (!claim) return null;
                  return (
                    <div
                      key={claim.claim_id + virtualRow.index}
                      className="flex items-center border-b border-ifx-border-dark/50 hover:bg-navy-700/30 transition-colors"
                      style={{
                        position: "absolute",
                        top: virtualRow.start,
                        height: virtualRow.size,
                        width: "100%",
                      }}
                    >
                      {/* Claim ID */}
                      <div
                        className="px-3 py-1 text-xs font-mono text-slate-300 truncate shrink-0"
                        style={{ width: COL_WIDTHS[0] }}
                        title={claim.claim_id}
                      >
                        {claim.claim_id}
                      </div>
                      {/* Status */}
                      <div className="px-3 py-1 shrink-0" style={{ width: COL_WIDTHS[1] }}>
                        <span
                          className={`px-1.5 py-0.5 rounded text-xs font-bold ${
                            STATUS_BADGE[claim.status] ?? "bg-slate-700 text-slate-300"
                          }`}
                        >
                          {claim.status}
                        </span>
                      </div>
                      {/* Client */}
                      <div
                        className="px-3 py-1 text-xs text-slate-200 truncate shrink-0"
                        style={{ width: COL_WIDTHS[2] }}
                        title={claim.client_name}
                      >
                        {claim.client_name}
                      </div>
                      {/* Group */}
                      <div
                        className="px-3 py-1 text-xs font-mono text-slate-400 truncate shrink-0"
                        style={{ width: COL_WIDTHS[3] }}
                      >
                        {claim.group_number}
                      </div>
                      {/* NDC */}
                      <div
                        className="px-3 py-1 text-xs font-mono text-slate-300 truncate shrink-0"
                        style={{ width: COL_WIDTHS[4] }}
                      >
                        {claim.ndc}
                      </div>
                      {/* Pharmacy NPI */}
                      <div
                        className="px-3 py-1 text-xs font-mono text-slate-400 truncate shrink-0"
                        style={{ width: COL_WIDTHS[5] }}
                      >
                        {claim.service_provider_id}
                      </div>
                      {/* DOS */}
                      <div
                        className="px-3 py-1 text-xs text-slate-400 shrink-0"
                        style={{ width: COL_WIDTHS[6] }}
                      >
                        {formatDate(claim.date_of_service) || claim.date_of_service}
                      </div>
                      {/* Qty */}
                      <div
                        className="px-3 py-1 text-xs text-slate-400 text-right tabular-nums shrink-0"
                        style={{ width: COL_WIDTHS[7] }}
                      >
                        {claim.quantity}
                      </div>
                      {/* Days */}
                      <div
                        className="px-3 py-1 text-xs text-slate-400 text-right tabular-nums shrink-0"
                        style={{ width: COL_WIDTHS[8] }}
                      >
                        {claim.days_supply}
                      </div>
                      {/* Billed */}
                      <div className="px-3 py-1 shrink-0" style={{ width: COL_WIDTHS[9] }}>
                        <DollarDisplay amount={claim.total_client_billed} size="sm" showScale={false} />
                      </div>
                      {/* Pharmacy Paid */}
                      <div className="px-3 py-1 shrink-0" style={{ width: COL_WIDTHS[10] }}>
                        <DollarDisplay amount={claim.pharmacy_ingredient_cost_paid} size="sm" showScale={false} />
                      </div>
                      {/* Copay */}
                      <div className="px-3 py-1 shrink-0" style={{ width: COL_WIDTHS[11] }}>
                        <DollarDisplay amount={claim.copay} size="sm" showScale={false} />
                      </div>
                      {/* CPFee */}
                      <div className="px-3 py-1 shrink-0" style={{ width: COL_WIDTHS[12] }}>
                        <DollarDisplay amount={claim.claim_processing_fee} size="sm" showScale={false} />
                      </div>
                      {/* TxFee */}
                      <div className="px-3 py-1 shrink-0" style={{ width: COL_WIDTHS[13] }}>
                        <DollarDisplay amount={claim.transaction_fees} size="sm" showScale={false} />
                      </div>
                      {/* NRID */}
                      <div
                        className="px-3 py-1 text-xs font-mono text-slate-400 truncate shrink-0"
                        style={{ width: COL_WIDTHS[14] }}
                      >
                        {claim.network_reimbursement_id}
                      </div>
                      {/* Chain */}
                      <div
                        className="px-3 py-1 text-xs font-mono text-slate-500 truncate shrink-0"
                        style={{ width: COL_WIDTHS[15] }}
                      >
                        {claim.primary_chain_code}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </ErrorBoundary>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center gap-4 shrink-0 pt-1">
          <button
            onClick={() => handleFilterChange("page", Math.max(1, filters.page - 1))}
            disabled={filters.page <= 1}
            className="px-3 py-1.5 text-sm rounded border border-ifx-border-dark text-slate-300 hover:bg-navy-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Previous
          </button>
          <span className="text-sm text-slate-400">
            Page {filters.page} of {totalPages} ({total.toLocaleString()} total claims)
          </span>
          <button
            onClick={() => handleFilterChange("page", Math.min(totalPages, filters.page + 1))}
            disabled={filters.page >= totalPages}
            className="px-3 py-1.5 text-sm rounded border border-ifx-border-dark text-slate-300 hover:bg-navy-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
