// src/ingestion/RunHistoryDrawer.tsx
// Slide-in drawer showing run history for a single ingestion source.
// Fetches GET /api/directories/ingest/{source}/history.
"use client";

import React, { useEffect, useState } from "react";

interface RunSummary {
  id: string;
  source: string;
  run_type: string;
  status: string;
  records_inserted: number;
  records_updated: number;
  records_errored: number;
  started_at: string;
  completed_at: string | null;
  duration_seconds: number | null;
  error_message: string | null;
}

export interface RunHistoryDrawerProps {
  source: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ingestBaseUrl?: string;
  /** Optional fetch override — supply to inject auth headers */
  fetchFn?: typeof fetch;
}

export function RunHistoryDrawer({
  source,
  open,
  onOpenChange,
  ingestBaseUrl = "/api/directories/ingest",
  fetchFn = fetch,
}: RunHistoryDrawerProps) {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchFn(`${ingestBaseUrl}/${source}/history?limit=50`)
      .then((r) => r.json())
      .then((data: RunSummary[]) => {
        if (!cancelled) setRuns(data);
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Failed to load history");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, source, ingestBaseUrl, fetchFn]);

  if (!open) return null;

  function formatDuration(seconds: number | null): string {
    if (seconds === null) return "—";
    if (seconds < 60) return `${seconds}s`;
    return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  }

  function formatDate(iso: string | null): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleString();
  }

  return (
    <div
      data-testid="run-history-drawer"
      role="dialog"
      aria-label={`Run history for ${source}`}
      className="fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col bg-white shadow-xl"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <h2 className="text-lg font-semibold">
          Run history — <code className="text-sm">{source}</code>
        </h2>
        <button
          type="button"
          data-testid="drawer-close"
          onClick={() => onOpenChange(false)}
          className="rounded p-1 hover:bg-gray-100"
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-auto px-6 py-4">
        {loading && (
          <p data-testid="drawer-loading" className="text-sm text-gray-500">
            Loading…
          </p>
        )}
        {error && (
          <p data-testid="drawer-error" className="text-sm text-red-600">
            {error}
          </p>
        )}
        {!loading && !error && runs.length === 0 && (
          <p data-testid="drawer-empty" className="text-sm text-gray-500">
            No runs found for this source.
          </p>
        )}
        {!loading && runs.length > 0 && (
          <table className="w-full text-xs" data-testid="drawer-table">
            <thead>
              <tr className="border-b text-left text-gray-500">
                <th className="pb-2 pr-4">Run ID</th>
                <th className="pb-2 pr-4">Status</th>
                <th className="pb-2 pr-4">Started</th>
                <th className="pb-2 pr-4">Duration</th>
                <th className="pb-2 pr-4">Inserted</th>
                <th className="pb-2 pr-4">Updated</th>
                <th className="pb-2 pr-4">Errors</th>
                <th className="pb-2">Trigger</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr
                  key={run.id}
                  data-testid={`drawer-row-${run.id}`}
                  className={
                    run.records_errored > 0 || run.status === "failed"
                      ? "bg-red-50"
                      : ""
                  }
                >
                  <td className="py-1 pr-4 font-mono">
                    {run.id.substring(0, 8)}
                  </td>
                  <td className="py-1 pr-4">
                    <span
                      className={
                        run.status === "failed"
                          ? "text-red-600 font-medium"
                          : run.status === "running"
                            ? "text-blue-600"
                            : "text-green-700"
                      }
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="py-1 pr-4">{formatDate(run.started_at)}</td>
                  <td className="py-1 pr-4">
                    {formatDuration(run.duration_seconds)}
                  </td>
                  <td className="py-1 pr-4">
                    {run.records_inserted.toLocaleString()}
                  </td>
                  <td className="py-1 pr-4">
                    {run.records_updated.toLocaleString()}
                  </td>
                  <td className="py-1 pr-4">
                    {run.records_errored > 0 ? (
                      <span className="font-medium text-orange-600">
                        {run.records_errored.toLocaleString()}
                      </span>
                    ) : (
                      "0"
                    )}
                  </td>
                  <td className="py-1">{run.run_type}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
