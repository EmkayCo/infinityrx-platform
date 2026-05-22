// src/ingestion/TriggerRefreshButton.tsx
// Button to manually trigger an ingestion run for a single source.
// Posts to BFF /api/directories/ingest/{source}/trigger.
// Handles 409 (already running) and error toasts via sonner.
"use client";

import React, { useState } from "react";
import { toast } from "sonner";

export interface TriggerRefreshButtonProps {
  /** Source key — must be in TRIGGERABLE_SOURCES */
  source: string;
  /** Called with the new run_id on successful trigger */
  onRunStarted: (runId: string) => void;
  /** Set true while a run is already in-flight for this source */
  disabled?: boolean;
  ingestBaseUrl?: string;
  /** Optional fetch override — supply to inject auth headers */
  fetchFn?: typeof fetch;
}

export function TriggerRefreshButton({
  source,
  onRunStarted,
  disabled = false,
  ingestBaseUrl = "/api/directories/ingest",
  fetchFn = fetch,
}: TriggerRefreshButtonProps) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    if (disabled || loading) return;
    setLoading(true);
    try {
      const resp = await fetchFn(`${ingestBaseUrl}/${source}/trigger`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ run_type: "manual_trigger" }),
      });

      if (resp.status === 409) {
        toast.warning(
          `A refresh is already running for ${source}. View its progress.`,
        );
        return;
      }

      if (resp.status === 404) {
        const body = await resp.json().catch(() => ({}));
        const cid: string = body?.error?.correlation_id ?? "unknown";
        toast.error(
          `Source not found. Check ingestion console. (correlation_id: ${cid})`,
        );
        return;
      }

      if (!resp.ok) {
        const body = await resp.json().catch(() => ({}));
        const cid: string = body?.error?.correlation_id ?? "unknown";
        toast.error(`Trigger failed. (correlation_id: ${cid})`);
        return;
      }

      const body = await resp.json();
      onRunStarted(String(body.run_id));
    } catch (err) {
      toast.error(
        `Network error triggering ${source}: ${err instanceof Error ? err.message : String(err)}`,
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      type="button"
      data-testid={`trigger-refresh-${source}`}
      onClick={handleClick}
      disabled={disabled || loading}
      aria-label={`Trigger refresh for ${source}`}
      className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium border border-gray-300 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
    >
      {loading ? (
        <span
          data-testid="trigger-spinner"
          className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
          aria-hidden="true"
        />
      ) : null}
      {loading ? "Running…" : "Refresh"}
    </button>
  );
}
