// Payment Batch Wizard local types.
import type { BatchRouting } from "@shared/types/payments";

export interface PaymentBatchWizardData {
  // Step 1 — Select Claims
  selected_claim_ids: string[];
  selected_total: string; // Decimal string, running total

  // Step 2 — Review Routing
  routing_summary: BatchRouting[];

  // Step 3 — Generate Files (preview generated in memory before approval)
  batch_id: string | null; // set after backend batch creation

  // Step 4 — Approve
  approver_id: string | null;
  approval_notes: string;

  // Step 5 — Transmit (output)
  transmission_statuses: Record<string, "pending" | "transmitting" | "transmitted" | "failed">;
}

export const INITIAL_BATCH_DATA: PaymentBatchWizardData = {
  selected_claim_ids: [],
  selected_total: "0.00",
  routing_summary: [],
  batch_id: null,
  approver_id: null,
  approval_notes: "",
  transmission_statuses: {},
};
