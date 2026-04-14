"use client";

import React, { use } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowLeft, Star, Play, Clock, FileText, Tag } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { apiGet, apiPost, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { ReportTemplate, ReportFormat, GeneratedReport } from "@shared/types/reporting";
import { cn, formatDate, formatRelative } from "@shared/lib/format";

const CATEGORY_BADGE: Record<string, string> = {
  financial: "bg-green-900/40 text-green-300",
  clinical: "bg-blue-900/40 text-blue-300",
  operational: "bg-purple-900/40 text-purple-300",
  regulatory: "bg-orange-900/40 text-orange-300",
};

const FORMAT_LABELS: Record<ReportFormat, string> = {
  pdf: "PDF",
  excel: "Excel",
  csv: "CSV",
  html: "HTML",
};

const PARAM_TYPE_LABELS: Record<string, string> = {
  date_range: "Date Range",
  date: "Date",
  text: "Text",
  select: "Select",
  multi_select: "Multi-Select",
  boolean: "Boolean (Yes/No)",
  number: "Number",
};

export default function ReportTemplateDetailPage({ params }: { params: Promise<{ templateId: string }> }) {
  const { templateId } = use(params);
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: template, isLoading } = useQuery<ReportTemplate>({
    queryKey: ["report-template", templateId],
    queryFn: () =>
      apiGet<ReportTemplate>(buildUrl(`${API_URLS.reporting}/api/v1/templates/${templateId}`)),
    staleTime: 60_000,
  });

  const { data: recents = [], isLoading: recentsLoading } = useQuery<GeneratedReport[]>({
    queryKey: ["template-recents", templateId],
    queryFn: () =>
      apiGet<GeneratedReport[]>(
        buildUrl(`${API_URLS.reporting}/api/v1/reports`, { template_id: templateId, limit: 5 })
      ),
    staleTime: 30_000,
  });

  const toggleFavorite = useMutation({
    mutationFn: () =>
      apiPost<void>(buildUrl(`${API_URLS.reporting}/api/v1/templates/${templateId}/favorite`), {
        is_favorite: !template?.is_favorite,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["report-template", templateId] });
      void queryClient.invalidateQueries({ queryKey: ["report-templates"] });
    },
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-4 w-96" />
        <div className="grid grid-cols-2 gap-6">
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      </div>
    );
  }

  if (!template) {
    return (
      <div className="p-6 text-center py-16">
        <p className="text-slate-400">Report template not found.</p>
        <button onClick={() => router.back()} className="mt-4 text-teal-400 hover:text-teal-300 text-sm">
          Go back
        </button>
      </div>
    );
  }

  const estimatedMinutes = template.estimated_duration_seconds
    ? Math.ceil(template.estimated_duration_seconds / 60)
    : null;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button onClick={() => router.back()} className="mt-1 text-slate-400 hover:text-slate-200 transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <FileText className="w-5 h-5 text-teal-400" />
            <h1 className="text-2xl font-bold text-white">{template.name}</h1>
            <span className={cn("text-xs px-2 py-0.5 rounded capitalize", CATEGORY_BADGE[template.category] ?? "bg-slate-700 text-slate-400")}>
              {template.category}
            </span>
          </div>
          <p className="text-slate-400 text-sm mt-1">{template.description}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={() => void toggleFavorite.mutate()}
            disabled={toggleFavorite.isPending}
            className={cn(
              "p-2 rounded-lg border transition-colors",
              template.is_favorite
                ? "border-yellow-600/40 bg-yellow-900/20 text-yellow-400"
                : "border-ifx-border-dark bg-ifx-surface-dark text-slate-400 hover:text-yellow-400"
            )}
            aria-label={template.is_favorite ? "Remove from favorites" : "Add to favorites"}
          >
            <Star className={cn("w-4 h-4", template.is_favorite && "fill-current")} />
          </button>
          <button
            onClick={() => router.push(`/reporting/generate?template=${templateId}`)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors"
          >
            <Play className="w-4 h-4" />
            Generate Report
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Template Info */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Template Details</h3>
            <div className="space-y-3">
              {estimatedMinutes !== null && (
                <div className="flex items-center gap-2 text-sm">
                  <Clock className="w-4 h-4 text-slate-500" />
                  <span className="text-slate-400">Estimated generation time:</span>
                  <span className="text-slate-200">~{estimatedMinutes} min</span>
                </div>
              )}

              <div>
                <p className="text-xs text-slate-400 mb-2">Available Formats</p>
                <div className="flex gap-2 flex-wrap">
                  {template.available_formats.map((fmt) => (
                    <span
                      key={fmt}
                      className="text-xs px-2 py-1 rounded bg-navy-700 text-slate-300 font-mono"
                    >
                      {FORMAT_LABELS[fmt]}
                    </span>
                  ))}
                </div>
              </div>

              {template.tags && template.tags.length > 0 && (
                <div>
                  <p className="text-xs text-slate-400 mb-2 flex items-center gap-1">
                    <Tag className="w-3 h-3" />
                    Tags
                  </p>
                  <div className="flex gap-2 flex-wrap">
                    {template.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-xs px-2 py-0.5 rounded border border-ifx-border-dark text-slate-400"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {template.last_generated && (
                <div>
                  <p className="text-xs text-slate-400">Last generated:</p>
                  <p className="text-sm text-slate-300 mt-0.5">
                    {formatRelative(template.last_generated)} ({formatDate(template.last_generated)})
                  </p>
                </div>
              )}
            </div>
          </div>
        </ErrorBoundary>

        {/* Parameters */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">
              Parameters ({template.parameters.length})
            </h3>
            {template.parameters.length === 0 ? (
              <p className="text-sm text-slate-500">This report has no configurable parameters.</p>
            ) : (
              <div className="space-y-2">
                {template.parameters.map((param) => (
                  <div
                    key={param.key}
                    className="flex items-start justify-between p-3 rounded-lg bg-navy-900/40 border border-ifx-border-dark/50"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-slate-200">{param.label}</span>
                        {param.required && (
                          <span className="text-xs text-red-400">*</span>
                        )}
                      </div>
                      <span className="text-xs text-slate-500 font-mono">{param.key}</span>
                    </div>
                    <div className="text-right">
                      <span className="text-xs px-2 py-0.5 rounded bg-navy-700 text-slate-400">
                        {PARAM_TYPE_LABELS[param.type] ?? param.type}
                      </span>
                      {param.default_value !== undefined && (
                        <p className="text-xs text-slate-500 mt-1">
                          Default: {String(param.default_value)}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </ErrorBoundary>
      </div>

      {/* Recent Runs */}
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Recent Runs</h3>
          {recentsLoading ? (
            <Skeleton className="h-32" />
          ) : recents.length === 0 ? (
            <p className="text-sm text-slate-500">No reports generated yet for this template.</p>
          ) : (
            <div className="space-y-2">
              {recents.map((report) => (
                <div
                  key={report.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-navy-900/40 hover:bg-navy-700/20 cursor-pointer transition-colors"
                  onClick={() => router.push(`/reporting/viewer/${report.id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && router.push(`/reporting/viewer/${report.id}`)}
                >
                  <div className="flex items-center gap-3">
                    <span className={cn(
                      "text-xs px-2 py-0.5 rounded",
                      report.status === "ready" ? "bg-green-900/40 text-green-300" :
                      report.status === "failed" ? "bg-red-900/40 text-red-300" :
                      report.status === "generating" ? "bg-blue-900/40 text-blue-300 animate-pulse" :
                      "bg-slate-700 text-slate-400"
                    )}>
                      {report.status}
                    </span>
                    <div>
                      <p className="text-sm text-slate-200">{report.template_name}</p>
                      <p className="text-xs text-slate-500">
                        {report.created_by_name ? `by ${report.created_by_name} · ` : ""}
                        {formatRelative(report.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500 font-mono uppercase">{report.format}</span>
                    {report.status === "ready" && (
                      <span className="text-xs text-teal-400">View →</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </ErrorBoundary>
    </div>
  );
}
