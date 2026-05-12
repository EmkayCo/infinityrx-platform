"use client";

// Destructive-action confirmation dialog.
//
// Tier 1: low-risk destructive ops use a plain confirm with one
// button. Tier 2: high-risk (irreversible) ops require typing the
// confirmation text exactly before the action button enables.

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { AlertTriangle, Loader2, X } from "lucide-react";
import { cn } from "@shared/lib/format";

export interface DestructiveActionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: React.ReactNode;
  actionLabel: string;
  onConfirm: () => void | Promise<void>;
  loading?: boolean;
  // Tier 2 — set to require operator to type this string before
  // confirm enables. e.g. cycle_label, batch_number.
  confirmationText?: string;
  reasonRequired?: boolean;
  reasonLabel?: string;
  onReasonChange?: (reason: string) => void;
}

export function DestructiveActionDialog({
  open, onOpenChange, title, description,
  actionLabel, onConfirm, loading,
  confirmationText, reasonRequired, reasonLabel = "Reason",
  onReasonChange,
}: DestructiveActionDialogProps) {
  const [typed, setTyped] = useState("");
  const [reason, setReason] = useState("");

  const tier2 = !!confirmationText;
  const matched = !tier2 || typed === confirmationText;
  const reasonOk = !reasonRequired || reason.trim().length > 0;
  const canConfirm = !loading && matched && reasonOk;

  const handleReason = (value: string) => {
    setReason(value);
    onReasonChange?.(value);
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-background/80 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-card p-6 shadow-lg">
          <div className="mb-4 flex items-start gap-3">
            <div className="rounded-md bg-rose-500/10 p-2">
              <AlertTriangle className="h-5 w-5 text-rose-500" />
            </div>
            <div className="flex-1">
              <Dialog.Title className="text-base font-semibold">
                {title}
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-muted-foreground">
                {description}
              </Dialog.Description>
            </div>
            <Dialog.Close
              className="text-muted-foreground hover:text-foreground"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          {tier2 && (
            <label className="mb-3 block text-xs">
              <span className="font-medium">
                Type <span className="font-mono">{confirmationText}</span> to confirm
              </span>
              <input
                type="text" value={typed}
                onChange={(e) => setTyped(e.target.value)}
                className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm"
                autoComplete="off"
              />
            </label>
          )}

          {reasonRequired && (
            <label className="mb-3 block text-xs">
              <span className="font-medium">{reasonLabel}</span>
              <textarea
                value={reason}
                onChange={(e) => handleReason(e.target.value)}
                rows={3}
                className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
                placeholder="Required for audit log"
              />
            </label>
          )}

          <div className="mt-4 flex justify-end gap-2">
            <button
              type="button" onClick={() => onOpenChange(false)}
              disabled={loading}
              className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button" onClick={onConfirm}
              disabled={!canConfirm}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-white",
                canConfirm ? "bg-rose-500 hover:bg-rose-600" : "bg-rose-500/40",
              )}
            >
              {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {actionLabel}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
