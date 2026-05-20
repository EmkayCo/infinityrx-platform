// packages/modules/paysync/__tests__/surfaces/payment-runs.test.tsx
// RTL tests for the payment-runs surface components.
// Uses happy-dom. Follows the cycles/batches/invoices test pattern.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import type { PaymentRun } from "@infinityrx/contract";

afterEach(() => cleanup());

// Shared fixtures

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000+00:00";

function makeRun(overrides: Partial<PaymentRun> = {}): PaymentRun {
  return {
    id: "20000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    batch_id: "b1000000-0000-0000-0000-000000000001",
    status: "pending",
    total_amount: "67890.12",
    payment_count: 25,
    run_at: NOW,
    completed_at: null,
    created_at: NOW,
    ...overrides,
  };
}

// PaymentRunsListPage

describe("PaymentRunsListPage", () => {
  let PaymentRunsListPage: typeof import("../../src/surfaces/payment-runs/PaymentRunsListPage.js").PaymentRunsListPage;

  beforeEach(async () => {
    ({ PaymentRunsListPage } = await import("../../src/surfaces/payment-runs/PaymentRunsListPage.js"));
  });

  it("renders the payment runs list page container", () => {
    render(<PaymentRunsListPage runs={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("payment-runs-list-page")).toBeTruthy();
  });

  it("renders a row for each payment run", () => {
    const runs = [
      makeRun({ id: "r1" }),
      makeRun({ id: "r2", status: "completed" }),
    ];
    render(<PaymentRunsListPage runs={runs} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("payment-run-row")).toHaveLength(2);
  });

  it("renders MoneyDisplay for total_amount", () => {
    render(<PaymentRunsListPage runs={[makeRun()]} isLoading={false} error={null} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders status badge for each run", () => {
    render(<PaymentRunsListPage runs={[makeRun({ status: "held" })]} isLoading={false} error={null} />);
    expect(screen.getByTestId("payment-run-status-badge")).toBeTruthy();
  });

  it("renders loading state when isLoading=true", () => {
    render(<PaymentRunsListPage runs={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("payment-runs-list-loading")).toBeTruthy();
  });

  it("renders error message when error is set", () => {
    render(<PaymentRunsListPage runs={[]} isLoading={false} error="Network failure" />);
    expect(screen.getByTestId("payment-runs-list-error")).toBeTruthy();
  });

  it("renders empty state when no runs", () => {
    render(<PaymentRunsListPage runs={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("payment-runs-list-empty")).toBeTruthy();
  });
});

// PaymentRunDetailPage

describe("PaymentRunDetailPage", () => {
  let PaymentRunDetailPage: typeof import("../../src/surfaces/payment-runs/PaymentRunDetailPage.js").PaymentRunDetailPage;

  beforeEach(async () => {
    ({ PaymentRunDetailPage } = await import("../../src/surfaces/payment-runs/PaymentRunDetailPage.js"));
  });

  it("renders the payment run detail page container", () => {
    render(
      <PaymentRunDetailPage
        run={makeRun()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onRelease={vi.fn()}
      />,
    );
    expect(screen.getByTestId("payment-run-detail-page")).toBeTruthy();
  });

  it("renders total_amount via MoneyDisplay", () => {
    render(
      <PaymentRunDetailPage
        run={makeRun()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onRelease={vi.fn()}
      />,
    );
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders ProvenanceBreadcrumb when originUploadId is set", () => {
    render(
      <PaymentRunDetailPage
        run={makeRun({ status: "pending" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        originUploadId="u-origin-001"
        onRelease={vi.fn()}
      />,
    );
    expect(screen.getByTestId("provenance-breadcrumb")).toBeTruthy();
  });

  it("renders release button disabled (RbacGate denied) for Operator role", () => {
    render(
      <PaymentRunDetailPage
        run={makeRun({ status: "pending" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        onRelease={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders release button enabled (RbacGate allowed) for Approver role", () => {
    render(
      <PaymentRunDetailPage
        run={makeRun({ status: "pending" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onRelease={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("does not render release button when run is completed", () => {
    render(
      <PaymentRunDetailPage
        run={makeRun({ status: "completed" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onRelease={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("payment-run-release-button")).toBeNull();
  });

  it("calls onRelease with run id when Approver clicks release", () => {
    const onRelease = vi.fn();
    render(
      <PaymentRunDetailPage
        run={makeRun({ status: "pending" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onRelease={onRelease}
      />,
    );
    fireEvent.click(screen.getByTestId("payment-run-release-button"));
    expect(onRelease).toHaveBeenCalledWith("20000000-0000-0000-0000-000000000001");
  });

  it("renders loading state", () => {
    render(
      <PaymentRunDetailPage
        run={null}
        isLoading={true}
        error={null}
        currentRole="operator"
        onRelease={vi.fn()}
      />,
    );
    expect(screen.getByTestId("payment-run-detail-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(
      <PaymentRunDetailPage
        run={null}
        isLoading={false}
        error="Not found"
        currentRole="operator"
        onRelease={vi.fn()}
      />,
    );
    expect(screen.getByTestId("payment-run-detail-error")).toBeTruthy();
  });
});

// ManualApForm

describe("ManualApForm", () => {
  let ManualApForm: typeof import("../../src/surfaces/payment-runs/ManualApForm.js").ManualApForm;

  beforeEach(async () => {
    ({ ManualApForm } = await import("../../src/surfaces/payment-runs/ManualApForm.js"));
  });

  it("renders the manual AP entry form", () => {
    render(
      <ManualApForm
        currentRole="approver"
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByTestId("manual-ap-form")).toBeTruthy();
  });

  it("renders MoneyInput for the amount field", () => {
    render(
      <ManualApForm
        currentRole="approver"
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByTestId("money-input")).toBeTruthy();
  });

  it("renders submit gated to Approver role (denied for Operator)", () => {
    render(
      <ManualApForm
        currentRole="operator"
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders submit enabled for Approver role", () => {
    render(
      <ManualApForm
        currentRole="approver"
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });
});

// ApPaymentRunHeldCard

describe("ApPaymentRunHeldCard (inbox card)", () => {
  let ApPaymentRunHeldCard: typeof import("../../src/inbox/cards/ApPaymentRunHeldCard.js").default;

  beforeEach(async () => {
    ({ default: ApPaymentRunHeldCard } = await import("../../src/inbox/cards/ApPaymentRunHeldCard.js"));
  });

  it("renders the ap_payment_run_held inbox card", () => {
    const item = {
      id: "inbox-001",
      kind: "ap_payment_run_held" as const,
      tenant_id: TENANT,
      upload_id: null,
      rbac_required: "approver" as const,
      created_at: NOW,
      priority: "high" as const,
      payload: {
        run_id: "20000000-0000-0000-0000-000000000002",
        hold_reason: "OFAC screening pending",
        total_amount: "67890.12",
      },
    };
    render(<ApPaymentRunHeldCard item={item} />);
    expect(screen.getByTestId("inbox-card-ap_payment_run_held")).toBeTruthy();
  });

  it("renders hold_reason from payload", () => {
    const item = {
      id: "inbox-002",
      kind: "ap_payment_run_held" as const,
      tenant_id: TENANT,
      upload_id: null,
      rbac_required: "approver" as const,
      created_at: NOW,
      priority: "high" as const,
      payload: {
        run_id: "20000000-0000-0000-0000-000000000002",
        hold_reason: "OFAC screening pending",
        total_amount: "67890.12",
      },
    };
    render(<ApPaymentRunHeldCard item={item} />);
    expect(screen.getByTestId("card-hold-reason")).toBeTruthy();
    expect(screen.getByText("OFAC screening pending")).toBeTruthy();
  });

  it("renders action link to payment run detail", () => {
    const item = {
      id: "inbox-003",
      kind: "ap_payment_run_held" as const,
      tenant_id: TENANT,
      upload_id: null,
      rbac_required: "approver" as const,
      created_at: NOW,
      priority: "normal" as const,
      payload: {
        run_id: "20000000-0000-0000-0000-000000000002",
        hold_reason: "Manual review required",
        total_amount: "67890.12",
      },
    };
    render(<ApPaymentRunHeldCard item={item} />);
    expect(screen.getByTestId("card-action-link")).toBeTruthy();
  });
});
