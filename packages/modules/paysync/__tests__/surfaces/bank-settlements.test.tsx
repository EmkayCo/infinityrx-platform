// packages/modules/paysync/__tests__/surfaces/bank-settlements.test.tsx
// RTL tests for the bank-settlements surface components.
// Uses happy-dom. Follows the batches/carryovers test pattern.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import type { BankSettlement } from "@infinityrx/contract";

afterEach(() => cleanup());

// ── Shared fixtures ──────────────────────────────────────────────────────

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000+00:00";

function makeSettlement(overrides: Partial<BankSettlement> = {}): BankSettlement {
  return {
    id: "f0000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    batch_id: "b1000000-0000-0000-0000-000000000001",
    bank_reference: "ACH-20260502-001",
    expected_amount: "12345.67",
    actual_amount: "12345.67",
    status: "matched",
    settlement_date: "2026-05-02",
    resolved_at: null,
    created_at: NOW,
    ...overrides,
  };
}

// ── BankSettlementsListPage ───────────────────────────────────────────────

describe("BankSettlementsListPage", () => {
  let BankSettlementsListPage: typeof import("../../src/surfaces/bank-settlements/BankSettlementsListPage.js").BankSettlementsListPage;

  beforeEach(async () => {
    ({ BankSettlementsListPage } = await import("../../src/surfaces/bank-settlements/BankSettlementsListPage.js"));
  });

  it("renders the bank settlements list page container", () => {
    render(<BankSettlementsListPage settlements={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("bank-settlements-list-page")).toBeTruthy();
  });

  it("renders a row for each settlement", () => {
    const settlements = [
      makeSettlement({ id: "f1" }),
      makeSettlement({ id: "f2", status: "discrepancy" }),
    ];
    render(<BankSettlementsListPage settlements={settlements} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("bank-settlement-row")).toHaveLength(2);
  });

  it("renders bank_reference for each settlement", () => {
    render(<BankSettlementsListPage settlements={[makeSettlement()]} isLoading={false} error={null} />);
    expect(screen.getByText("ACH-20260502-001")).toBeTruthy();
  });

  it("renders status badge for each settlement", () => {
    render(<BankSettlementsListPage settlements={[makeSettlement({ status: "discrepancy" })]} isLoading={false} error={null} />);
    expect(screen.getByTestId("bank-settlement-status-badge")).toBeTruthy();
  });

  it("renders discrepancy badge for settlements with discrepancy status", () => {
    render(<BankSettlementsListPage settlements={[makeSettlement({ status: "discrepancy" })]} isLoading={false} error={null} />);
    const badge = screen.getByTestId("bank-settlement-status-badge");
    expect(badge.getAttribute("data-status")).toBe("discrepancy");
  });

  it("renders MoneyDisplay for expected_amount and actual_amount", () => {
    render(<BankSettlementsListPage settlements={[makeSettlement()]} isLoading={false} error={null} />);
    const displays = screen.getAllByTestId("money-display");
    expect(displays.length).toBeGreaterThanOrEqual(2);
  });

  it("renders loading state when isLoading=true", () => {
    render(<BankSettlementsListPage settlements={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("bank-settlements-list-loading")).toBeTruthy();
  });

  it("renders error message when error is set", () => {
    render(<BankSettlementsListPage settlements={[]} isLoading={false} error="Network failure" />);
    expect(screen.getByTestId("bank-settlements-list-error")).toBeTruthy();
  });

  it("renders empty state when no settlements", () => {
    render(<BankSettlementsListPage settlements={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("bank-settlements-list-empty")).toBeTruthy();
  });
});

// ── BankSettlementDetailPage ──────────────────────────────────────────────

describe("BankSettlementDetailPage", () => {
  let BankSettlementDetailPage: typeof import("../../src/surfaces/bank-settlements/BankSettlementDetailPage.js").BankSettlementDetailPage;

  beforeEach(async () => {
    ({ BankSettlementDetailPage } = await import("../../src/surfaces/bank-settlements/BankSettlementDetailPage.js"));
  });

  it("renders the bank settlement detail page container", () => {
    render(
      <BankSettlementDetailPage
        settlement={makeSettlement()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onResolveDiscrepancy={vi.fn()}
      />,
    );
    expect(screen.getByTestId("bank-settlement-detail-page")).toBeTruthy();
  });

  it("renders expected_amount and actual_amount via MoneyDisplay", () => {
    render(
      <BankSettlementDetailPage
        settlement={makeSettlement()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onResolveDiscrepancy={vi.fn()}
      />,
    );
    const displays = screen.getAllByTestId("money-display");
    expect(displays.length).toBeGreaterThanOrEqual(2);
  });

  it("renders resolve discrepancy button disabled (RbacGate denied) for Operator role", () => {
    render(
      <BankSettlementDetailPage
        settlement={makeSettlement({ status: "discrepancy" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        onResolveDiscrepancy={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders resolve discrepancy button enabled (RbacGate allowed) for Approver role", () => {
    render(
      <BankSettlementDetailPage
        settlement={makeSettlement({ status: "discrepancy" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onResolveDiscrepancy={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("does not render resolve button when settlement is already resolved", () => {
    render(
      <BankSettlementDetailPage
        settlement={makeSettlement({ status: "resolved", resolved_at: NOW })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onResolveDiscrepancy={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("bank-settlement-resolve-button")).toBeNull();
  });

  it("calls onResolveDiscrepancy with settlement id when Approver clicks resolve", () => {
    const onResolveDiscrepancy = vi.fn();
    render(
      <BankSettlementDetailPage
        settlement={makeSettlement({ status: "discrepancy" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onResolveDiscrepancy={onResolveDiscrepancy}
      />,
    );
    fireEvent.click(screen.getByTestId("bank-settlement-resolve-button"));
    expect(onResolveDiscrepancy).toHaveBeenCalledWith("f0000000-0000-0000-0000-000000000001");
  });

  it("renders loading state", () => {
    render(
      <BankSettlementDetailPage
        settlement={null}
        isLoading={true}
        error={null}
        currentRole="operator"
        onResolveDiscrepancy={vi.fn()}
      />,
    );
    expect(screen.getByTestId("bank-settlement-detail-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(
      <BankSettlementDetailPage
        settlement={null}
        isLoading={false}
        error="Not found"
        currentRole="operator"
        onResolveDiscrepancy={vi.fn()}
      />,
    );
    expect(screen.getByTestId("bank-settlement-detail-error")).toBeTruthy();
  });
});
