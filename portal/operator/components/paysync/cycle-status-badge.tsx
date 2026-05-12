"use client";

import { StatusBadge, type StatusVariant } from "@/components/ui/status-badge";
import type {
  CycleStatus, BatchStatus, InvoiceStatus, ManualApStatus,
} from "@shared/lib/paysync-api";

const CYCLE_VARIANTS: Record<CycleStatus, StatusVariant> = {
  open: "info",
  closing: "warning",
  closed: "neutral",
  invoiced: "info",
  paid: "success",
  reconciled: "success",
  closed_finalized: "success",
};

export function CycleStatusBadge({ status }: { status: CycleStatus }) {
  return <StatusBadge status={status.replace(/_/g, " ")} variant={CYCLE_VARIANTS[status]} />;
}

const BATCH_VARIANTS: Record<BatchStatus, StatusVariant> = {
  draft: "warning",
  pending_approval: "warning",
  approved: "info",
  submitted: "info",
  settled: "success",
  reconciled: "success",
  voided: "neutral",
  failed: "error",
};

export function BatchStatusBadge({ status }: { status: BatchStatus }) {
  return <StatusBadge status={status.replace(/_/g, " ")} variant={BATCH_VARIANTS[status]} />;
}

const INVOICE_VARIANTS: Record<InvoiceStatus, StatusVariant> = {
  draft: "warning",
  finalized: "info",
  sent: "info",
  paid: "success",
  partial: "warning",
  reconciled: "success",
  voided: "neutral",
};

export function InvoiceStatusBadge({ status }: { status: InvoiceStatus }) {
  return <StatusBadge status={status.replace(/_/g, " ")} variant={INVOICE_VARIANTS[status]} />;
}

const MANUAL_AP_VARIANTS: Record<ManualApStatus, StatusVariant> = {
  draft: "warning",
  pending: "warning",
  recognized: "info",
  submitted: "info",
  processed: "success",
  failed: "error",
  voided: "neutral",
};

export function ManualApStatusBadge({ status }: { status: ManualApStatus }) {
  return <StatusBadge status={status.replace(/_/g, " ")} variant={MANUAL_AP_VARIANTS[status]} />;
}
