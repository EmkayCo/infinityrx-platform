"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import * as Tabs from "@radix-ui/react-tabs";
import {
  ArrowLeft, CheckCircle2, FileDown, Loader2, Wallet, XCircle,
} from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  getBatch, listBatchCredits, listBatchAudit,
  approveBatch, voidBatch, generateNacha, generate835,
  type PaymentBatch, type BatchCredit, type BatchAuditEntry,
} from "@shared/lib/paysync-api";

import { BatchStatusBadge } from "@/components/paysync/cycle-status-badge";
import { StateMachineDiagram } from "@/components/paysync/state-machine-diagram";
import { AuditLogTimeline } from "@/components/paysync/audit-log-timeline";
import { DestructiveActionDialog } from "@/components/paysync/destructive-action-dialog";

interface PageParams { batchId: string; }

const BATCH_NODES = [
  { id: "draft", label: "Draft" },
  { id: "pending_approval", label: "Pending approval" },
  { id: "approved", label: "Approved" },
  { id: "submitted", label: "Submitted" },
  { id: "settled", label: "Settled" },
  { id: "reconciled", label: "Reconciled" },
];

export default function BatchDetailPage(
  { params }: { params: Promise<PageParams> },
) {
  const { batchId } = use(params);
  const [batch, setBatch] = useState<PaymentBatch | null>(null);
  const [loading, setLoading] = useState(true);
  const [voidOpen, setVoidOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [voidReason, setVoidReason] = useState("");

  function refresh() {
    getBatch(batchId)
      .then(setBatch)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load batch — ${msg}`);
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => { refresh(); }, [batchId]);

  async function handleApprove() {
    setBusy("approve");
    try {
      const updated = await approveBatch(batchId);
      setBatch(updated);
      toast.success("Batch approved.");
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Approve failed — ${msg}`);
    } finally { setBusy(null); }
  }

  async function handleGenerateNacha() {
    setBusy("nacha");
    try {
      const res = await generateNacha(batchId);
      toast.success(`NACHA generated (${res.trace_count} traces, sha ${res.sha256.slice(0, 8)})`);
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`NACHA generation failed — ${msg}`);
    } finally { setBusy(null); }
  }

  async function handleGenerate835s() {
    setBusy("835");
    try {
      const res = await generate835(batchId);
      toast.success(`${res.files.length} 835 file(s) generated.`);
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`835 generation failed — ${msg}`);
    } finally { setBusy(null); }
  }

  async function handleVoid() {
    if (!voidReason.trim()) return;
    setBusy("void");
    try {
      const updated = await voidBatch(batchId, voidReason);
      setBatch(updated);
      toast.success("Batch voided.");
      setVoidOpen(false);
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Void failed — ${msg}`);
    } finally { setBusy(null); }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading batch…
      </div>
    );
  }
  if (!batch) {
    return (
      <div className="p-6">
        <p className="text-rose-500">Batch not found.</p>
        <Link href="/admin/paysync/batches" className="text-sky-500 hover:underline">
          ← Back to batches
        </Link>
      </div>
    );
  }

  const canApprove = batch.status === "draft" || batch.status === "pending_approval";
  const canNacha = batch.status === "approved" || batch.status === "draft";
  const can835 = ["approved", "submitted", "settled"].includes(batch.status);
  const canVoid = !["voided", "settled", "reconciled"].includes(batch.status);

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/admin/paysync/batches" className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-3.5 w-3.5" /> Batches
        </Link>
        <span>/</span>
        <span className="font-mono text-foreground">#{batch.batch_number}</span>
      </div>

      <header className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-emerald-500/10 p-2">
            <Wallet className="h-5 w-5 text-emerald-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Batch #{batch.batch_number}</h1>
            <p className="text-sm text-muted-foreground">
              Cycle{" "}
              <Link href={`/admin/paysync/cycles/${batch.cycle_id}`}
                    className="font-mono text-sky-500 hover:underline">
                {batch.cycle_label}
              </Link>{" "}
              · effective entry {batch.effective_entry_date}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <BatchStatusBadge status={batch.status} />
          {canApprove && (
            <button onClick={handleApprove} disabled={busy === "approve"}
                    className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50">
              {busy === "approve" ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                  : <CheckCircle2 className="h-3.5 w-3.5" />}
              Approve
            </button>
          )}
          {canNacha && (
            <button onClick={handleGenerateNacha} disabled={busy === "nacha"}
                    className="inline-flex items-center gap-1.5 rounded-md bg-amber-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50">
              {busy === "nacha" ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <FileDown className="h-3.5 w-3.5" />}
              Generate NACHA
            </button>
          )}
          {can835 && (
            <button onClick={handleGenerate835s} disabled={busy === "835"}
                    className="inline-flex items-center gap-1.5 rounded-md border bg-background px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
              {busy === "835" ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              : <FileDown className="h-3.5 w-3.5" />}
              Generate 835s
            </button>
          )}
          {canVoid && (
            <button onClick={() => setVoidOpen(true)}
                    className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/50 bg-background px-3 py-1.5 text-sm text-rose-600 hover:bg-rose-500/5">
              <XCircle className="h-3.5 w-3.5" /> Void
            </button>
          )}
        </div>
      </header>

      <div className="mb-6 grid gap-3 md:grid-cols-4">
        <Kpi label="Total credit" value={`$${batch.total_credit_amount}`} />
        <Kpi label="Credits" value={batch.credit_entry_count.toLocaleString()} />
        <Kpi label="Claims" value={batch.claim_count.toLocaleString()} />
        <Kpi label="Entry class" value={batch.entry_class_code ?? "mixed"} />
      </div>

      <Tabs.Root defaultValue="overview">
        <Tabs.List className="flex flex-wrap gap-1 border-b">
          {[
            ["overview", "Overview"], ["credits", "Credits"],
            ["audit", "Audit log"],
          ].map(([v, l]) => (
            <Tabs.Trigger key={v} value={v}
                          className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-emerald-500 data-[state=active]:text-foreground">
              {l}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="overview" className="pt-6">
          <section className="rounded-lg border bg-card p-4">
            <h2 className="mb-3 text-sm font-semibold">State machine</h2>
            <StateMachineDiagram nodes={BATCH_NODES} current={batch.status} />
            <p className="mt-3 text-xs text-muted-foreground">
              Voided / failed are terminal sidecar states; not shown.
            </p>
          </section>
        </Tabs.Content>

        <Tabs.Content value="credits" className="pt-6">
          <CreditsTab batchId={batchId} />
        </Tabs.Content>

        <Tabs.Content value="audit" className="pt-6">
          <AuditTab batchId={batchId} />
        </Tabs.Content>
      </Tabs.Root>

      <DestructiveActionDialog
        open={voidOpen}
        onOpenChange={setVoidOpen}
        title="Void batch"
        description={
          <>
            Voiding batch <span className="font-mono">#{batch.batch_number}</span>{" "}
            stops further processing. Files already generated remain on disk
            but will not be transmitted. This action is logged.
          </>
        }
        actionLabel="Void batch"
        onConfirm={handleVoid}
        loading={busy === "void"}
        confirmationText={String(batch.batch_number)}
        reasonRequired
        reasonLabel="Reason (audit log)"
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

function CreditsTab({ batchId }: { batchId: string }) {
  const [rows, setRows] = useState<BatchCredit[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listBatchCredits(batchId)
      .then(setRows)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load credits — ${msg}`);
      })
      .finally(() => setLoading(false));
  }, [batchId]);

  if (loading) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">No credits.</p>;

  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left">Pay-to</th>
            <th className="px-3 py-2 text-left">Type</th>
            <th className="px-3 py-2 text-right">Credit</th>
            <th className="px-3 py-2 text-right">Claims</th>
            <th className="px-3 py-2 text-left">Banking</th>
            <th className="px-3 py-2 text-left">Trace</th>
            <th className="px-3 py-2 text-left">Class</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="px-3 py-1.5">
                <Link href={`/admin/network/pay-to-entities/${r.pay_to_entity_id}`}
                      className="text-sky-500 hover:underline">
                  {r.pay_to_name}
                </Link>
                <span className="ml-2 font-mono text-xs text-muted-foreground">
                  {r.pay_to_external_id}
                </span>
              </td>
              <td className="px-3 py-1.5 text-xs">{r.pay_to_type}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">${r.credit_amount}</td>
              <td className="px-3 py-1.5 text-right">{r.claim_count}</td>
              <td className="px-3 py-1.5 font-mono text-xs">
                {r.banking_routing && `${r.banking_routing.slice(0, 5)}… / ****${r.banking_account_last_four}`}
              </td>
              <td className="px-3 py-1.5 font-mono text-xs">{r.trace_number ?? "—"}</td>
              <td className="px-3 py-1.5 font-mono text-xs">{r.entry_class_code}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditTab({ batchId }: { batchId: string }) {
  const [entries, setEntries] = useState<BatchAuditEntry[]>([]);
  useEffect(() => {
    listBatchAudit(batchId)
      .then(setEntries)
      .catch(() => { /* surfaced via toast in API client */ });
  }, [batchId]);
  return <AuditLogTimeline entries={entries} />;
}
