// tests/unit/quality/IngestionAlertList.test.tsx
// IngestionAlertList component tests (SP-2 Plan D Task D-3).
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { IngestionAlertList } from "../../../src/quality/IngestionAlertList.js";
import type { DatasetQuality } from "../../../src/search/schemas.js";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function isoDateDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString();
}

function makeDataset(overrides: Partial<DatasetQuality>): DatasetQuality {
  return {
    source: "nppes",
    cluster: "prescribers",
    last_run_at: isoDateDaysAgo(1),
    last_success_at: isoDateDaysAgo(1),
    last_run_status: "completed",
    records_inserted: 1000,
    records_errored: 0,
    cron_expression: "0 3 1 * *",
    next_run_at: null,
    is_dismissed: false,
    no_loader: false,
    b9_blocked: false,
    ...overrides,
  };
}

describe("IngestionAlertList", () => {
  it("shows empty state message when no alerts", () => {
    const datasets = [makeDataset({ last_run_status: "completed", records_errored: 0 })];
    render(<IngestionAlertList datasets={datasets} />);
    expect(screen.getByText(/no data quality issues detected/i)).toBeTruthy();
  });

  it("shows alert with 'Run failed' label for failed status within 7 days", () => {
    const datasets = [makeDataset({ last_run_status: "failed", last_run_at: isoDateDaysAgo(1) })];
    render(<IngestionAlertList datasets={datasets} />);
    expect(screen.getByText(/run failed/i)).toBeTruthy();
  });

  it("shows 'View details' and 'Re-trigger' links on failed alert", () => {
    const datasets = [makeDataset({ last_run_status: "failed", last_run_at: isoDateDaysAgo(1) })];
    render(<IngestionAlertList datasets={datasets} />);
    expect(screen.getByText(/view details/i)).toBeTruthy();
    expect(screen.getByText(/re-trigger/i)).toBeTruthy();
  });

  it("shows 'Dismiss' button on undismissed alert", () => {
    const datasets = [makeDataset({ last_run_status: "failed", last_run_at: isoDateDaysAgo(1) })];
    render(<IngestionAlertList datasets={datasets} />);
    expect(screen.getByText(/dismiss/i)).toBeTruthy();
  });

  it("shows records_errored count badge for error-type alert", () => {
    const datasets = [makeDataset({ records_errored: 99, last_run_at: isoDateDaysAgo(2) })];
    render(<IngestionAlertList datasets={datasets} />);
    expect(screen.getByText(/99 record errors/i)).toBeTruthy();
  });

  it("does NOT show 'Dismiss' button for already-dismissed alert", () => {
    const datasets = [
      makeDataset({
        last_run_status: "failed",
        last_run_at: isoDateDaysAgo(1),
        is_dismissed: true,
      }),
    ];
    render(<IngestionAlertList datasets={datasets} />);
    // Alert row is rendered but dismiss button is absent.
    const dismissButtons = document.querySelectorAll(".dismiss-alert-action__button");
    expect(dismissButtons.length).toBe(0);
  });

  it("does NOT show alert for failed run older than 7 days", () => {
    const datasets = [makeDataset({ last_run_status: "failed", last_run_at: isoDateDaysAgo(8) })];
    render(<IngestionAlertList datasets={datasets} />);
    expect(screen.getByText(/no data quality issues detected/i)).toBeTruthy();
  });

  it("shows source name and cluster badge on alert row", () => {
    const datasets = [makeDataset({ last_run_status: "failed", last_run_at: isoDateDaysAgo(1) })];
    render(<IngestionAlertList datasets={datasets} />);
    expect(screen.getByText("nppes")).toBeTruthy();
    expect(screen.getByText("prescribers")).toBeTruthy();
  });
});
