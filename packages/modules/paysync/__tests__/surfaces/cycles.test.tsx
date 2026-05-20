// packages/modules/paysync/__tests__/surfaces/cycles.test.tsx
// RTL tests for the cycles surface components.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { Cycle } from "@infinityrx/contract";

afterEach(() => cleanup());

// ── Shared fixtures ──────────────────────────────────────────────────────

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000+00:00";

function makeCycle(overrides: Partial<Cycle> = {}): Cycle {
  return {
    id: "c1000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    period_label: "2026-05",
    status: "open",
    window_closed_at: null,
    origin_upload_id: "u0000000-0000-0000-0000-000000000001",
    total_billed_amount: null,
    claim_count: 20,
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  };
}

// ── CyclesListPage ────────────────────────────────────────────────────────

describe("CyclesListPage", () => {
  let CyclesListPage: typeof import("../../src/surfaces/cycles/CyclesListPage.js").CyclesListPage;

  beforeEach(async () => {
    ({ CyclesListPage } = await import("../../src/surfaces/cycles/CyclesListPage.js"));
  });

  it("renders the cycles list page container", () => {
    render(<CyclesListPage cycles={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("cycles-list-page")).toBeTruthy();
  });

  it("renders a row for each cycle", () => {
    const cycles = [
      makeCycle({ id: "c1", period_label: "2026-05" }),
      makeCycle({ id: "c2", period_label: "2026-04" }),
    ];
    render(<CyclesListPage cycles={cycles} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("cycle-row")).toHaveLength(2);
  });

  it("renders period_label for each cycle", () => {
    render(<CyclesListPage cycles={[makeCycle()]} isLoading={false} error={null} />);
    expect(screen.getByText("2026-05")).toBeTruthy();
  });

  it("renders status badge for each cycle", () => {
    render(<CyclesListPage cycles={[makeCycle({ status: "closing" })]} isLoading={false} error={null} />);
    expect(screen.getByTestId("cycle-status-badge")).toBeTruthy();
  });

  it("renders MoneyDisplay for total_billed_amount when set", () => {
    render(<CyclesListPage cycles={[makeCycle({ total_billed_amount: "45678.9000", status: "closed" })]} isLoading={false} error={null} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders loading state", () => {
    render(<CyclesListPage cycles={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("cycles-list-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(<CyclesListPage cycles={[]} isLoading={false} error="Network error" />);
    expect(screen.getByTestId("cycles-list-error")).toBeTruthy();
  });

  it("renders empty state when no cycles", () => {
    render(<CyclesListPage cycles={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("cycles-list-empty")).toBeTruthy();
  });
});

// ── CycleDetailPage ───────────────────────────────────────────────────────

describe("CycleDetailPage", () => {
  let CycleDetailPage: typeof import("../../src/surfaces/cycles/CycleDetailPage.js").CycleDetailPage;

  beforeEach(async () => {
    ({ CycleDetailPage } = await import("../../src/surfaces/cycles/CycleDetailPage.js"));
  });

  it("renders the cycle detail page container", () => {
    render(
      <CycleDetailPage
        cycle={makeCycle()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("cycle-detail-page")).toBeTruthy();
  });

  it("renders the period_label as heading", () => {
    render(
      <CycleDetailPage
        cycle={makeCycle({ period_label: "2026-05" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByText("2026-05")).toBeTruthy();
  });

  it("renders ProvenanceBreadcrumb when origin_upload_id is set", () => {
    render(
      <CycleDetailPage
        cycle={makeCycle({ origin_upload_id: "u-origin-001" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("provenance-breadcrumb")).toBeTruthy();
  });

  it("renders close button disabled (RbacGate denied) for Operator role", () => {
    render(
      <CycleDetailPage
        cycle={makeCycle({ status: "closing" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        onClose={vi.fn()}
      />,
    );
    // RbacGate denied renders data-testid="rbac-gate-denied"
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders close button enabled (RbacGate allowed) for Approver role", () => {
    render(
      <CycleDetailPage
        cycle={makeCycle({ status: "closing" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("does not render close button when cycle is already closed", () => {
    render(
      <CycleDetailPage
        cycle={makeCycle({ status: "closed" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onClose={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("cycle-close-button")).toBeNull();
  });

  it("renders loading state", () => {
    render(
      <CycleDetailPage
        cycle={null}
        isLoading={true}
        error={null}
        currentRole="operator"
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("cycle-detail-loading")).toBeTruthy();
  });

  it("renders MoneyDisplay for total_billed_amount when set", () => {
    render(
      <CycleDetailPage
        cycle={makeCycle({ status: "closed", total_billed_amount: "98765.4321" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onClose={vi.fn()}
      />,
    );
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });
});
