// src/quality/QualityDashboardPanel.tsx
// Data-quality dashboard sidebar panel (SP-2 Plan D).
// Fetches GET /api/directories/quality, renders one FreshnessChip row per source
// (sorted by staleness, oldest first), and surfaces IngestionAlertList.
"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { FreshnessChip } from "../components/FreshnessChip.js";
import { IngestionAlertList } from "./IngestionAlertList.js";
import type { DatasetQuality, QualityResponse } from "../search/schemas.js";

export interface QualityDashboardPanelProps {
  /** Base URL for the quality BFF endpoint (defaults to relative path) */
  qualityBaseUrl?: string;
  onAlertDismiss?: (source: string) => void;
}

async function fetchQuality(qualityBaseUrl: string): Promise<QualityResponse> {
  const res = await fetch(`${qualityBaseUrl}/api/directories/quality`);
  if (!res.ok) {
    throw new Error(`Quality fetch failed: ${res.status}`);
  }
  return res.json();
}

/** Sort order: null last_run_at first (never loaded), then oldest. */
function sortByStaleness(datasets: DatasetQuality[]): DatasetQuality[] {
  return [...datasets].sort((a, b) => {
    if (!a.last_run_at && !b.last_run_at) return 0;
    if (!a.last_run_at) return -1;
    if (!b.last_run_at) return 1;
    return new Date(a.last_run_at).getTime() - new Date(b.last_run_at).getTime();
  });
}

export function QualityDashboardPanel({
  qualityBaseUrl = "",
  onAlertDismiss,
}: QualityDashboardPanelProps) {
  const { data, isLoading, isError } = useQuery<QualityResponse>({
    queryKey: ["dir:quality"],
    queryFn: () => fetchQuality(qualityBaseUrl),
    // Matches BFF s-maxage=60 — don't refetch more often than the cache TTL.
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="quality-dashboard-panel quality-dashboard-panel--loading">
        <p className="quality-dashboard-panel__loading-text">
          Loading data quality…
        </p>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="quality-dashboard-panel quality-dashboard-panel--error">
        <p className="quality-dashboard-panel__error-text">
          Unable to load quality data. Try refreshing.
        </p>
      </div>
    );
  }

  const sorted = sortByStaleness(data.datasets);

  return (
    <div className="quality-dashboard-panel">
      {data.is_partial && (
        <p className="quality-dashboard-panel__partial-banner">
          Some backend services were unreachable — data may be incomplete.
        </p>
      )}

      <section className="quality-dashboard-panel__freshness-list" aria-label="Source freshness">
        {sorted.map((dataset) => (
          <div
            key={dataset.source}
            className="quality-dashboard-panel__row"
            data-source={dataset.source}
          >
            <FreshnessChip
              sourceKey={dataset.source}
              lastRunAt={dataset.last_run_at}
            />
            {dataset.records_errored != null && dataset.records_errored > 0 && (
              <span
                className="quality-dashboard-panel__error-badge"
                aria-label={`${dataset.records_errored} records errored`}
              >
                {dataset.records_errored} errors
              </span>
            )}
            {dataset.b9_blocked && (
              <span className="quality-dashboard-panel__b9-badge">
                Pending B9
              </span>
            )}
          </div>
        ))}
      </section>

      <IngestionAlertList
        datasets={data.datasets}
        qualityBaseUrl={qualityBaseUrl}
        onAlertDismiss={onAlertDismiss}
      />
    </div>
  );
}
