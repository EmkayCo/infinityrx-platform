"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import * as Tabs from "@radix-ui/react-tabs";
import {
  ArrowLeft, CheckCircle2, DollarSign, FileText, Loader2, Mail,
  Receipt, RefreshCw, XCircle,
} from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  getInvoice, listInvoiceLines, listInvoiceAttachments,
  listInvoiceEmailDeliveries, listInvoiceAudit, listEmailRecipients,
  finalizeInvoice, markInvoicePaid, voidInvoice,
  type Invoice, type InvoiceLine, type InvoiceAttachment,
  type EmailDelivery, type InvoiceAuditEntry, type EmailRecipient,
} from "@shared/lib/paysync-api";

import { InvoiceStatusBadge } from "@/components/paysync/cycle-status-badge";
import { StateMachineDiagram } from "@/components/paysync/state-machine-diagram";
import { AuditLogTimeline } from "@/components/paysync/audit-log-timeline";
import { EmailComposer } from "@/components/paysync/email-composer";
import { DestructiveActionDialog } from "@/components/paysync/destructive-action-dialog";
import { FileDownloadButton } from "@/components/paysync/file-download-button";

interface PageParams { invoiceId: string; }

const INVOICE_NODES = [
  { id: "draft", label: "Draft" },
  { id: "finalized", label: "Finalized" },
  { id: "sent", label: "Sent" },
  { id: "paid", label: "Paid" },
  { id: "reconciled", label: "Reconciled" },
];

