"use client";

import React, { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Search, Upload } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiPost, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { HCPCSNDCMapping } from "@shared/types/medical-claims";
import { cn } from "@shared/lib/format";

const mappingColumns: ColDef<HCPCSNDCMapping>[] = [
  { accessorKey: "ndc", header: "NDC", cell: (c) => <span className="font-mono text-xs text-teal-400">{c.getValue() as string}</span> },
  { accessorKey: "drug_name", header: "Drug Name", cell: (c) => <span className="font-medium text-white">{c.getValue() as string}</span> },
  { accessorKey: "strength", header: "Strength", cell: (c) => <span className="text-xs text-slate-400">{c.getValue() as string}</span> },
  { accessorKey: "units_per_claim", header: "Units/Claim" },
  {
    accessorKey: "confidence_score",
    header: "Confidence",
    cell: (c) => {
      const score = c.getValue() as number;
      return (
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 rounded-full bg-navy-700 max-w-16">
            <div
              className={cn("h-full rounded-full", score >= 0.9 ? "bg-green-400" : score >= 0.7 ? "bg-yellow-400" : "bg-red-400")}
              style={{ width: `${score * 100}%` }}
            />
          </div>
          <span className="text-xs text-slate-400">{Math.round(score * 100)}%</span>
        </div>
      );
    },
  },
  {
    accessorKey: "mapping_source",
    header: "Source",
    cell: (c) => (
      <span className="text-xs px-2 py-0.5 rounded bg-navy-700 text-slate-300 uppercase">{c.getValue() as string}</span>
    ),
  },
];

export default function CrosswalkPage() {
  const [searchMode, setSearchMode] = useState<"hcpcs_to_ndc" | "ndc_to_hcpcs">("hcpcs_to_ndc");
  const [query, setQuery] = useState("");

  const search = useMutation({
    mutationFn: (q: string) =>
      apiPost<HCPCSNDCMapping[]>(
        buildUrl(`${API_URLS.medicalClaims}/api/v1/crosswalk/search`),
        { mode: searchMode, code: q }
      ),
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">HCPCS→NDC Crosswalk</h1>
          <p className="text-slate-400 text-sm mt-1">Map HCPCS codes to NDC codes and vice versa</p>
        </div>
        <button className="flex items-center gap-2 px-3 py-2 rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 text-sm transition-colors">
          <Upload className="w-4 h-4" />
          Bulk Upload
        </button>
      </div>

      {/* Search mode toggle */}
      <div className="flex gap-2">
        {(["hcpcs_to_ndc", "ndc_to_hcpcs"] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setSearchMode(mode)}
            className={cn(
              "px-4 py-2 rounded-lg border text-sm font-medium transition-colors",
              searchMode === mode
                ? "border-teal-500 bg-teal-900/20 text-teal-300"
                : "border-ifx-border-dark text-slate-400 hover:border-teal-600/40"
            )}
          >
            {mode === "hcpcs_to_ndc" ? "HCPCS → NDC" : "NDC → HCPCS"}
          </button>
        ))}
      </div>

      <div className="flex gap-3 max-w-md">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder={searchMode === "hcpcs_to_ndc" ? "Enter HCPCS code (e.g. J0178)" : "Enter NDC (11 digits)"}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && query && search.mutate(query)}
            className="w-full pl-9 pr-4 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          />
        </div>
        <button
          onClick={() => query && search.mutate(query)}
          disabled={!query || search.isPending}
          className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors disabled:opacity-40"
        >
          {search.isPending ? "Searching..." : "Search"}
        </button>
      </div>

      {search.data && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <p className="text-xs text-slate-400 mb-3">
              {search.data.length} mapping{search.data.length !== 1 ? "s" : ""} found
            </p>
            <DataTable
              columns={mappingColumns}
              data={search.data}
              emptyTitle="No mappings found"
              emptyDescription="No NDC mappings found for this HCPCS code."
            />
          </div>
        </ErrorBoundary>
      )}
    </div>
  );
}
