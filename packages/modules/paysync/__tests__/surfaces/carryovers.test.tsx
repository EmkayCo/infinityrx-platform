// packages/modules/paysync/__tests__/surfaces/carryovers.test.tsx
// RTL tests for the carryovers surface components.
// Uses happy-dom. Follows the batches/payment-runs test pattern.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import type { Carryover } from "@infinityrx/contract";

afterEach(() => cleanup());

// ── Shared fixtures ──────────────────────────────────────────────────────

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000+00:00";

function makeCarryover(overrides: Partial<Carryover> = {}): Carryover {
  // C4: contract now models AP carryforward (ap_record_id + amount + resolved),
  // not member accumulator carryover. See packages/contract/src/impls/paysync/types.ts.
  return {
    id: "d0000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    upload_id: null,
    ap_record_id: "e0000000-0000-0000-0000-000000000001",
    amount: "250.00",
    reason: "deductible_carryover",
    resolved: false,
    resolved_at: null,
    resolved_by: null,
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  };
}

// ── CarryoversListPage ────────────────────────────────────────────────────

describe("CarryoversListPage", () => {
  let CarryoversListPage: typeof import("../../src/surfaces/carryovers/CarryoversListPage.js").CarryoversListPage;

  beforeEach(async () => {
    ({ CarryoversListPage } = await import("../../src/surfaces/carryovers/CarryoversListPage.js"));
  });

  it("renders the carryovers list page container", () => {
    render(<CarryoversListPage carryovers={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("carryovers-list-page")).toBeTruthy();
  });

  it("renders a row for each carryover", () => {
    const carryovers = [
      makeCarryover({ id: "d1" }),
      makeCarryover({ id: "d2", reason: "oop_carryover" }),
    ];
    render(<CarryoversListPage carryovers={carryovers} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("carryover-row")).toHaveLength(2);
  });

  it("renders reason for each carryover", () => {
    render(<CarryoversListPage carryovers={[makeCarryover()]} isLoading={false} error={null} />);
    expect(screen.getByTestId("carryover-reason")).toBeTruthy();
    expect(screen.getByText("deductible_carryover")).toBeTruthy();
  });

  it("renders MoneyDisplay for amount", () => {
    render(<CarryoversListPage carryovers={[makeCarryover()]} isLoading={false} error={null} />);
    const displays = screen.getAllByTestId("money-display");
    expect(displays.length).toBeGreaterThanOrEqual(1);
  });

  it("renders resolved status indicator", () => {
    render(
      <CarryoversListPage
        carryovers={[makeCarryover({ resolved: false }), makeCarryover({ id: "d2", resolved: true })]}
        isLoading={false}
        error={null}
      />,
    );
    const statuses = screen.getAllByTestId("carryover-status");
    expect(statuses.map((s) => s.textContent)).toContain("open");
    expect(statuses.map((s) => s.textContent)).toContain("resolved");
  });

  it("renders loading state when isLoading=true", () => {
    render(<CarryoversListPage carryovers={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("carryovers-list-loading")).toBeTruthy();
  });

  it("renders error message when error is set", () => {
    render(<CarryoversListPage carryovers={[]} isLoading={false} error="Network failure" />);
    expect(screen.getByTestId("carryovers-list-error")).toBeTruthy();
  });

  it("renders empty state when no carryovers", () => {
    render(<CarryoversListPage carryovers={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("carryovers-list-empty")).toBeTruthy();
  });
});

// ── CarryoverDetailPage ───────────────────────────────────────────────────

describe("CarryoverDetailPage", () => {
  let CarryoverDetailPage: typeof import("../../src/surfaces/carryovers/CarryoverDetailPage.js").CarryoverDetailPage;

  beforeEach(async () => {
    ({ CarryoverDetailPage } = await import("../../src/surfaces/carryovers/CarryoverDetailPage.js"));
  });

  it("renders the carryover detail page container", () => {
    render(
      <CarryoverDetailPage
        carryover={makeCarryover()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onResolve={vi.fn()}
      />,
    );
    expect(screen.getByTestId("carryover-detail-page")).toBeTruthy();
  });

  it("renders amount via MoneyDisplay", () => {
    render(
      <CarryoverDetailPage
        carryover={makeCarryover()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onResolve={vi.fn()}
      />,
    );
    const displays = screen.getAllByTestId("money-display");
    expect(displays.length).toBeGreaterThanOrEqual(1);
  });

  it("renders ProvenanceBreadcrumb when originUploadId is set", () => {
    render(
      <CarryoverDetailPage
        carryover={makeCarryover()}
        isLoading={false}
        error={null}
        currentRole="operator"
        originUploadId="u-origin-001"
        onResolve={vi.fn()}
      />,
    );
    expect(screen.getByTestId("provenance-breadcrumb")).toBeTruthy();
  });

  it("renders resolve button disabled (RbacGate denied) for Operator role", () => {
    render(
      <CarryoverDetailPage
        carryover={makeCarryover()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onResolve={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders resolve button enabled (RbacGate allowed) for Approver role", () => {
    render(
      <CarryoverDetailPage
        carryover={makeCarryover()}
        isLoading={false}
        error={null}
        currentRole="approver"
        onResolve={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("calls onResolve with carryover id when Approver clicks resolve", () => {
    const onResolve = vi.fn();
    render(
      <CarryoverDetailPage
        carryover={makeCarryover()}
        isLoading={false}
        error={null}
        currentRole="approver"
        onResolve={onResolve}
      />,
    );
    fireEvent.click(screen.getByTestId("carryover-resolve-button"));
    expect(onResolve).toHaveBeenCalledWith("d0000000-0000-0000-0000-000000000001");
  });

  it("renders loading state", () => {
    render(
      <CarryoverDetailPage
        carryover={null}
        isLoading={true}
        error={null}
        currentRole="operator"
        onResolve={vi.fn()}
      />,
    );
    expect(screen.getByTestId("carryover-detail-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(
      <CarryoverDetailPage
        carryover={null}
        isLoading={false}
        error="Not found"
        currentRole="operator"
        onResolve={vi.fn()}
      />,
    );
    expect(screen.getByTestId("carryover-detail-error")).toBeTruthy();
  });
});
