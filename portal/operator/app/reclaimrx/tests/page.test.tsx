// portal/operator/app/reclaimrx/tests/page.test.tsx
// SP-3 Plan A5 — smoke tests for 6 new empty-state reclaimrx pages.
// Each page renders ComingSoonPage with the correct title/phase.
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ReclaimRxDashboardPage from "../dashboard/page";
import ReclaimRxHoldsPage from "../holds/page";
import ReclaimRxFraudRingsPage from "../fraud-rings/page";
import ReclaimRxGraphRunsPage from "../graph-runs/page";
import ReclaimRxThresholdsPage from "../thresholds/page";
import ReclaimRxAccumulatorAnomaliesPage from "../accumulator-anomalies/page";

describe("ReclaimRx empty-state pages", () => {
  it("dashboard page renders with correct title", () => {
    render(<ReclaimRxDashboardPage />);
    expect(screen.getByText("FWA Detection Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Coming in Plan D")).toBeInTheDocument();
  });

  it("holds page renders with correct title", () => {
    render(<ReclaimRxHoldsPage />);
    expect(screen.getByText("Payment Holds")).toBeInTheDocument();
    expect(screen.getByText("Coming in Plan D")).toBeInTheDocument();
  });

  it("fraud-rings page renders with correct title", () => {
    render(<ReclaimRxFraudRingsPage />);
    expect(screen.getByText("Fraud Ring Visualization")).toBeInTheDocument();
    expect(screen.getByText("Coming in Plan E")).toBeInTheDocument();
  });

  it("graph-runs page renders with correct title", () => {
    render(<ReclaimRxGraphRunsPage />);
    expect(screen.getByText("Graph Analysis Runs")).toBeInTheDocument();
    expect(screen.getByText("Coming in Plan E")).toBeInTheDocument();
  });

  it("thresholds page renders with correct title", () => {
    render(<ReclaimRxThresholdsPage />);
    expect(screen.getByText("Threshold Configuration")).toBeInTheDocument();
    expect(screen.getByText("Coming in Plan C")).toBeInTheDocument();
  });

  it("accumulator-anomalies page renders with correct title", () => {
    render(<ReclaimRxAccumulatorAnomaliesPage />);
    expect(screen.getByText("Accumulator Anomaly Detection")).toBeInTheDocument();
    expect(screen.getByText("Coming in Plan E")).toBeInTheDocument();
  });
});
