"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Activity, CheckCircle, XCircle, Clock, AlertCircle, ChevronDown, ChevronRight } from "lucide-react";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { DetectionRunRead, DetectionRunDetail } from "@/lib/reclaimrx/anomaly-adapter";
import { StatusBadge } from "@/components/ui/status-badge";
import type { StatusVariant } from "@/components/ui/status-badge";

const RUN_STATUS_VARIANT: Record<DetectionRunRead["status"], StatusVariant> = {
  completed: "success",
  in_progress: "warning",
  failed: "error",
  cancelled: "neutral",
};

function RunStatusIcon({ status }: { status: DetectionRunRead["status"] }) {
  if (status === "completed") return <CheckCircle className="w-4 h-4 text-green-500" />;
  if (status === "in_progress") return <Clock className="w-4 h-4 text-amber-500" />;
  if (status === "failed") return <XCircle className="w-4 h-4 text-red-500" />;
  return <AlertCircle className="w-4 h-4 text-gray-400" />;
}

function DataQualityChips({ quality }: { quality: Record<string, unknown> | null }) {
  if (!quality || Object.keys(quality).length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {Object.entries(quality).map(([k, v]) => (
        <span
          key={k}
          className="text-xs px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200"
        >
          {k.replace(/_/g, " ")}: {String(v)}
        </span>
      ))}
    </div>
  );
}

function RunDetail({ runId }: { runId: string }) {
  const { data: detail, isLoading } = useQuery<DetectionRunDetail>({
    queryKey: ["detection-run-detail", runId],
    queryFn: () =>
      apiGet<DetectionRunDetail>(
        buildUrl(`${API_URLS.reclaimrx}/api/v1/reclaimrx/detection-runs/${runId}`)
      ),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="py-3 px-4 text-sm text-ifx-gray-400 animate-pulse">
        Loading breakdown…
      </div>
    );
  }

  if (!detail?.per_rule_breakdown || detail.per_rule_breakdown.length === 0) {
    return (
      <div className="py-3 px-4 text-sm text-ifx-gray-400">
        No per-rule breakdown available.
      </div>
    );
  }

  const severityOrder = ["critical", "high", "medium", "low", "informational"];
  const sorted = [...detail.per_rule_breakdown].sort((a, b) => {
    const ai = severityOrder.indexOf(a.severity);
    const bi = severityOrder.indexOf(b.severity);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  const SEVERITY_COLORS: Record<string, string> = {
    critical: "bg-red-100 text-red-700",
    high: "bg-orange-100 text-orange-700",
    medium: "bg-amber-100 text-amber-700",
    low: "bg-blue-100 text-blue-700",
    informational: "bg-gray-100 text-gray-600",
  };

  return (
    <div className="py-3 px-4">
      <p className="text-xs font-semibold text-ifx-gray-500 uppercase mb-2">Per-Rule Breakdown</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs text-ifx-gray-400 border-b">
            <th className="text-left pb-1 font-medium">Rule</th>
            <th className="text-left pb-1 font-medium">Severity</th>
            <th className="text-right pb-1 font-medium">Count</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.finding_code} className="border-b last:border-0">
              <td className="py-1 font-mono text-xs text-ifx-blue">{row.finding_code}</td>
              <td className="py-1">
                <span
                  className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                    SEVERITY_COLORS[row.severity] ?? "bg-gray-100 text-gray-600"
                  }`}
                >
                  {row.severity}
                </span>
              </td>
              <td className="py-1 text-right font-semibold">{row.count.toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RunRow({ run }: { run: DetectionRunRead }) {
  const router = useRouter();
  const [expanded, setExpanded] = useState(false);

  const completedAt = run.completed_at
    ? new Date(run.completed_at).toLocaleString()
    : null;

  return (
    <>
      <tr
        className="hover:bg-ifx-gray-50 cursor-pointer transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <td className="py-3 px-4">
          <div className="flex items-center gap-1.5">
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-ifx-gray-400" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-ifx-gray-400" />
            )}
            <span className="font-medium text-sm text-ifx-gray-900">
              {run.run_label ?? run.id.slice(0, 8)}
            </span>
          </div>
          {run.source_filename && (
            <div className="text-xs text-ifx-gray-400 ml-5 mt-0.5">{run.source_filename}</div>
          )}
        </td>
        <td className="py-3 px-4">
          <div className="flex items-center gap-1.5">
            <RunStatusIcon status={run.status} />
            <StatusBadge
              status={run.status.replace(/_/g, " ")}
              variant={RUN_STATUS_VARIANT[run.status]}
            />
          </div>
        </td>
        <td className="py-3 px-4 text-right text-sm">
          {run.record_count.toLocaleString()}
        </td>
        <td className="py-3 px-4 text-right">
          <span className="font-semibold text-red-600">
            {run.anomaly_count.toLocaleString()}
          </span>
        </td>
        <td className="py-3 px-4">
          <DataQualityChips quality={run.data_quality} />
        </td>
        <td className="py-3 px-4 text-sm text-ifx-gray-400">
          {completedAt ?? "—"}
        </td>
        <td className="py-3 px-4">
          <button
            className="text-xs text-ifx-blue hover:underline"
            onClick={(e) => {
              e.stopPropagation();
              router.push(`/reclaimrx/leakage?run_id=${run.id}`);
            }}
          >
            View findings
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={7} className="bg-ifx-gray-50 border-b">
            <RunDetail runId={run.id} />
          </td>
        </tr>
      )}
    </>
  );
}

export default function RunsPage() {
  const { data: runs = [], isLoading, isError } = useQuery<DetectionRunRead[]>({
    queryKey: ["detection-runs"],
    queryFn: () =>
      apiGet<DetectionRunRead[]>(
        buildUrl(`${API_URLS.reclaimrx}/api/v1/reclaimrx/detection-runs`)
      ),
    staleTime: 30_000,
  });

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-ifx-blue" />
          <h1 className="text-xl font-bold text-ifx-gray-900">Detection Runs</h1>
        </div>
        <a
          href="/reclaimrx/upload"
          className="text-sm bg-ifx-blue text-white px-3 py-1.5 rounded-lg hover:bg-ifx-blue/90 transition-colors"
        >
          + New Run
        </a>
      </div>

      {isError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 flex items-center gap-2">
          <XCircle className="w-4 h-4 shrink-0" />
          Failed to load detection runs.
        </div>
      )}

      <div className="bg-white rounded-xl ifx-card-shadow overflow-hidden">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-ifx-gray-400 animate-pulse">
            Loading detection runs…
          </div>
        ) : runs.length === 0 ? (
          <div className="p-8 text-center text-sm text-ifx-gray-400">
            No detection runs yet.{" "}
            <a href="/reclaimrx/upload" className="text-ifx-blue hover:underline">
              Upload a CSV
            </a>{" "}
            to start.
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-ifx-gray-50 border-b">
              <tr className="text-xs font-semibold text-ifx-gray-500 uppercase">
                <th className="text-left py-3 px-4">Run</th>
                <th className="text-left py-3 px-4">Status</th>
                <th className="text-right py-3 px-4">Records</th>
                <th className="text-right py-3 px-4">Anomalies</th>
                <th className="text-left py-3 px-4">Data Quality</th>
                <th className="text-left py-3 px-4">Completed</th>
                <th className="py-3 px-4" />
              </tr>
            </thead>
            <tbody className="divide-y divide-ifx-gray-100">
              {runs.map((run) => (
                <RunRow key={run.id} run={run} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
