"use client";

import React, { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Plus, X, Play, Save } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { apiGet, apiPost, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { ReportFormat } from "@shared/types/reporting";
import { cn } from "@shared/lib/format";

interface MetricOption {
  key: string;
  label: string;
  category: string;
  data_type: "money" | "number" | "percent" | "string" | "date";
}

interface DimensionOption {
  key: string;
  label: string;
  type: "date" | "categorical";
  options?: string[];
}

interface FilterClause {
  dimension: string;
  operator: "equals" | "contains" | "between" | "in";
  value: string;
}

const OUTPUT_FORMATS: ReportFormat[] = ["pdf", "excel", "csv", "html"];

export default function ReportBuilderPage() {
  const router = useRouter();
  const [selectedMetrics, setSelectedMetrics] = useState<string[]>([]);
  const [selectedDimensions, setSelectedDimensions] = useState<string[]>([]);
  const [filters, setFilters] = useState<FilterClause[]>([]);
  const [outputFormat, setOutputFormat] = useState<ReportFormat>("excel");
  const [templateName, setTemplateName] = useState("");
  const [showSaveDialog, setShowSaveDialog] = useState(false);

  const { data: metrics = [], isLoading: metricsLoading } = useQuery<MetricOption[]>({
    queryKey: ["report-metrics"],
    queryFn: () =>
      apiGet<MetricOption[]>(buildUrl(`${API_URLS.reporting}/api/v1/reports/builder/metrics`)),
    staleTime: 300_000,
  });

  const { data: dimensions = [], isLoading: dimensionsLoading } = useQuery<DimensionOption[]>({
    queryKey: ["report-dimensions"],
    queryFn: () =>
      apiGet<DimensionOption[]>(buildUrl(`${API_URLS.reporting}/api/v1/reports/builder/dimensions`)),
    staleTime: 300_000,
  });

  const previewMutation = useMutation({
    mutationFn: () =>
      apiPost<{ report_id: string }>(
        `${API_URLS.reporting}/api/v1/reports/builder/preview`,
        { metrics: selectedMetrics, dimensions: selectedDimensions, filters, format: outputFormat }
      ),
    onSuccess: (res) => {
      router.push(`/reporting/viewer/${res.report_id}`);
    },
  });

  const saveMutation = useMutation({
    mutationFn: () =>
      apiPost(`${API_URLS.reporting}/api/v1/reports/templates`, {
        name: templateName,
        metrics: selectedMetrics,
        dimensions: selectedDimensions,
        filters,
        available_formats: OUTPUT_FORMATS,
        category: "operational",
      }),
    onSuccess: () => {
      setShowSaveDialog(false);
      router.push("/reporting");
    },
  });

  function addFilter() {
    setFilters((prev) => [
      ...prev,
      { dimension: dimensions[0]?.key ?? "", operator: "equals", value: "" },
    ]);
  }

  function removeFilter(index: number) {
    setFilters((prev) => prev.filter((_, i) => i !== index));
  }

  function updateFilter(index: number, partial: Partial<FilterClause>) {
    setFilters((prev) => prev.map((f, i) => (i === index ? { ...f, ...partial } : f)));
  }

  function toggleMetric(key: string) {
    setSelectedMetrics((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  function toggleDimension(key: string) {
    setSelectedDimensions((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  const canPreview = selectedMetrics.length > 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Report Builder</h1>
          <p className="text-slate-400 text-sm mt-1">
            Build custom reports by selecting metrics, dimensions, and filters
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowSaveDialog(true)}
            disabled={!canPreview || !templateName}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 text-sm transition-colors disabled:opacity-40"
          >
            <Save className="w-4 h-4" />
            Save as Template
          </button>
          <button
            onClick={() => previewMutation.mutate()}
            disabled={!canPreview || previewMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors disabled:opacity-40"
          >
            <Play className="w-4 h-4" />
            {previewMutation.isPending ? "Generating..." : "Preview"}
          </button>
        </div>
      </div>

      {showSaveDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="w-full max-w-sm rounded-xl border border-ifx-border-dark bg-navy-900 p-6 shadow-xl">
            <h2 className="text-base font-semibold text-white mb-4">Save as Template</h2>
            <input
              type="text"
              placeholder="Template name"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              className="w-full px-3 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm focus:outline-none focus:ring-2 focus:ring-teal-500/40 mb-4"
            />
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowSaveDialog(false)}
                className="px-4 py-2 text-sm rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => saveMutation.mutate()}
                disabled={!templateName || saveMutation.isPending}
                className="px-4 py-2 text-sm rounded-lg bg-teal-600 hover:bg-teal-500 text-white font-medium transition-colors disabled:opacity-40"
              >
                {saveMutation.isPending ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Metrics */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">
              Metrics ({selectedMetrics.length} selected)
            </h3>
            {metricsLoading ? (
              <Skeleton className="h-40" />
            ) : (
              <div className="space-y-1 max-h-80 overflow-y-auto">
                {metrics.map((m) => (
                  <label
                    key={m.key}
                    className={cn(
                      "flex items-center gap-2.5 px-3 py-2 rounded-lg cursor-pointer transition-colors",
                      selectedMetrics.includes(m.key)
                        ? "bg-teal-900/20 border border-teal-600/30"
                        : "hover:bg-navy-700/30 border border-transparent"
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={selectedMetrics.includes(m.key)}
                      onChange={() => toggleMetric(m.key)}
                      className="accent-teal-500"
                    />
                    <span className="text-sm text-slate-200">{m.label}</span>
                    <span className="ml-auto text-xs text-slate-500 capitalize">{m.data_type}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </ErrorBoundary>

        {/* Dimensions */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">
              Dimensions ({selectedDimensions.length} selected)
            </h3>
            {dimensionsLoading ? (
              <Skeleton className="h-40" />
            ) : (
              <div className="space-y-1 max-h-80 overflow-y-auto">
                {dimensions.map((d) => (
                  <label
                    key={d.key}
                    className={cn(
                      "flex items-center gap-2.5 px-3 py-2 rounded-lg cursor-pointer transition-colors",
                      selectedDimensions.includes(d.key)
                        ? "bg-teal-900/20 border border-teal-600/30"
                        : "hover:bg-navy-700/30 border border-transparent"
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={selectedDimensions.includes(d.key)}
                      onChange={() => toggleDimension(d.key)}
                      className="accent-teal-500"
                    />
                    <span className="text-sm text-slate-200">{d.label}</span>
                    <span className="ml-auto text-xs text-slate-500 capitalize">{d.type}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </ErrorBoundary>

        {/* Filters + Output */}
        <div className="space-y-4">
          <ErrorBoundary>
            <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-slate-200">Filters</h3>
                <button
                  onClick={addFilter}
                  className="flex items-center gap-1 text-xs text-teal-400 hover:text-teal-300 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add
                </button>
              </div>
              <div className="space-y-2">
                {filters.map((f, i) => (
                  <div key={i} className="flex gap-2 items-center">
                    <select
                      value={f.dimension}
                      onChange={(e) => updateFilter(i, { dimension: e.target.value })}
                      className="flex-1 px-2 py-1.5 rounded border border-ifx-border-dark bg-navy-900 text-white text-xs focus:outline-none"
                    >
                      {dimensions.map((d) => (
                        <option key={d.key} value={d.key}>{d.label}</option>
                      ))}
                    </select>
                    <input
                      type="text"
                      value={f.value}
                      onChange={(e) => updateFilter(i, { value: e.target.value })}
                      placeholder="Value"
                      className="w-24 px-2 py-1.5 rounded border border-ifx-border-dark bg-navy-900 text-white text-xs focus:outline-none"
                    />
                    <button
                      onClick={() => removeFilter(i)}
                      className="text-slate-500 hover:text-red-400 transition-colors"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                {filters.length === 0 && (
                  <p className="text-xs text-slate-500 italic">No filters added</p>
                )}
              </div>
            </div>
          </ErrorBoundary>

          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Output Format</h3>
            <div className="flex gap-2">
              {OUTPUT_FORMATS.map((f) => (
                <button
                  key={f}
                  onClick={() => setOutputFormat(f)}
                  className={cn(
                    "flex-1 py-2 rounded-lg border text-xs uppercase font-medium transition-colors",
                    outputFormat === f
                      ? "border-teal-500 bg-teal-900/20 text-teal-300"
                      : "border-ifx-border-dark text-slate-400 hover:border-teal-600/40"
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
