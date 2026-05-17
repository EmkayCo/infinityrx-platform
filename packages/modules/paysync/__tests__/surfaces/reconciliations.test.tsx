// packages/modules/paysync/__tests__/surfaces/reconciliations.test.tsx
// RTL tests for the reconciliations surface components.
// Uses happy-dom. Follows the batches/bank-settlements test pattern.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import type { Reconciliation } from "@infinityrx/contract";

afterEach(() => cleanup());

// ── Shared fixtures ──────────────────────────────────────────────────────

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000+00:00";

function makeReconciliation(overrides: Partial<Reconciliation> = {}): Reconciliation {
  return {
    id: "10000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    period_label: "2026-04",
    status: "pending",
    total_billed: "98765.43",
    total_paid: "98765.43",
    variance: "0.00",
    finalized_at: null,
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  };
}

// ── ReconciliationsListPage ───────────────────────────────────────────────

describe("ReconciliationsListPage", () => {
  let ReconciliationsListPage: typeof import("../../src/surfaces/reconciliations/ReconciliationsListPage.js").ReconciliationsListPage;

  beforeEach(async () => {
    ({ ReconciliationsListPage } = await import("../../src/surfaces/reconciliations/ReconciliationsListPage.js"));
  });

  it("renders the reconciliations list page container", () => {
    render(<ReconciliationsListPage reconciliations={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("reconciliations-list-page")).toBeTruthy();
  });

  it("renders a row for each reconciliation", () => {
    const reconciliations = [
      makeReconciliation({ id: "r1", period_label: "2026-04" }),
      makeReconciliation({ id: "r2", period_label: "2026-03" }),
    ];
    render(<ReconciliationsListPage reconciliations={reconciliations} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("reconciliation-row")).toHaveLength(2);
  });

  it("renders period_label for each reconciliation", () => {
    render(<ReconciliationsListPage reconciliations={[makeReconciliation()]} isLoading={false} error={null} />);
    expect(screen.getByText("2026-04")).toBeTruthy();
  });

  it("renders status badge for each reconciliation", () => {
    render(<ReconciliationsListPage reconciliations={[makeReconciliation({ status: "pending" })]} isLoading={false} error={null} />);
    expect(screen.getByTestId("reconciliation-status-badge")).toBeTruthy();
  });

  it("renders MoneyDisplay for total_billed when present", () => {
    render(<ReconciliationsListPage reconciliations={[makeReconciliation()]} isLoading={false} error={null} />);
    const displays = screen.getAllByTestId("money-display");
    expect(displays.length).toBeGreaterThanOrEqual(1);
  });

  it("renders loading state when isLoading=true", () => {
    render(<ReconciliationsListPage reconciliations={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("reconciliations-list-loading")).toBeTruthy();
  });

  it("renders error message when error is set", () => {
    render(<ReconciliationsListPage reconciliations={[]} isLoading={false} error="Network failure" />);
    expect(screen.getByTestId("reconciliations-list-error")).toBeTruthy();
  });

  it("renders empty state when no reconciliations", () => {
    render(<ReconciliationsListPage reconciliations={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("reconciliations-list-empty")).toBeTruthy();
  });
});

// ── ReconciliationDetailPage ──────────────────────────────────────────────

describe("ReconciliationDetailPage", () => {
  let ReconciliationDetailPage: typeof import("../../src/surfaces/reconciliations/ReconciliationDetailPage.js").ReconciliationDetailPage;

  beforeEach(async () => {
    ({ ReconciliationDetailPage } = await import("../../src/surfaces/reconciliations/ReconciliationDetailPage.js"));
  });

  it("renders the reconciliation detail page container", () => {
    render(
      <ReconciliationDetailPage
        reconciliation={makeReconciliation()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onFinalize={vi.fn()}
      />,
    );
    expect(screen.getByTestId("reconciliation-detail-page")).toBeTruthy();
  });

  it("renders period_label as heading", () => {
    render(
      <ReconciliationDetailPage
        reconciliation={makeReconciliation({ period_label: "2026-04" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        onFinalize={vi.fn()}
      />,
    );
    expect(screen.getByText("2026-04")).toBeTruthy();
  });

  it("renders total_billed via MoneyDisplay when present", () => {
    render(
      <ReconciliationDetailPage
        reconciliation={makeReconciliation()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onFinalize={vi.fn()}
      />,
    );
    const displays = screen.getAllByTestId("money-display");
    expect(displays.length).toBeGreaterThanOrEqual(1);
  });

  it("renders finalize button disabled (RbacGate denied) for Operator role", () => {
    render(
      <ReconciliationDetailPage
        reconciliation={makeReconciliation({ status: "in_progress" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        onFinalize={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders finalize button enabled (RbacGate allowed) for Approver role", () => {
    render(
      <ReconciliationDetailPage
        reconciliation={makeReconciliation({ status: "in_progress" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onFinalize={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("does not render finalize button when reconciliation is already complete", () => {
    render(
      <ReconciliationDetailPage
        reconciliation={makeReconciliation({ status: "complete", finalized_at: NOW })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onFinalize={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("reconciliation-finalize-button")).toBeNull();
  });

  it("calls onFinalize with reconciliation id when Approver clicks finalize", () => {
    const onFinalize = vi.fn();
    render(
      <ReconciliationDetailPage
        reconciliation={makeReconciliation({ status: "in_progress" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onFinalize={onFinalize}
      />,
    );
    fireEvent.click(screen.getByTestId("reconciliation-finalize-button"));
    expect(onFinalize).toHaveBeenCalledWith("10000000-0000-0000-0000-000000000001");
  });

  it("renders loading state", () => {
    render(
      <ReconciliationDetailPage
        reconciliation={null}
        isLoading={true}
        error={null}
        currentRole="operator"
        onFinalize={vi.fn()}
      />,
    );
    expect(screen.getByTestId("reconciliation-detail-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(
      <ReconciliationDetailPage
        reconciliation={null}
        isLoading={false}
        error="Not found"
        currentRole="operator"
        onFinalize={vi.fn()}
      />,
    );
    expect(screen.getByTestId("reconciliation-detail-error")).toBeTruthy();
  });
});