export default function InvoiceDetailPage(
  { params }: { params: Promise<PageParams> },
) {
  const { invoiceId } = use(params);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [recipients, setRecipients] = useState<EmailRecipient[]>([]);
  const [loading, setLoading] = useState(true);

  const [emailOpen, setEmailOpen] = useState(false);
  const [paidOpen, setPaidOpen] = useState(false);
  const [voidOpen, setVoidOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  const [paidAmount, setPaidAmount] = useState("");
  const [paidRef, setPaidRef] = useState("");
  const [voidReason, setVoidReason] = useState("");
  const [voidForcePaid, setVoidForcePaid] = useState(false);

  function refresh() {
    getInvoice(invoiceId).then((inv) => {
      setInvoice(inv);
      return listEmailRecipients(inv.bill_to_id);
    }).then(setRecipients)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load invoice — ${msg}`);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => { refresh(); }, [invoiceId]);

  async function handleFinalize() {
    setBusy("finalize");
    try {
      const updated = await finalizeInvoice(invoiceId);
      setInvoice(updated);
      toast.success("Invoice finalized.");
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Finalize failed — ${msg}`);
    } finally { setBusy(null); }
  }

  async function handleMarkPaid() {
    if (!paidAmount.trim()) return;
    setBusy("paid");
    try {
      const updated = await markInvoicePaid(invoiceId, {
        paid_amount: paidAmount,
        reference: paidRef || undefined,
      });
      setInvoice(updated);
      toast.success(`Invoice marked ${updated.status}.`);
      setPaidOpen(false);
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Mark paid failed — ${msg}`);
    } finally { setBusy(null); }
  }

  async function handleVoid() {
    if (!voidReason.trim()) return;
    setBusy("void");
    try {
      const updated = await voidInvoice(invoiceId, {
        reason: voidReason,
        force_paid_void: voidForcePaid,
      });
      setInvoice(updated);
      toast.success("Invoice voided.");
      setVoidOpen(false);
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Void failed — ${msg}`);
    } finally { setBusy(null); }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading invoice…
      </div>
    );
  }
  if (!invoice) {
    return (
      <div className="p-6">
        <p className="text-rose-500">Invoice not found.</p>
        <Link href="/admin/paysync/invoices" className="text-sky-500 hover:underline">
          ← Back to invoices
        </Link>
      </div>
    );
  }

  const canFinalize = invoice.status === "draft";
  const canSend = invoice.status === "finalized" || invoice.status === "sent";
  const canPay = ["finalized", "sent", "partial"].includes(invoice.status);
  const canVoid = invoice.status !== "voided";

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/admin/paysync/invoices" className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-3.5 w-3.5" /> Invoices
        </Link>
        <span>/</span>
        <span className="font-mono text-foreground">{invoice.invoice_number}</span>
      </div>

      <header className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-sky-500/10 p-2">
            <Receipt className="h-5 w-5 text-sky-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{invoice.invoice_number}</h1>
            <p className="text-sm text-muted-foreground">
              {invoice.sequence_type === "reimbursement" ? "Reimbursement" : "Client fees"}{" "}
              · {invoice.bill_to_name} · cycle{" "}
              <Link href={`/admin/paysync/cycles/${invoice.cycle_id}`}
                    className="font-mono text-sky-500 hover:underline">
                {invoice.cycle_label}
              </Link>
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <InvoiceStatusBadge status={invoice.status} />
          {canFinalize && (
            <button onClick={handleFinalize} disabled={busy === "finalize"}
                    className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50">
              {busy === "finalize" ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                   : <CheckCircle2 className="h-3.5 w-3.5" />}
              Finalize
            </button>
          )}
          {canSend && (
            <button onClick={() => setEmailOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-md bg-sky-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-600">
              <Mail className="h-3.5 w-3.5" />
              {invoice.sent_at ? "Resend" : "Send"}
            </button>
          )}
          {canPay && (
            <button onClick={() => {
              setPaidAmount(invoice.total_amount); setPaidOpen(true);
            }}
                    className="inline-flex items-center gap-1.5 rounded-md border bg-background px-3 py-1.5 text-sm hover:bg-muted">
              <DollarSign className="h-3.5 w-3.5" /> Mark paid
            </button>
          )}
          {canVoid && (
            <button onClick={() => setVoidOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/50 bg-background px-3 py-1.5 text-sm text-rose-600 hover:bg-rose-500/5">
              <XCircle className="h-3.5 w-3.5" /> Void
            </button>
          )}
          <button onClick={refresh}
                  className="rounded-md border bg-background p-2 hover:bg-muted"
                  aria-label="Refresh">
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>
      </header>

      <div className="mb-6 grid gap-3 md:grid-cols-4">
        <Kpi label="Total" value={`$${invoice.total_amount}`} />
        <Kpi label="Paid" value={`$${invoice.paid_amount}`} />
        <Kpi label="Invoice date" value={invoice.invoice_date} />
        <Kpi label="Due date" value={invoice.due_date ?? "—"} />
      </div>

      <Tabs.Root defaultValue="overview">
        <Tabs.List className="flex flex-wrap gap-1 border-b">
          {[
            ["overview", "Overview"], ["lines", "Lines"],
            ["attachments", "Attachments"], ["email", "Email history"],
            ["audit", "Audit log"],
          ].map(([v, l]) => (
            <Tabs.Trigger key={v} value={v}
                          className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-sky-500 data-[state=active]:text-foreground">
              {l}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="overview" className="pt-6">
          <section className="rounded-lg border bg-card p-4">
            <h2 className="mb-3 text-sm font-semibold">State machine</h2>
            <StateMachineDiagram nodes={INVOICE_NODES} current={invoice.status} />
            <p className="mt-3 text-xs text-muted-foreground">
              Voided / partial branches are sidecar states. Voiding a paid
              invoice requires <span className="font-mono">force_paid_void=true</span>.
            </p>
          </section>
        </Tabs.Content>

        <Tabs.Content value="lines" className="pt-6">
          <LinesTab invoiceId={invoiceId} />
        </Tabs.Content>

        <Tabs.Content value="attachments" className="pt-6">
          <AttachmentsTab invoiceId={invoiceId} />
        </Tabs.Content>

        <Tabs.Content value="email" className="pt-6">
          <EmailHistoryTab invoiceId={invoiceId} />
        </Tabs.Content>

        <Tabs.Content value="audit" className="pt-6">
          <AuditTab invoiceId={invoiceId} />
        </Tabs.Content>
      </Tabs.Root>

      <EmailComposer
        open={emailOpen} onOpenChange={setEmailOpen}
        invoiceId={invoice.id} invoiceNumber={invoice.invoice_number}
        defaultRecipients={recipients}
        isResend={!!invoice.sent_at}
        onSent={refresh}
      />

      <MarkPaidDialog
        open={paidOpen} onOpenChange={setPaidOpen}
        invoice={invoice}
        amount={paidAmount} onAmountChange={setPaidAmount}
        reference={paidRef} onReferenceChange={setPaidRef}
        onConfirm={handleMarkPaid}
        loading={busy === "paid"}
      />

      <DestructiveActionDialog
        open={voidOpen} onOpenChange={setVoidOpen}
        title="Void invoice"
        description={
          <div className="space-y-2">
            <p>
              Voiding invoice <span className="font-mono">{invoice.invoice_number}</span>{" "}
              is logged but irreversible. Any sent emails remain in delivery
              logs; recipients should be notified separately.
            </p>
            {invoice.status === "paid" && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={voidForcePaid}
                       onChange={(e) => setVoidForcePaid(e.target.checked)} />
                <span>Force-void this paid invoice</span>
              </label>
            )}
          </div>
        }
        actionLabel="Void invoice"
        onConfirm={handleVoid}
        loading={busy === "void"}
        confirmationText={invoice.invoice_number}
        reasonRequired
        onReasonChange={setVoidReason}
      />
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-lg font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function LinesTab({ invoiceId }: { invoiceId: string }) {
  const [rows, setRows] = useState<InvoiceLine[]>([]);
  useEffect(() => {
    listInvoiceLines(invoiceId).then(setRows).catch(() => { /* toast in client */ });
  }, [invoiceId]);
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">No lines.</p>;
  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left">#</th>
            <th className="px-3 py-2 text-left">Type</th>
            <th className="px-3 py-2 text-left">Description</th>
            <th className="px-3 py-2 text-right">Qty</th>
            <th className="px-3 py-2 text-right">Unit</th>
            <th className="px-3 py-2 text-right">Line total</th>
            <th className="px-3 py-2 text-left">GL</th>
            <th className="px-3 py-2 text-left">Source claim</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((l) => (
            <tr key={l.id}>
              <td className="px-3 py-1.5 font-mono text-xs">{l.line_number}</td>
              <td className="px-3 py-1.5 text-xs">{l.line_type}</td>
              <td className="px-3 py-1.5">{l.description}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">{l.quantity}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">${l.unit_amount}</td>
              <td className="px-3 py-1.5 text-right tabular-nums font-medium">${l.line_amount}</td>
              <td className="px-3 py-1.5 font-mono text-xs">{l.gl_account ?? "—"}</td>
              <td className="px-3 py-1.5 font-mono text-xs">
                {l.source_claim_id?.slice(0, 8) ?? "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AttachmentsTab({ invoiceId }: { invoiceId: string }) {
  const [rows, setRows] = useState<InvoiceAttachment[]>([]);
  useEffect(() => {
    listInvoiceAttachments(invoiceId).then(setRows).catch(() => {});
  }, [invoiceId]);
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">No attachments yet.</p>;
  return (
    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
      {rows.map((a) => (
        <div key={a.id} className="rounded-md border bg-card p-3">
          <p className="text-xs font-medium">{a.attachment_type}</p>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {a.file_path.split("/").pop()}
          </p>
          <div className="mt-2">
            <FileDownloadButton
              fileId={a.id}
              fileLabel="Download"
              sha256={a.sha256}
              sizeBytes={a.size_bytes}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function EmailHistoryTab({ invoiceId }: { invoiceId: string }) {
  const [rows, setRows] = useState<EmailDelivery[]>([]);
  useEffect(() => {
    listInvoiceEmailDeliveries(invoiceId).then(setRows).catch(() => {});
  }, [invoiceId]);
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">No emails sent.</p>;
  return (
    <div className="space-y-3">
      {rows.map((d) => (
        <div key={d.id} className="rounded-md border bg-card p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium">{d.subject}</p>
              <p className="text-xs text-muted-foreground">
                {d.sent_at ? new Date(d.sent_at).toLocaleString() : "pending"}
                {" · "}
                {d.to_addresses.join(", ")}
                {d.cc_addresses.length > 0 && ` · cc: ${d.cc_addresses.join(", ")}`}
              </p>
            </div>
            <span className={
              "rounded-full px-2 py-0.5 text-[11px] font-medium " + (
                d.status === "sent" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" :
                d.status === "failed" ? "bg-rose-500/10 text-rose-700 dark:text-rose-300" :
                "bg-amber-500/10 text-amber-700 dark:text-amber-300"
              )
            }>
              {d.status}
            </span>
          </div>
          {d.failure_reason && (
            <p className="mt-2 text-xs text-rose-500">{d.failure_reason}</p>
          )}
        </div>
      ))}
    </div>
  );
}

function AuditTab({ invoiceId }: { invoiceId: string }) {
  const [entries, setEntries] = useState<InvoiceAuditEntry[]>([]);
  useEffect(() => {
    listInvoiceAudit(invoiceId).then(setEntries).catch(() => {});
  }, [invoiceId]);
  return <AuditLogTimeline entries={entries} />;
}

// ── Mark Paid dialog ─────────────────────────────────────────

function MarkPaidDialog({
  open, onOpenChange, invoice, amount, onAmountChange,
  reference, onReferenceChange, onConfirm, loading,
}: {
  open: boolean;
  onOpenChange: (b: boolean) => void;
  invoice: Invoice;
  amount: string;
  onAmountChange: (s: string) => void;
  reference: string;
  onReferenceChange: (s: string) => void;
  onConfirm: () => void;
  loading: boolean;
}) {
  if (!open) return null;
  // Inline modal pattern (Radix Dialog used inline for brevity).
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
         onClick={() => onOpenChange(false)}>
      <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-3 text-base font-semibold">Mark invoice paid</h3>
        <p className="mb-4 text-sm text-muted-foreground">
          {invoice.invoice_number} — total ${invoice.total_amount}.
        </p>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Paid amount</span>
          <input type="text" value={amount}
                 onChange={(e) => onAmountChange(e.target.value)}
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          <span className="text-[11px] text-muted-foreground">
            Less than total marks invoice as <span className="font-mono">partial</span>.
          </span>
        </label>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Reference (optional)</span>
          <input type="text" value={reference}
                 onChange={(e) => onReferenceChange(e.target.value)}
                 placeholder="check #, ACH trace, wire ref"
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
        </label>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={() => onOpenChange(false)} disabled={loading}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
            Cancel
          </button>
          <button onClick={onConfirm} disabled={loading || !amount.trim()}
                  className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50">
            {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Mark paid
          </button>
        </div>
      </div>
    </div>
  );
}
