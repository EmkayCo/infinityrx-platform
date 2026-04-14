// T2: ApprovalFlow — two-person approval widget for financial operations.
// When amount exceeds configurable threshold, swap Confirm button → Submit for Approval.
"use client";

import React, { useState } from "react";
import { ShieldCheck, AlertTriangle, UserCheck, Clock } from "lucide-react";
import { DollarDisplay } from "@shared/components/dollar-display";
import { cn, formatDollars } from "@shared/lib/format";
import type { Money } from "@shared/types/common";

export type ApprovalStatus = "not_required" | "pending" | "approved" | "rejected";

interface Approver {
  id: string;
  name: string;
  email: string;
  role: string;
}

interface ApprovalFlowProps {
  /** Dollar amount as string (Decimal serialized from backend) */
  amount: Money | null | undefined;
  /** Threshold above which approval is required (string, from APPROVAL_THRESHOLDS) */
  threshold: string;
  /** List of eligible approvers */
  approvers?: Approver[];
  /** Called when user submits for approval (selects approver and submits) */
  onSubmitForApproval?: (approverId: string, notes: string) => void | Promise<void>;
  /** Called when user confirms directly (below threshold) */
  onConfirm?: () => void | Promise<void>;
  /** Label for the confirm action */
  confirmLabel?: string;
  /** Current approval status */
  status?: ApprovalStatus;
  /** Rejection reason (if status === 'rejected') */
  rejectionReason?: string | null;
  /** Whether to show a summary of what is being approved */
  summaryLabel?: string;
  /** Whether button is disabled for another reason (e.g. form invalid) */
  disabled?: boolean;
  className?: string;
}

function exceedsThreshold(amount: Money | null | undefined, threshold: string): boolean {
  if (!amount) return false;
  // String-safe comparison using parseFloat — amounts are well-formed decimals from backend
  const amountNum = parseFloat(String(amount));
  const thresholdNum = parseFloat(threshold);
  if (isNaN(amountNum) || isNaN(thresholdNum)) return false;
  return amountNum > thresholdNum;
}

export function ApprovalFlow({
  amount,
  threshold,
  approvers = [],
  onSubmitForApproval,
  onConfirm,
  confirmLabel = "Confirm and Execute",
  status = "not_required",
  rejectionReason,
  summaryLabel,
  disabled = false,
  className,
}: ApprovalFlowProps) {
  const requiresApproval = exceedsThreshold(amount, threshold);
  const [selectedApprover, setSelectedApprover] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleConfirm = async () => {
    setIsSubmitting(true);
    try {
      await onConfirm?.();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitForApproval = async () => {
    if (!selectedApprover) return;
    setIsSubmitting(true);
    try {
      await onSubmitForApproval?.(selectedApprover, notes);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Approval already in flight
  if (status === "pending") {
    return (
      <div className={cn("rounded-lg border border-ifx-warning/30 bg-ifx-warning/5 p-5", className)}>
        <div className="flex items-center gap-3 mb-2">
          <Clock className="w-5 h-5 text-ifx-warning" />
          <span className="font-semibold text-ifx-warning">Pending Approval</span>
        </div>
        <p className="text-sm text-slate-400">
          This operation is awaiting approval from a second authorized user.
          You will be notified when a decision is made.
        </p>
        {amount && (
          <div className="mt-3">
            <DollarDisplay amount={amount} size="lg" showVerbal />
          </div>
        )}
      </div>
    );
  }

  if (status === "rejected") {
    return (
      <div className={cn("rounded-lg border border-ifx-error/30 bg-ifx-error/5 p-5", className)}>
        <div className="flex items-center gap-3 mb-2">
          <AlertTriangle className="w-5 h-5 text-ifx-error" />
          <span className="font-semibold text-red-400">Rejected</span>
        </div>
        {rejectionReason && (
          <p className="text-sm text-slate-400 mb-3">Reason: {rejectionReason}</p>
        )}
        <p className="text-sm text-slate-500">
          You may modify the submission and resubmit for approval.
        </p>
      </div>
    );
  }

  if (status === "approved") {
    return (
      <div className={cn("rounded-lg border border-ifx-success/30 bg-ifx-success/5 p-5", className)}>
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-ifx-success" />
          <span className="font-semibold text-green-400">Approved</span>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Dollar amount confirmation */}
      {amount && (
        <div className="rounded-lg border border-ifx-border-dark bg-navy-900/40 p-5">
          {summaryLabel && (
            <p className="text-sm text-slate-400 mb-2">{summaryLabel}</p>
          )}
          <DollarDisplay amount={amount} size="xl" showVerbal />
        </div>
      )}

      {requiresApproval ? (
        <div className="rounded-lg border border-ifx-warning/30 bg-ifx-warning/5 p-5 space-y-4">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-ifx-warning mt-0.5 shrink-0" />
            <div>
              <p className="font-semibold text-ifx-warning text-sm">
                Two-person approval required
              </p>
              <p className="text-sm text-slate-400 mt-1">
                This operation exceeds {formatDollars(threshold)} and requires
                approval from a second authorized user.
              </p>
            </div>
          </div>

          {approvers.length > 0 && (
            <div className="space-y-2">
              <label className="block text-sm font-medium text-slate-300">
                Select approver
              </label>
              <select
                value={selectedApprover}
                onChange={(e) => setSelectedApprover(e.target.value)}
                className="w-full px-3 py-2 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white focus:outline-none focus:ring-2 focus:ring-teal-500/40"
                aria-label="Select approver"
              >
                <option value="">Choose an approver…</option>
                {approvers.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.role})
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="space-y-2">
            <label className="block text-sm font-medium text-slate-300">
              Notes for approver{" "}
              <span className="text-slate-500 font-normal">(optional)</span>
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Add context for the approver…"
              className="w-full px-3 py-2 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-teal-500/40 resize-none"
            />
          </div>

          <button
            onClick={handleSubmitForApproval}
            disabled={disabled || isSubmitting || (approvers.length > 0 && !selectedApprover)}
            className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-md bg-ifx-warning text-navy-900 hover:bg-yellow-400 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <UserCheck className="w-4 h-4" />
            {isSubmitting ? "Submitting…" : "Submit for Approval"}
          </button>
        </div>
      ) : (
        <button
          onClick={handleConfirm}
          disabled={disabled || isSubmitting}
          className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-md bg-teal-500 text-white hover:bg-teal-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ShieldCheck className="w-4 h-4" />
          {isSubmitting ? "Processing…" : confirmLabel}
        </button>
      )}
    </div>
  );
}
