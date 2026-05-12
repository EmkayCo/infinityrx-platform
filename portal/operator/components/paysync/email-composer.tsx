"use client";

// Email composer modal — used for invoice send + resend.

import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Loader2, Mail, X } from "lucide-react";
import { toast } from "sonner";
import { ApiClientError } from "@shared/lib/api-client";
import { sendInvoice, type EmailRecipient } from "@shared/lib/paysync-api";

export interface EmailComposerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  invoiceId: string;
  invoiceNumber: string;
  defaultRecipients: EmailRecipient[];
  isResend: boolean;
  onSent?: () => void;
}

export function EmailComposer({
  open, onOpenChange, invoiceId, invoiceNumber,
  defaultRecipients, isResend, onSent,
}: EmailComposerProps) {
  const [overrideRecipients, setOverrideRecipients] = useState<string[]>([]);
  const [overrideSubject, setOverrideSubject] = useState("");
  const [overrideBody, setOverrideBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [draftRecipient, setDraftRecipient] = useState("");

  function addRecipient() {
    if (draftRecipient.trim()) {
      setOverrideRecipients([...overrideRecipients, draftRecipient.trim()]);
      setDraftRecipient("");
    }
  }

  async function handleSend() {
    setBusy(true);
    try {
      await sendInvoice(invoiceId, {
        override_recipients: overrideRecipients.length > 0 ? overrideRecipients : undefined,
        override_subject: overrideSubject || undefined,
        override_body: overrideBody || undefined,
        is_resend: isResend,
      });
      toast.success(`Invoice ${invoiceNumber} ${isResend ? "resent" : "sent"}.`);
      onSent?.();
      onOpenChange(false);
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Send failed — ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  const finalRecipients = overrideRecipients.length > 0
    ? overrideRecipients
    : defaultRecipients.map((r) => r.email_address);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-background/80 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-card p-6 shadow-lg">
          <div className="mb-4 flex items-start gap-3">
            <div className="rounded-md bg-sky-500/10 p-2">
              <Mail className="h-5 w-5 text-sky-500" />
            </div>
            <div className="flex-1">
              <Dialog.Title className="text-base font-semibold">
                {isResend ? "Resend invoice" : "Send invoice"}
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-muted-foreground">
                Invoice {invoiceNumber}
              </Dialog.Description>
            </div>
            <Dialog.Close className="text-muted-foreground hover:text-foreground"
                          aria-label="Close">
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          <div className="mb-3">
            <label className="block text-xs font-medium">Recipients</label>
            {overrideRecipients.length === 0 && defaultRecipients.length > 0 && (
              <p className="mt-1 text-[11px] text-muted-foreground">
                Default: {defaultRecipients.map((r) =>
                  `${r.email_address}${r.is_cc ? " (cc)" : ""}`).join(", ")}
              </p>
            )}
            <div className="mt-1 flex gap-2">
              <input type="email" value={draftRecipient}
                     onChange={(e) => setDraftRecipient(e.target.value)}
                     onKeyDown={(e) => e.key === "Enter" && addRecipient()}
                     placeholder="add override recipient"
                     className="flex-1 rounded-md border bg-background px-3 py-2 text-sm" />
              <button type="button" onClick={addRecipient}
                      className="rounded-md border px-3 text-sm hover:bg-muted">
                Add
              </button>
            </div>
            {overrideRecipients.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {overrideRecipients.map((r, i) => (
                  <span key={i}
                        className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 px-2 py-0.5 text-xs text-sky-700 dark:text-sky-300">
                    {r}
                    <button onClick={() => setOverrideRecipients(
                      overrideRecipients.filter((_, j) => j !== i))}
                            aria-label={`Remove ${r}`}>
                      <X className="h-3 w-3" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <label className="mb-3 block text-xs">
            <span className="font-medium">Subject override (optional)</span>
            <input type="text" value={overrideSubject}
                   onChange={(e) => setOverrideSubject(e.target.value)}
                   placeholder="leave blank to use template default"
                   className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
          </label>

          <label className="mb-3 block text-xs">
            <span className="font-medium">Body override (optional)</span>
            <textarea value={overrideBody}
                      onChange={(e) => setOverrideBody(e.target.value)}
                      rows={4}
                      placeholder="leave blank to use template default"
                      className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
          </label>

          <div className="mt-4 flex justify-end gap-2">
            <button type="button" onClick={() => onOpenChange(false)}
                    disabled={busy}
                    className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
              Cancel
            </button>
            <button type="button" onClick={handleSend}
                    disabled={busy || finalRecipients.length === 0}
                    className="inline-flex items-center gap-1.5 rounded-md bg-sky-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-50">
              {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {isResend ? "Resend" : "Send"} to {finalRecipients.length} recipient(s)
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
