// packages/modules/paysync/__tests__/inbox/cards.test.tsx
// Smoke-render every inbox card stub. Asserts: each card mounts without
// crashing given a minimal InboxItem fixture, and renders the expected
// data-testid. Per Plan A R4.3 these are Task 5 stubs — replaced with real
// cards in Plans B–E; this test guards the typed-stub interface.

import type { ComponentType } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { InboxItem, InboxItemKind } from "../../src/inbox/types.js";
import UploadPendingReviewCard from "../../src/inbox/cards/UploadPendingReviewCard.js";
import UploadValidatedCard from "../../src/inbox/cards/UploadValidatedCard.js";
import CyclePendingCloseCard from "../../src/inbox/cards/CyclePendingCloseCard.js";
import CycleCloseReviewCard from "../../src/inbox/cards/CycleCloseReviewCard.js";
import BatchDraftedCard from "../../src/inbox/cards/BatchDraftedCard.js";
import ArInvoiceDraftCard from "../../src/inbox/cards/ArInvoiceDraftCard.js";
import ApPaymentRunHeldCard from "../../src/inbox/cards/ApPaymentRunHeldCard.js";
import BankingDiscrepancyCard from "../../src/inbox/cards/BankingDiscrepancyCard.js";
import ReconciliationPendingCard from "../../src/inbox/cards/ReconciliationPendingCard.js";
import CarryoverOpenCard from "../../src/inbox/cards/CarryoverOpenCard.js";
import JournalPeriodicReviewCard from "../../src/inbox/cards/JournalPeriodicReviewCard.js";

afterEach(() => cleanup());

const TENANT = "00000000-0000-0000-0000-000000000001";
const NOW = "2026-05-16T22:00:00.000Z";

function fixture(kind: InboxItemKind): InboxItem {
  return {
    id: `i-${kind}`,
    kind,
    tenant_id: TENANT,
    upload_id: null,
    rbac_required: "operator",
    created_at: NOW,
    priority: "normal",
    payload: {},
  };
}

const CARDS: ReadonlyArray<[InboxItemKind, ComponentType<{ item: InboxItem }>]> = [
  ["upload_pending_review",              UploadPendingReviewCard],
  ["upload_validated_awaiting_batching", UploadValidatedCard],
  ["cycle_pending_close",                CyclePendingCloseCard],
  ["cycle_close_review",                 CycleCloseReviewCard],
  ["batch_drafted",                      BatchDraftedCard],
  ["ar_invoice_draft",                   ArInvoiceDraftCard],
  ["ap_payment_run_held",                ApPaymentRunHeldCard],
  ["banking_discrepancy",                BankingDiscrepancyCard],
  ["reconciliation_pending",             ReconciliationPendingCard],
  ["carryover_open",                     CarryoverOpenCard],
  ["journal_periodic_review",            JournalPeriodicReviewCard],
];

describe("inbox card stubs", () => {
  it.each(CARDS)("%s card renders with correct data-testid", (kind, Card) => {
    render(<Card item={fixture(kind)} />);
    expect(screen.getByTestId(`inbox-card-${kind}`)).toBeTruthy();
  });

  it("count: all 11 InboxItemKind values have a card", () => {
    expect(CARDS).toHaveLength(11);
  });
});
