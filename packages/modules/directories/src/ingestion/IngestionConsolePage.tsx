// src/ingestion/IngestionConsolePage.tsx
// Ingestion console — table of all registered reference-data sources with
// status, last run details, schedule, and manual trigger controls.
//
// Data: BFF GET /api/directories/ingest/status → SourceStatus[]
// Rows: 20 triggerable sources + bpg (live API) + fdb (B9-pending) = 22 rows.
// relay-health is NOT shown (not a loader, not in scope per spec §6.4).
"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { TriggerRefreshButton } from "./TriggerRefreshButton.js";
import { RunHistoryDrawer } from "./RunHistoryDrawer.js";
import { RunProgressBar } from "./RunProgressBar.js";
import { formatScheduleLabel, SOURCE_CLUSTER } from "./scheduleLabels.js";

// ---------------------------------------------------------------------------
// All source rows shown in the console table (in display order).
// ---------------------------------------------------------------------------

interface SourceRow {
  source: string;
  /** true = has a loader that can be triggered */
  triggerable: boolean;
  /** shown in Status column when no run data (non-loader sources) */
  staticStatus?: string;
}

const ALL_SOURCE_ROWS: SourceRow[] = [
  // Prescribers cluster
  { source: "nppes", triggerable: true },
  { source: "nppes_monthly", triggerable: true },
  { source: "nppes_deactivation", triggerable: true },
  { source: "dea_registrations", triggerable: true },
  // Pharmacies cluster
  { source: "ncpdp", triggerable: true },
  // Drugs cluster
  { source: "fda_ndc", triggerable: true },
  { source: "fda_orange_book", triggerable: true },
  { source: "fda_purple_book", triggerable: true },
  { source: "fda_drug_shortages", triggerable: true },
  { source: "fda_rems", triggerable: true },
  { source: "rxnorm", triggerable: true },
  { source: "fdb", triggerable: false, staticStatus: "Pending B9" },
  // Codes cluster
  { source: "hcpcs", triggerable: true },
  { source: "icd10_cm", triggerable: true },
  // Pricing cluster
  { source: "cms_asp", triggerable: true },
  { source: "cms_nadac", triggerable: true },
  { source: "state_medicaid_bins", triggerable: true },
  { source: "bpg", triggerable: false, staticStatus: "Live API — no schedule" },
  // Exclusions cluster
  { source: "cms_opt_out", triggerable: true },
  { source: "ofac_sdn", triggerable: true },
  { source: "sam_exclusions", triggerable: true },
  { source: "oig_leie", triggerable: true },
];

// ---------------------------------------------------------------------------
// SourceStatus from backend (mirrors shared/data_ingestion/api/schemas.py)
// ---------------------------------------------------------------------------

interface LastRun {
  id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  records_inserted: number;
  records_updated: number;
  records_errored: number;
  records_in_source: number | null;
  error_message: string | null;
}

