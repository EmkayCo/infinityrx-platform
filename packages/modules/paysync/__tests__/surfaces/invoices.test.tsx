// packages/modules/paysync/__tests__/surfaces/invoices.test.tsx
// RTL tests for the invoices surface components.
// Uses happy-dom. Follows the cycles/batches test pattern.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import type { Invoice } from "@infinityrx/contract";

afterEach(() => cleanup());

// Shared fixtures

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000+00:00";

function makeInvoice(overrides: Partial<Invoice> = {}): Invoice {
  return {
    id: "11000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    invoice_number: "INV-2026-001",
    invoice_type: "client_billing",
    client_id: "c1000000-0000-0000-0000-000000000001",
    client_name: "Acme Health Plan",
    period_start: "2026-04-01",
    period_end: "2026-04-30",
    claims_subtotal: "50000.00",
    fees_subtotal: "2500.00",
    adjustments: "0.00",
    late_fees: "0.00",
    total: "52500.00",
    paid_amount: "0.00",
    claim_count: 500,
    status: "draft",
    due_date: "2026-05-15",
    created_at: NOW,
    ...overrides,
  };
}

// InvoicesListPage

describe("InvoicesListPage", () => {
  let InvoicesListPage: typeof import("../../src/surfaces/invoices/InvoicesListPage.js").InvoicesListPage;

  beforeEach(async () => {
    ({ InvoicesListPage } = await import("../../src/surfaces/invoices/InvoicesListPage.js"));
  });

  it("renders the invoices list page container", () => {
    render(<InvoicesListPage invoices={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("invoices-list-page")).toBeTruthy();
  });

  it("renders a row for each invoice", () => {
    const invoices = [
      makeInvoice({ id: "i1", invoice_number: "INV-2026-001" }),
      makeInvoice({ id: "i2", invoice_number: "INV-2026-002" }),
    ];
    render(<InvoicesListPage invoices={invoices} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("invoice-row")).toHaveLength(2);
  });

  it("renders invoice_number for each invoice", () => {
    render(<InvoicesListPage invoices={[makeInvoice()]} isLoading={false} error={null} />);
    expect(screen.getByText("INV-2026-001")).toBeTruthy();
  });

  it("renders MoneyDisplay for invoice total", () => {
    render(<InvoicesListPage invoices={[makeInvoice()]} isLoading={false} error={null} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders status badge with draft visible", () => {
    render(<InvoicesListPage invoices={[makeInvoice({ status: "draft" })]} isLoading={false} error={null} />);
    expect(screen.getByTestId("invoice-status-badge")).toBeTruthy();
  });

  it("renders loading state when isLoading=true", () => {
    render(<InvoicesListPage invoices={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("invoices-list-loading")).toBeTruthy();
  });

  it("renders error message when error is set", () => {
    render(<InvoicesListPage invoices={[]} isLoading={false} error="Network failure" />);
    expect(screen.getByTestId("invoices-list-error")).toBeTruthy();
  });

  it("renders empty state when no invoices", () => {
    render(<InvoicesListPage invoices={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("invoices-list-empty")).toBeTruthy();
  });
});

// InvoiceDetailPage

describe("InvoiceDetailPage", () => {
  let InvoiceDetailPage: typeof import("../../src/surfaces/invoices/InvoiceDetailPage.js").InvoiceDetailPage;

  beforeEach(async () => {
    ({ InvoiceDetailPage } = await import("../../src/surfaces/invoices/InvoiceDetailPage.js"));
  });

  it("renders the invoice detail page container", () => {
    render(
      <InvoiceDetailPage
        invoice={makeInvoice()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSend={vi.fn()}
      />,
    );
    expect(screen.getByTestId("invoice-detail-page")).toBeTruthy();
  });

  it("renders invoice_number as heading", () => {
    render(
      <InvoiceDetailPage
        invoice={makeInvoice({ invoice_number: "INV-2026-001" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSend={vi.fn()}
      />,
    );
    expect(screen.getByText("INV-2026-001")).toBeTruthy();
  });

  it("renders total via MoneyDisplay", () => {
    render(
      <InvoiceDetailPage
        invoice={makeInvoice()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSend={vi.fn()}
      />,
    );
    expect(screen.getAllByTestId("money-display").length).toBeGreaterThan(0);
  });

  it("renders ProvenanceBreadcrumb showing upload -> cycle -> batch -> invoice chain", () => {
    render(
      <InvoiceDetailPage
        invoice={makeInvoice({ status: "draft" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        originUploadId="u-origin-001"
        originCycleId="c-origin-001"
        originBatchId="b-origin-001"
        onSend={vi.fn()}
      />,
    );
    expect(screen.getByTestId("provenance-breadcrumb")).toBeTruthy();
  });

  it("renders send button disabled (RbacGate denied) for Operator role", () => {
    render(
      <InvoiceDetailPage
        invoice={makeInvoice({ status: "approved" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSend={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders send button enabled (RbacGate allowed) for Approver role", () => {
    render(
      <InvoiceDetailPage
        invoice={makeInvoice({ status: "approved" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onSend={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("does not render send button when invoice is already sent", () => {
    render(
      <InvoiceDetailPage
        invoice={makeInvoice({ status: "sent" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onSend={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("invoice-send-button")).toBeNull();
  });

  it("calls onSend with invoice id when Approver clicks send", () => {
    const onSend = vi.fn();
    render(
      <InvoiceDetailPage
        invoice={makeInvoice({ status: "approved" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onSend={onSend}
      />,
    );
    fireEvent.click(screen.getByTestId("invoice-send-button"));
    expect(onSend).toHaveBeenCalledWith("11000000-0000-0000-0000-000000000001");
  });

  it("renders loading state", () => {
    render(
      <InvoiceDetailPage
        invoice={null}
        isLoading={true}
        error={null}
        currentRole="operator"
        onSend={vi.fn()}
      />,
    );
    expect(screen.getByTestId("invoice-detail-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(
      <InvoiceDetailPage
        invoice={null}
        isLoading={false}
        error="Not found"
        currentRole="operator"
        onSend={vi.fn()}
      />,
    );
    expect(screen.getByTestId("invoice-detail-error")).toBeTruthy();
  });
});

// ArInvoiceDraftCard

describe("ArInvoiceDraftCard (inbox card)", () => {
  let ArInvoiceDraftCard: typeof import("../../src/inbox/cards/ArInvoiceDraftCard.js").default;

  beforeEach(async () => {
    ({ default: ArInvoiceDraftCard } = await import("../../src/inbox/cards/ArInvoiceDraftCard.js"));
  });

  it("renders the ar_invoice_draft inbox card", () => {
    const item = {
      id: "inbox-001",
      kind: "ar_invoice_draft" as const,
      tenant_id: TENANT,
      upload_id: null,
      rbac_required: "approver" as const,
      created_at: NOW,
      priority: "normal" as const,
      payload: {
        invoice_number: "INV-2026-002",
        total: "49900.00",
        invoice_id: "11000000-0000-0000-0000-000000000002",
      },
    };
    render(<ArInvoiceDraftCard item={item} />);
    expect(screen.getByTestId("inbox-card-ar_invoice_draft")).toBeTruthy();
  });

  it("renders invoice amount as string via MoneyDisplay", () => {
    const item = {
      id: "inbox-002",
      kind: "ar_invoice_draft" as const,
      tenant_id: TENANT,
      upload_id: null,
      rbac_required: "approver" as const,
      created_at: NOW,
      priority: "high" as const,
      payload: {
        invoice_number: "INV-2026-002",
        total: "49900.00",
        invoice_id: "11000000-0000-0000-0000-000000000002",
      },
    };
    render(<ArInvoiceDraftCard item={item} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders action link to invoice detail", () => {
    const item = {
      id: "inbox-003",
      kind: "ar_invoice_draft" as const,
      tenant_id: TENANT,
      upload_id: null,
      rbac_required: "approver" as const,
      created_at: NOW,
      priority: "normal" as const,
      payload: {
        invoice_number: "INV-2026-002",
        total: "49900.00",
        invoice_id: "11000000-0000-0000-0000-000000000002",
      },
    };
    render(<ArInvoiceDraftCard item={item} />);
    expect(screen.getByTestId("card-action-link")).toBeTruthy();
  });
});
