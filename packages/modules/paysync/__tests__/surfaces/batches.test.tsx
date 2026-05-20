// packages/modules/paysync/__tests__/surfaces/batches.test.tsx
// RTL tests for the batches surface components.
// Uses happy-dom. Follows the uploads/cycles test pattern.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import type { Batch } from "@infinityrx/contract";

afterEach(() => cleanup());

// ── Shared fixtures ──────────────────────────────────────────────────────

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000+00:00";

function makeBatch(overrides: Partial<Batch> = {}): Batch {
  return {
    id: "b1000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    batch_number: "BATCH-2026-001",
    payment_route: "ach",
    total_amount: "12345.67",
    payment_count: 10,
    ap_count: 10,
    status: "approved",
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  };
}

// ── BatchesListPage ───────────────────────────────────────────────────────

describe("BatchesListPage", () => {
  let BatchesListPage: typeof import("../../src/surfaces/batches/BatchesListPage.js").BatchesListPage;

  beforeEach(async () => {
    ({ BatchesListPage } = await import("../../src/surfaces/batches/BatchesListPage.js"));
  });

  it("renders the batches list page container", () => {
    render(<BatchesListPage batches={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("batches-list-page")).toBeTruthy();
  });

  it("renders a row for each batch", () => {
    const batches = [
      makeBatch({ id: "b1", batch_number: "BATCH-2026-001" }),
      makeBatch({ id: "b2", batch_number: "BATCH-2026-002" }),
    ];
    render(<BatchesListPage batches={batches} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("batch-row")).toHaveLength(2);
  });

  it("renders batch_number for each batch", () => {
    render(<BatchesListPage batches={[makeBatch()]} isLoading={false} error={null} />);
    expect(screen.getByText("BATCH-2026-001")).toBeTruthy();
  });

  it("renders MoneyDisplay for total_amount", () => {
    render(<BatchesListPage batches={[makeBatch()]} isLoading={false} error={null} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders status badge for each batch", () => {
    render(<BatchesListPage batches={[makeBatch({ status: "generated" })]} isLoading={false} error={null} />);
    expect(screen.getByTestId("batch-status-badge")).toBeTruthy();
  });

  it("renders loading state when isLoading=true", () => {
    render(<BatchesListPage batches={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("batches-list-loading")).toBeTruthy();
  });

  it("renders error message when error is set", () => {
    render(<BatchesListPage batches={[]} isLoading={false} error="Network failure" />);
    expect(screen.getByTestId("batches-list-error")).toBeTruthy();
  });

  it("renders empty state when no batches", () => {
    render(<BatchesListPage batches={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("batches-list-empty")).toBeTruthy();
  });
});

// ── BatchDetailPage ───────────────────────────────────────────────────────

describe("BatchDetailPage", () => {
  let BatchDetailPage: typeof import("../../src/surfaces/batches/BatchDetailPage.js").BatchDetailPage;

  beforeEach(async () => {
    ({ BatchDetailPage } = await import("../../src/surfaces/batches/BatchDetailPage.js"));
  });

  it("renders the batch detail page container", () => {
    render(
      <BatchDetailPage
        batch={makeBatch()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onRelease={vi.fn()}
        onHold={vi.fn()}
      />,
    );
    expect(screen.getByTestId("batch-detail-page")).toBeTruthy();
  });

  it("renders batch_number as heading", () => {
    render(
      <BatchDetailPage
        batch={makeBatch({ batch_number: "BATCH-2026-001" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        onRelease={vi.fn()}
        onHold={vi.fn()}
      />,
    );
    expect(screen.getByText("BATCH-2026-001")).toBeTruthy();
  });

  it("renders total_amount via MoneyDisplay", () => {
    render(
      <BatchDetailPage
        batch={makeBatch()}
        isLoading={false}
        error={null}
        currentRole="operator"
        onRelease={vi.fn()}
        onHold={vi.fn()}
      />,
    );
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders ProvenanceBreadcrumb when origin_upload_id is set", () => {
    render(
      <BatchDetailPage
        batch={makeBatch({ status: "approved" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        originUploadId="u-origin-001"
        onRelease={vi.fn()}
        onHold={vi.fn()}
      />,
    );
    expect(screen.getByTestId("provenance-breadcrumb")).toBeTruthy();
  });

  it("renders release button disabled (RbacGate denied) for Operator role", () => {
    render(
      <BatchDetailPage
        batch={makeBatch({ status: "approved" })}
        isLoading={false}
        error={null}
        currentRole="operator"
        onRelease={vi.fn()}
        onHold={vi.fn()}
      />,
    );
    // Both release and hold gates are denied for operator; getAllByTestId handles multiple matches.
    expect(screen.getAllByTestId("rbac-gate-denied").length).toBeGreaterThan(0);
  });

  it("renders release button enabled (RbacGate allowed) for Approver role", () => {
    render(
      <BatchDetailPage
        batch={makeBatch({ status: "approved" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onRelease={vi.fn()}
        onHold={vi.fn()}
      />,
    );
    // Both release and hold gates are allowed for approver; getAllByTestId handles multiple matches.
    expect(screen.getAllByTestId("rbac-gate-allowed").length).toBeGreaterThan(0);
  });

  it("does not render release button when batch is already settled", () => {
    render(
      <BatchDetailPage
        batch={makeBatch({ status: "settled" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onRelease={vi.fn()}
        onHold={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("batch-release-button")).toBeNull();
  });

  it("calls onRelease with batch id when Approver clicks release", () => {
    const onRelease = vi.fn();
    render(
      <BatchDetailPage
        batch={makeBatch({ status: "approved" })}
        isLoading={false}
        error={null}
        currentRole="approver"
        onRelease={onRelease}
        onHold={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("batch-release-button"));
    expect(onRelease).toHaveBeenCalledWith("b1000000-0000-0000-0000-000000000001");
  });

  it("renders loading state", () => {
    render(
      <BatchDetailPage
        batch={null}
        isLoading={true}
        error={null}
        currentRole="operator"
        onRelease={vi.fn()}
        onHold={vi.fn()}
      />,
    );
    expect(screen.getByTestId("batch-detail-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(
      <BatchDetailPage
        batch={null}
        isLoading={false}
        error="Not found"
        currentRole="operator"
        onRelease={vi.fn()}
        onHold={vi.fn()}
      />,
    );
    expect(screen.getByTestId("batch-detail-error")).toBeTruthy();
  });
});

// ── BatchDraftedCard ──────────────────────────────────────────────────────

describe("BatchDraftedCard (inbox card)", () => {
  let BatchDraftedCard: typeof import("../../src/inbox/cards/BatchDraftedCard.js").default;

  beforeEach(async () => {
    ({ default: BatchDraftedCard } = await import("../../src/inbox/cards/BatchDraftedCard.js"));
  });

  it("renders the batch_drafted inbox card", () => {
    const item = {
      id: "inbox-001",
      kind: "batch_drafted" as const,
      tenant_id: TENANT,
      upload_id: "u0000000-0000-0000-0000-000000000001",
      rbac_required: "approver" as const,
      created_at: NOW,
      priority: "normal" as const,
      payload: {
        batch_number: "BATCH-2026-003",
        total_amount: "5000.00",
        batch_id: "b1000000-0000-0000-0000-000000000003",
      },
    };
    render(<BatchDraftedCard item={item} />);
    expect(screen.getByTestId("inbox-card-batch_drafted")).toBeTruthy();
  });

  it("renders batch amount via MoneyDisplay", () => {
    const item = {
      id: "inbox-002",
      kind: "batch_drafted" as const,
      tenant_id: TENANT,
      upload_id: null,
      rbac_required: "approver" as const,
      created_at: NOW,
      priority: "high" as const,
      payload: {
        batch_number: "BATCH-2026-003",
        total_amount: "5000.00",
        batch_id: "b1000000-0000-0000-0000-000000000003",
      },
    };
    render(<BatchDraftedCard item={item} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders action link to batch detail", () => {
    const item = {
      id: "inbox-003",
      kind: "batch_drafted" as const,
      tenant_id: TENANT,
      upload_id: null,
      rbac_required: "approver" as const,
      created_at: NOW,
      priority: "normal" as const,
      payload: {
        batch_number: "BATCH-2026-003",
        total_amount: "5000.00",
        batch_id: "b1000000-0000-0000-0000-000000000003",
      },
    };
    render(<BatchDraftedCard item={item} />);
    expect(screen.getByTestId("card-action-link")).toBeTruthy();
  });
});