interface SourceStatus {
  source: string;
  cron_expression: string | null;
  enabled: boolean;
  last_run: LastRun | null;
  next_run_at: string | null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface IngestionConsolePageProps {
  ingestBaseUrl?: string;
}

export function IngestionConsolePage({
  ingestBaseUrl = "/api/directories/ingest",
}: IngestionConsolePageProps) {
  const [drawerSource, setDrawerSource] = useState<string | null>(null);
  const [inFlightRuns, setInFlightRuns] = useState<Record<string, string>>({}); // source → run_id
  const [completedDeltas, setCompletedDeltas] = useState<Record<string, number>>({}); // source → records_processed

  const { data: statuses = [], isLoading } = useQuery<SourceStatus[]>({
    queryKey: ["ingestion-status"],
    queryFn: async () => {
      const resp = await fetch(`${ingestBaseUrl}/status`);
      if (!resp.ok) return [];
      return resp.json();
    },
    refetchInterval: 30_000,
  });

  const statusBySource = Object.fromEntries(
    statuses.map((s) => [s.source, s]),
  );

  function formatDate(iso: string | null | undefined): string {
    if (!iso) return "—";
    return new Date(iso).toLocaleString();
  }

  function handleRunStarted(source: string, runId: string) {
    setInFlightRuns((prev) => ({ ...prev, [source]: runId }));
  }

  function handleRunComplete(source: string, result?: { records_processed?: number }) {
    setInFlightRuns((prev) => {
      const next = { ...prev };
      delete next[source];
      return next;
    });
    if (result?.records_processed != null) {
      setCompletedDeltas((prev) => ({ ...prev, [source]: result.records_processed! }));
    }
  }

  return (
    <div data-testid="ingestion-console-page" className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold" data-testid="ingestion-console-title">Ingestion Console</h1>
        {isLoading && (
          <span className="text-sm text-gray-500">Loading status…</span>
        )}
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-sm" data-testid="ingestion-console-table">
          <thead className="bg-gray-50 text-xs font-medium uppercase text-gray-500">
            <tr>
              <th className="px-4 py-3 text-left">Source</th>
              <th className="px-4 py-3 text-left">Cluster</th>
              <th className="px-4 py-3 text-left">Last Run</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-right">Records</th>
              <th className="px-4 py-3 text-right">Errors</th>
              <th className="px-4 py-3 text-left">Next Scheduled</th>
              <th className="px-4 py-3 text-left">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {ALL_SOURCE_ROWS.map((row) => {
              const s = statusBySource[row.source];
              const inFlightRunId = inFlightRuns[row.source];
              const isRunning =
                s?.last_run?.status === "running" || Boolean(inFlightRunId);
              const records =
                s?.last_run
                  ? s.last_run.records_inserted + s.last_run.records_updated
                  : null;
              const errored = s?.last_run?.records_errored ?? 0;
              const cronExpr = s?.cron_expression ?? null;

              return (
                <tr
                  key={row.source}
                  data-testid={`ingestion-row-${row.source}`}
                  className="hover:bg-gray-50"
                >
                  {/* Source */}
                  <td className="px-4 py-3">
                    <code className="text-xs">{row.source}</code>
                  </td>

                  {/* Cluster */}
                  <td className="px-4 py-3 text-gray-600">
                    {SOURCE_CLUSTER[row.source] ?? "—"}
                  </td>

                  {/* Last Run */}
                  <td className="px-4 py-3 text-gray-500 text-xs">
                    {s?.last_run ? formatDate(s.last_run.started_at) : "—"}
                  </td>

                  {/* Status */}
                  <td className="px-4 py-3">
                    {!row.triggerable ? (
                      <span
                        data-testid={row.source === "bpg" ? "bpg-live-api-label" : `status-static-${row.source}`}
                        className="text-xs text-gray-500 italic"
                      >
                        {row.staticStatus}
                      </span>
                    ) : inFlightRunId ? (
                      <RunProgressBar
                        runId={inFlightRunId}
                        source={row.source}
                        onComplete={(result) => handleRunComplete(row.source, result)}
                        ingestBaseUrl={ingestBaseUrl}
                      />
                    ) : (
                      <span
                        data-testid={`status-${row.source}`}
                        className={
                          s?.last_run?.status === "failed"
                            ? "text-red-600 font-medium text-xs"
                            : s?.last_run?.status === "running"
                              ? "text-blue-600 text-xs"
                              : "text-green-700 text-xs"
                        }
                      >
                        {s?.last_run?.status ?? "—"}
                      </span>
                    )}
                  </td>

                  {/* Records */}
                  <td className="px-4 py-3 text-right text-xs">
                    {completedDeltas[row.source] != null ? (
                      <span data-testid="run-complete-delta">
                        {completedDeltas[row.source]!.toLocaleString()} records
                      </span>
                    ) : records !== null ? (
                      records.toLocaleString()
                    ) : (
                      "—"
                    )}
                  </td>

                  {/* Errors */}
                  <td className="px-4 py-3 text-right text-xs">
                    {errored > 0 ? (
                      <span
                        data-testid={`errors-badge-${row.source}`}
                        className="inline-block rounded-full bg-orange-100 px-2 py-0.5 text-orange-700 font-medium"
                      >
                        {errored.toLocaleString()}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>

                  {/* Next Scheduled */}
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {row.triggerable
                      ? formatScheduleLabel(cronExpr)
                      : "—"}
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {row.triggerable && (
                        <>
                          <TriggerRefreshButton
                            source={row.source}
                            onRunStarted={(runId) =>
                              handleRunStarted(row.source, runId)
                            }
                            disabled={isRunning}
                            ingestBaseUrl={ingestBaseUrl}
                          />
                          <button
                            type="button"
                            data-testid={`view-history-${row.source}`}
                            onClick={() => setDrawerSource(row.source)}
                            className="text-xs text-blue-600 hover:underline"
                          >
                            History
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Run history drawer */}
      {drawerSource && (
        <RunHistoryDrawer
          source={drawerSource}
          open={Boolean(drawerSource)}
          onOpenChange={(open) => {
            if (!open) setDrawerSource(null);
          }}
          ingestBaseUrl={ingestBaseUrl}
        />
      )}
    </div>
  );
}
