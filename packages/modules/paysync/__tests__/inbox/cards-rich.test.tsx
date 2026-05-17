// packages/modules/paysync/__tests__/inbox/cards-rich.test.tsx
// Rich content tests for the 4 Plan B inbox cards (upload x2, cycle x2).
// The original cards.test.tsx guards the stub interface (data-testid per kind).
// This file asserts the rich content that Plan B implementations add.

import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { InboxItem } from "../../src/inbox/types.js";

afterEach(() => cleanup());

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000+00:00";

function makeItem(kind: InboxItem["kind"], payload: Record<string, unknown> = {}): InboxItem {
  return {
    id: `i-${kind}`,
    kind,
    tenant_id: TENANT,
    upload_id: "u0000000-0000-0000-0000-000000000001",
    rbac_required: "operator",
    created_at: NOW,
    priority: "normal",
    payload,
  };
}

// ── UploadPendingReviewCard ───────────────────────────────────────────────

describe("UploadPendingReviewCard (rich)", () => {
  let Card: typeof import("../../src/inbox/cards/UploadPendingReviewCard.js").default;

  beforeEach(async () => {
    ({ default: Card } = await import("../../src/inbox/cards/UploadPendingReviewCard.js"));
  });

  it("renders the expected data-testid (interface guard)", () => {
    render(<Card item={makeItem("upload_pending_review")} />);
    expect(screen.getByTestId("inbox-card-upload_pending_review")).toBeTruthy();
  });

  it("renders the filename from payload", () => {
    render(<Card item={makeItem("upload_pending_review", { filename: "claims-q1.csv" })} />);
    expect(screen.getByText("claims-q1.csv")).toBeTruthy();
  });

  it("renders the error_count from payload", () => {
    render(<Card item={makeItem("upload_pending_review", { error_count: 7 })} />);
    expect(screen.getByTestId("card-error-count")).toBeTruthy();
  });

  it("renders priority=high indicator when item.priority is high", () => {
    const item: InboxItem = { ...makeItem("upload_pending_review"), priority: "high" };
    render(<Card item={item} />);
    expect(screen.getByTestId("card-priority-high")).toBeTruthy();
  });

  it("renders a link to the upload detail page via upload_id", () => {
    render(<Card item={makeItem("upload_pending_review")} />);
    expect(screen.getByTestId("card-action-link")).toBeTruthy();
  });
});

// ── UploadValidatedCard ───────────────────────────────────────────────────

describe("UploadValidatedCard (rich)", () => {
  let Card: typeof import("../../src/inbox/cards/UploadValidatedCard.js").default;

  beforeEach(async () => {
    ({ default: Card } = await import("../../src/inbox/cards/UploadValidatedCard.js"));
  });

  it("renders the expected data-testid (interface guard)", () => {
    render(<Card item={makeItem("upload_validated_awaiting_batching")} />);
    expect(screen.getByTestId("inbox-card-upload_validated_awaiting_batching")).toBeTruthy();
  });

  it("renders the filename from payload", () => {
    render(<Card item={makeItem("upload_validated_awaiting_batching", { filename: "claims-q2.csv" })} />);
    expect(screen.getByText("claims-q2.csv")).toBeTruthy();
  });

  it("renders the claim_count from payload", () => {
    render(<Card item={makeItem("upload_validated_awaiting_batching", { claim_count: 42 })} />);
    expect(screen.getByTestId("card-claim-count")).toBeTruthy();
  });

  it("renders a link to the upload detail page via upload_id", () => {
    render(<Card item={makeItem("upload_validated_awaiting_batching")} />);
    expect(screen.getByTestId("card-action-link")).toBeTruthy();
  });
});

// ── CyclePendingCloseCard ─────────────────────────────────────────────────

describe("CyclePendingCloseCard (rich)", () => {
  let Card: typeof import("../../src/inbox/cards/CyclePendingCloseCard.js").default;

  beforeEach(async () => {
    ({ default: Card } = await import("../../src/inbox/cards/CyclePendingCloseCard.js"));
  });

  it("renders the expected data-testid (interface guard)", () => {
    render(<Card item={makeItem("cycle_pending_close")} />);
    expect(screen.getByTestId("inbox-card-cycle_pending_close")).toBeTruthy();
  });

  it("renders the period_label from payload", () => {
    render(<Card item={makeItem("cycle_pending_close", { period_label: "2026-03" })} />);
    expect(screen.getByText("2026-03")).toBeTruthy();
  });

  it("renders priority=high indicator when item.priority is high", () => {
    const item: InboxItem = { ...makeItem("cycle_pending_close"), priority: "high" };
    render(<Card item={item} />);
    expect(screen.getByTestId("card-priority-high")).toBeTruthy();
  });

  it("renders a link to the cycle detail page via payload.cycle_id", () => {
    render(<Card item={makeItem("cycle_pending_close", { cycle_id: "c-111" })} />);
    expect(screen.getByTestId("card-action-link")).toBeTruthy();
  });
});

// ── CycleCloseReviewCard ──────────────────────────────────────────────────

