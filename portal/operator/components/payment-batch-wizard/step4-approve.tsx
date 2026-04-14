// Step 4 — Approve Payment Batch
"use client";

import React from "react";
import { DollarDisplay } from "@shared/components/dollar-display";
import { ApprovalFlow } from "@shared/components/approval-flow";
import { APPROVAL_THRESHOLDS } from "@shared/lib/constants";
import { PaymentBatchWizardData } from "./types";

interface ApproveBatchStepProps {
  data: PaymentBatchWizardData;
  onChange: (partial: Partial<PaymentBatchWizardData>) => void;
  onApprove: () => void | Promise<void>;
}

const STUB_APPROVERS = [
  { id: "user-001", name: "Sarah L.", email: "sarah@ifx.com", role: "Admin" },
  { id: "user-002", name: "Mike K.", email: "mike@ifx.com", role: "Billing Operator" },
];

export function ApproveBatchStep({ data, onChange, onApprove }: ApproveBatchStepProps) {
  return (
    <div className="space-y-5">
      <div className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-4">
        <h3 className="text-sm font-semibold text-slate-300 mb-3">Payment Batch Summary</h3>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-slate-500">Claims selected</dt>
          <dd className="text-slate-200 tabular-nums">
            {data.selected_claim_ids.length.toLocaleString()}
          </dd>
          <dt className="text-slate-500">Vendors</dt>
          <dd className="text-slate-200">
            {[...new Set(data.routing_summary.map((r) => r.vendor_name))].join(", ") || "—"}
          </dd>
          <dt className="text-slate-500">Total Amount</dt>
          <dd>
            <DollarDisplay amount={data.selected_total} size="md" showScale />
          </dd>
        </dl>
      </div>

      <ApprovalFlow
        amount={data.selected_total}
        threshold={APPROVAL_THRESHOLDS.paymentBatch}
        approvers={STUB_APPROVERS}
        onConfirm={onApprove}
        onSubmitForApproval={(approverId, notes) => {
          onChange({ approver_id: approverId, approval_notes: notes });
          return onApprove();
        }}
        confirmLabel="Approve and Authorize Transmission"
        summaryLabel="Total payment batch amount"
      />
    </div>
  );
}
