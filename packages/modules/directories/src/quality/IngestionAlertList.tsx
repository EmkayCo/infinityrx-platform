// src/quality/IngestionAlertList.tsx
// List of actionable ingestion alerts for the quality dashboard (SP-2 Plan D).
// An alert fires when: last_run_status === 'failed' in the last 7 days, OR
// records_errored > 0 in the last run.
"use client";

import React from "react";
import { DismissAlertAction } from "./DismissAlertAction.js";
import type { DatasetQuality } from "../search/schemas.js";

export interface IngestionAlertListProps {
  datasets: DatasetQuality[];
  qualityBaseUrl?: string;
  onAlertDismiss?: (source: string) => void;
}

interface IngestionAlert {
  source: string;
  cluster: DatasetQuality["cluster"];
  alertType: "failed" | "errors";
  records_errored: number;
  last_run_at: string;
  is_dismissed: boolean;
}

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

function buildAlerts(datasets: DatasetQuality[]): IngestionAlert[] {
  const alerts: IngestionAlert[] = [];
  const now = Date.now();

  for (const d of datasets) {
    // Skip sources with no run data.
    if (!d.last_run_at) continue;

    const runAge = now - new Date(d.last_run_at).getTime();
    const withinWindow = runAge <= SEVEN_DAYS_MS;

    if (d.last_run_status === "failed" && withinWindow) {
      alerts.push({
        source: d.source,
        cluster: d.cluster,
        alertType: "failed",
        records_errored: d.records_errored ?? 0,
        last_run_at: d.last_run_at,
        is_dismissed: d.is_dismissed,
      });
    } else if ((d.records_errored ?? 0) > 0 && withinWindow) {
      alerts.push({
        source: d.source,
        cluster: d.cluster,
        alertType: "errors",
        records_errored: d.records_errored ?? 0,
        last_run_at: d.last_run_at,
        is_dismissed: d.is_dismissed,
      });
    }
  }

  return alerts;
}

export function IngestionAlertList({
  datasets,
  qualityBaseUrl = "",
  onAlertDismiss,
}: IngestionAlertListProps) {
  const alerts = buildAlerts(datasets);

  if (alerts.length === 0) {
    return (
      <section
        className="ingestion-alert-list ingestion-alert-list--empty"
        aria-label="Ingestion alerts"
      >
        <p className="ingestion-alert-list__empty-text">
          No data quality issues detected
        </p>
      </section>
    );
  }

  return (
    <section
      className="ingestion-alert-list"
      aria-label="Ingestion alerts"
    >
      <h3 className="ingestion-alert-list__heading">Data Quality Alerts</h3>
      <ul className="ingestion-alert-list__list">
        {alerts.map((alert) => (
          <li
            key={alert.source}
            className={`ingestion-alert-list__item${alert.is_dismissed ? " ingestion-alert-list__item--dismissed" : ""}`}
            data-source={alert.source}
          >
            <div className="ingestion-alert-list__source">
              <span className="ingestion-alert-list__source-name">
                {alert.source}
              </span>
              <span className="ingestion-alert-list__cluster-badge">
                {alert.cluster}
              </span>
            </div>

            {alert.alertType === "failed" ? (
              <span className="ingestion-alert-list__alert-label">
                Run failed
              </span>
            ) : (
              <span className="ingestion-alert-list__alert-label">
                {alert.records_errored} record errors
              </span>
            )}

            <div className="ingestion-alert-list__actions">
              <a
                href={`/directories/ingestion?source=${encodeURIComponent(alert.source)}`}
                className="ingestion-alert-list__action-link"
              >
                View details
              </a>
              <a
                href={`/directories/ingestion?source=${encodeURIComponent(alert.source)}&trigger=1`}
                className="ingestion-alert-list__action-link"
              >
                Re-trigger
              </a>
              {!alert.is_dismissed && (
                <DismissAlertAction
                  source={alert.source}
                  qualityBaseUrl={qualityBaseUrl}
                  onDismissed={() => onAlertDismiss?.(alert.source)}
                />
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
