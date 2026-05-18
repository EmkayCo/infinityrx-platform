// src/ingestion/RunProgressBar.tsx
// Live progress bar for an in-flight ingestion run.
// Polls BFF /api/directories/ingest/runs/{runId} every 5 seconds until
// status is no longer 'running'.
"use client";

import React, { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

interface RunDetail {
  id: string;
  source: string;
  status: string;
  records_processed: number;
  records_in_source: number | null;
  error_message: string | null;
}

export interface RunProgressBarProps {
  runId: string;
  source: string;
  onComplete: (result: RunDetail) => void;
  ingestBaseUrl?: string;
  /** Poll interval in ms — defaults to 5000 */
  pollIntervalMs?: number;
}

export function RunProgressBar({
  runId,
  source,
  onComplete,
  ingestBaseUrl = "/api/directories/ingest",
  pollIntervalMs = 5000,
}: RunProgressBarProps) {
  const [processed, setProcessed] = useState(0);
  const [total, setTotal] = useState<number | null>(null);
  const [status, setStatus] = useState<string>("running");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const resp = await fetch(`${ingestBaseUrl}/runs/${runId}`);
        if (!resp.ok) return;
        const data: RunDetail = await resp.json();
        if (cancelled) return;

        setProcessed(data.records_processed ?? 0);
        setTotal(data.records_in_source ?? null);
        setStatus(data.status);

        if (data.status !== "running") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          if (data.status === "failed") {
            toast.error(
              `Ingestion run for ${source} failed: ${data.error_message ?? "unknown error"}`,
            );
          }
          onComplete(data);
        }
      } catch {
        // Network errors: keep polling; don't crash the UI
      }
    }

    poll();
    intervalRef.current = setInterval(poll, pollIntervalMs);

    return () => {
      cancelled = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [runId, source, ingestBaseUrl, pollIntervalMs, onComplete]);

  const pct =
    total && total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : null;

  return (
    <div
      data-testid="run-progress-bar"
      className="flex flex-col gap-1"
      aria-label={`Ingestion progress for ${source}`}
    >
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
        <div
          data-testid="progress-fill"
          className="h-full rounded-full bg-blue-500 transition-all"
          style={{ width: pct !== null ? `${pct}%` : "100%" }}
          aria-valuenow={pct ?? undefined}
          aria-valuemin={0}
          aria-valuemax={100}
          role="progressbar"
        />
      </div>
      <p className="text-xs text-gray-500">
        {status === "running" ? (
          total !== null ? (
            <span data-testid="progress-label">
              {processed.toLocaleString()} / {total.toLocaleString()} records
            </span>
          ) : (
            <span data-testid="progress-label-indeterminate">Processing…</span>
          )
        ) : (
          <span data-testid="progress-complete">{status}</span>
        )}
      </p>
    </div>
  );
}
