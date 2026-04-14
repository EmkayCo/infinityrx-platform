// Step 5 — Approve
"use client";

import React from "react";
import { DollarDisplay } from "@shared/components/dollar-display";
import { ApprovalFlow } from "@shared/components/approval-flow";
import { APPROVAL_THRESHOLDS } from "@shared/lib/constants";
import { BillingCycleWizardData } from "./types";

interface ApproveStepProps {
  data: BillingCycleWizardData;
  onChange: (partial: Partial<BillingCycleWizardData>) => void;
  onApprove: () => void | Promise<void>;
}

// Stub approvers — in production, fetched from core-platform /users?role=approver
const STUB_APPROVERS = [
  { id: "user-001", name: "Sarah L.", email: "sarah@ifx.com", role: "Admin" },
  { id: "user-002", name: "Mike K.", email: "mike@ifx.com", role: "Billing Operator" },
];

export function ApproveStep({ data, onChange, onApprove }: ApproveStepProps) {
  const totalAmount =
    data.financial_preview?.ap_total ?? data.total_ap_amount ?? "0.00";

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-slate-300">Billing Cycle Summary</h3>
        <div className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-4 space-y-2">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <dt className="text-slate-500">File</dt>
            <dd className="text-slate-200 truncate">{data.upload_filename ?? "—"}</dd>

            <dt className="text-slate-500">Total Claims</dt>
            <dd className="text-slate-200 tabular-nums">
              {data.total_claims?.toLocaleString() ?? "—"}
            </dd>

            <dt className="text-slate-500">AP Total</dt>
            <dd>
              <DollarDisplay
                amount={data.financial_preview?.ap_total ?? data.total_ap_amount}
                size="md"
                showScale
              />
            </dd>

            <dt className="text-slate-500">AR Total</dt>
            <dd>
              <DollarDisplay
                amount={data.financial_preview?.ar_total ?? data.total_ar_amount}
                size="md"
                showScale
              />
            </dd>

            <dt className="text-slate-500">Fees</dt>
            <dd>
              <DollarDisplay
                amount={data.financial_preview?.fee_total ?? data.total_fee_amount}
                size="md"
                showScale
              />
            </dd>
          </dl>
        </div>
      </div>

      {/* Approval flow */}
      <ApprovalFlow
        amount={totalAmount}
        threshold={APPROVAL_THRESHOLDS.billingCycle}
        approvers={STUB_APPROVERS}
        onConfirm={onApprove}
        onSubmitForApproval={(approverId, notes) => {
          onChange({ approver_id: approverId, approval_notes: notes });
          return onApprove();
        }}
        confirmLabel="Confirm and Generate Outputs"
        summaryLabel="Total amount to approve"
      />
    </div>
  );
}
