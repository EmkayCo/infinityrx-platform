"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ChevronLeft, Download, Share2, FileText } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { apiGet } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { GeneratedReport } from "@shared/types/reporting";
import { formatDateTime } from "@shared/lib/format";

export const dynamic = "force-dynamic";
// PHI compliance: Cache-Control: no-store set via headers config in next.config.ts

export default function ReportViewerPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const router = useRouter();

  const { data: report, isLoading } = useQuery<GeneratedReport>({
    queryKey: ["report", reportId],
    queryFn: () =>
      apiGet<GeneratedReport>(`${API_URLS.reporting}/api/v1/reports/${reportId}`),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-[70vh] rounded-lg" />
      </div>
    );
  }

  if (!report) {
    return (
      <div className="p-6">
        <p className="text-slate-400">Report not found or has expired.</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4 flex flex-col h-full">
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
          Back
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-white">{report.template_name}</h1>
          <p className="text-slate-400 text-sm">
            Generated {report.generated_at ? formatDateTime(report.generated_at) : "—"}
            {report.created_by_name && ` by ${report.created_by_name}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {report.download_url && (
            <>
              <a
                href={report.download_url}
                download
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 text-sm transition-colors"
              >
                <Download className="w-4 h-4" />
                PDF
              </a>
              <a
                href={`${report.download_url}?format=excel`}
                download
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 text-sm transition-colors"
              >
                <Download className="w-4 h-4" />
                Excel
              </a>
            </>
          )}
          {report.share_url && (
            <button
              onClick={() => {
                void navigator.clipboard.writeText(report.share_url!);
              }}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 text-sm transition-colors"
              title="Copy share link (expires 24h)"
            >
              <Share2 className="w-4 h-4" />
              Share
            </button>
          )}
        </div>
      </div>

      <ErrorBoundary>
        <div className="flex-1 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark overflow-hidden min-h-[500px]">
          {report.status === "generating" || report.status === "pending" ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 py-20">
              <div className="w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-slate-400 text-sm">Generating report...</p>
            </div>
          ) : report.status === "failed" ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 py-20">
              <FileText className="w-10 h-10 text-red-400" />
              <p className="text-red-400 text-sm font-medium">Report generation failed</p>
            </div>
          ) : report.download_url && report.format === "pdf" ? (
            <iframe
              src={`${report.download_url}#toolbar=0`}
              className="w-full h-full min-h-[600px]"
              title={report.template_name}
              sandbox="allow-same-origin allow-scripts"
            />
          ) : report.download_url ? (
            <div className="flex flex-col items-center justify-center h-full gap-4 py-20">
              <FileText className="w-12 h-12 text-teal-400" />
              <p className="text-slate-300 text-sm">
                {report.format?.toUpperCase()} report ready
                {report.file_size_bytes && ` (${Math.round(report.file_size_bytes / 1024)}KB)`}
              </p>
              <a
                href={report.download_url}
                download
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors"
              >
                <Download className="w-4 h-4" />
                Download Report
              </a>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full py-20">
              <p className="text-slate-500 text-sm">No preview available</p>
            </div>
          )}
        </div>
      </ErrorBoundary>
    </div>
  );
}