describe("CycleCloseReviewCard (rich)", () => {
  let Card: typeof import("../../src/inbox/cards/CycleCloseReviewCard.js").default;

  beforeEach(async () => {
    ({ default: Card } = await import("../../src/inbox/cards/CycleCloseReviewCard.js"));
  });

  it("renders the expected data-testid (interface guard)", () => {
    render(<Card item={makeItem("cycle_close_review")} />);
    expect(screen.getByTestId("inbox-card-cycle_close_review")).toBeTruthy();
  });

  it("renders the period_label from payload", () => {
    render(<Card item={makeItem("cycle_close_review", { period_label: "2026-02" })} />);
    expect(screen.getByText("2026-02")).toBeTruthy();
  });

  it("renders total_billed_amount via MoneyDisplay when present in payload", () => {
    render(<Card item={makeItem("cycle_close_review", { total_billed_amount: "98765.4321" })} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders a link to the cycle detail page via payload.cycle_id", () => {
    render(<Card item={makeItem("cycle_close_review", { cycle_id: "c-222" })} />);
    expect(screen.getByTestId("card-action-link")).toBeTruthy();
  });
});

// ── CarryoverOpenCard ─────────────────────────────────────────────────────

describe("CarryoverOpenCard (rich)", () => {
  let Card: typeof import("../../src/inbox/cards/CarryoverOpenCard.js").default;

  beforeEach(async () => {
    ({ default: Card } = await import("../../src/inbox/cards/CarryoverOpenCard.js"));
  });

  it("renders the expected data-testid (interface guard)", () => {
    render(<Card item={makeItem("carryover_open")} />);
    expect(screen.getByTestId("inbox-card-carryover_open")).toBeTruthy();
  });

  it("renders carried_amount via MoneyDisplay when present in payload", () => {
    render(<Card item={makeItem("carryover_open", { carried_amount: "250.00" })} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders from_period from payload", () => {
    render(<Card item={makeItem("carryover_open", { from_period: "2026-04" })} />);
    expect(screen.getByText(/2026-04/)).toBeTruthy();
  });

  it("renders priority=high indicator when item.priority is high", () => {
    const item: InboxItem = { ...makeItem("carryover_open"), priority: "high" };
    render(<Card item={item} />);
    expect(screen.getByTestId("card-priority-high")).toBeTruthy();
  });

  it("renders action link to carryover detail page via payload.carryover_id", () => {
    render(<Card item={makeItem("carryover_open", { carryover_id: "d-001" })} />);
    const link = screen.getByTestId("card-action-link") as HTMLAnchorElement;
    expect(link.href).toContain("d-001");
  });
});

// ── BankingDiscrepancyCard ────────────────────────────────────────────────

describe("BankingDiscrepancyCard (rich)", () => {
  let Card: typeof import("../../src/inbox/cards/BankingDiscrepancyCard.js").default;

  beforeEach(async () => {
    ({ default: Card } = await import("../../src/inbox/cards/BankingDiscrepancyCard.js"));
  });

  it("renders the expected data-testid (interface guard)", () => {
    render(<Card item={makeItem("banking_discrepancy")} />);
    expect(screen.getByTestId("inbox-card-banking_discrepancy")).toBeTruthy();
  });

  it("renders expected_amount via MoneyDisplay", () => {
    render(<Card item={makeItem("banking_discrepancy", { expected_amount: "12345.67", actual_amount: "12345.00" })} />);
    const displays = screen.getAllByTestId("money-display");
    expect(displays.length).toBeGreaterThanOrEqual(2);
  });

  it("renders bank_reference from payload", () => {
    render(<Card item={makeItem("banking_discrepancy", { bank_reference: "ACH-20260511-002" })} />);
    expect(screen.getByText("ACH-20260511-002")).toBeTruthy();
  });

  it("renders priority=high indicator when item.priority is high", () => {
    const item: InboxItem = { ...makeItem("banking_discrepancy"), priority: "high" };
    render(<Card item={item} />);
    expect(screen.getByTestId("card-priority-high")).toBeTruthy();
  });

  it("renders action link to bank settlement detail page via payload.settlement_id", () => {
    render(<Card item={makeItem("banking_discrepancy", { settlement_id: "f-001" })} />);
    const link = screen.getByTestId("card-action-link") as HTMLAnchorElement;
    expect(link.href).toContain("f-001");
  });
});

// ── ReconciliationPendingCard ─────────────────────────────────────────────

describe("ReconciliationPendingCard (rich)", () => {
  let Card: typeof import("../../src/inbox/cards/ReconciliationPendingCard.js").default;

  beforeEach(async () => {
    ({ default: Card } = await import("../../src/inbox/cards/ReconciliationPendingCard.js"));
  });

  it("renders the expected data-testid (interface guard)", () => {
    render(<Card item={makeItem("reconciliation_pending")} />);
    expect(screen.getByTestId("inbox-card-reconciliation_pending")).toBeTruthy();
  });

  it("renders period_label from payload", () => {
    render(<Card item={makeItem("reconciliation_pending", { period_label: "2026-05" })} />);
    expect(screen.getByText("2026-05")).toBeTruthy();
  });

  it("renders total_billed via MoneyDisplay when present in payload", () => {
    render(<Card item={makeItem("reconciliation_pending", { total_billed: "98765.43" })} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders priority=high indicator when item.priority is high", () => {
    const item: InboxItem = { ...makeItem("reconciliation_pending"), priority: "high" };
    render(<Card item={item} />);
    expect(screen.getByTestId("card-priority-high")).toBeTruthy();
  });

  it("renders action link to reconciliation detail page via payload.reconciliation_id", () => {
    render(<Card item={makeItem("reconciliation_pending", { reconciliation_id: "r-001" })} />);
    const link = screen.getByTestId("card-action-link") as HTMLAnchorElement;
    expect(link.href).toContain("r-001");
  });
});

