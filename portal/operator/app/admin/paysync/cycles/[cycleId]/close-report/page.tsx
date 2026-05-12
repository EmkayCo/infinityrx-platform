"use client";

// Cycle close report — Wave 40 M1.
//
// Renders the M7 cycle close report from Wave 39 in HTML form,
// with format toggles for JSON download and PDF (server-rendered
// via the report endpoint).

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, FileJson, FileText, Loader2 } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import { apiGet } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import {
  getCycle, listReconciliations, listBatches, listInvoices,
  type Cycle, type CycleReconciliation, type PaymentBatch,
  type Invoice,
} from "@shared/lib/paysync-api";

import { CycleStatusBadge, BatchStatusBadge, InvoiceStatusBadge } from "@/components/paysync/cycle-status-badge";
import { DeltaDisplay } from "@/components/paysync/delta-display";

interface PageParams { cycleId: string; }

const REPORT_BASE = `${API_URLS.adjudicationEngine}/admin/paysync/cycles`;

export default function CloseReportPage(
  { params }: { params: Promise<PageParams> },
) {
  const { cycleId } = use(params);
  const [cycle, setCycle] = useState<Cycle | null>(null);
  const [latestRecon, setLatestRecon] = useState<CycleReconciliation | null>(null);
  const [batches, setBatches] = useState<PaymentBatch[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getCycle(cycleId),
      listReconciliations(cycleId),
      listBatches({ cycle_id: cycleId, page: 1, page_size: 50 }),
      listInvoices({ cycle_id: cycleId, page: 1, page_size: 50 }),
    ]).then(([c, recons, b, inv]) => {
      if (cancelled) return;
      setCycle(c);
      setLatestRecon(recons[0] ?? null);
      setBatches(b.items);
      setInvoices(inv.items);
    }).catch((e: unknown) => {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Failed to load close report — ${msg}`);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [cycleId]);

  async function handleDownloadJson() {
    try {
      const json = await apiGet<unknown>(`${REPORT_BASE}/${cycleId}/close-report`);
      const blob = new Blob([JSON.stringify(json, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `cycle-close-report-${cycleId}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`JSON download failed — ${msg}`);
    }
  }

  function handleDownloadPdf() {
    window.location.href = `${REPORT_BASE}/${cycleId}/close-report.pdf`;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading…
      </div>
    );
  }
  if (!cycle) {
    return (
      <div className="p-6">
        <p className="text-rose-500">Cycle not found.</p>
        <Link href="/admin/paysync/cycles" className="text-sky-500 hover:underline">
          ← Back to cycles
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-[1100px] p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href={`/admin/paysync/cycles/${cycleId}`}
              className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-3.5 w-3.5" /> Cycle
        </Link>
        <span>/</span>
        <span className="text-foreground">Close report</span>
      </div>

      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Close report — {cycle.cycle_label}</h1>
          <p className="text-sm text-muted-foreground">
            <CycleStatusBadge status={cycle.status} />
            <span className="ml-2">{cycle.period_start} → {cycle.period_end}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleDownloadJson}
                  className="inline-flex items-center gap-1.5 rounded-md border bg-background px-3 py-1.5 text-sm hover:bg-muted">
            <FileJson className="h-3.5 w-3.5" /> JSON
          </button>
          <button onClick={handleDownloadPdf}
                  className="inline-flex items-center gap-1.5 rounded-md border bg-background px-3 py-1.5 text-sm hover:bg-muted">
            <FileText className="h-3.5 w-3.5" /> PDF
          </button>
        </div>
      </header>

      <section className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Kpi label="Claims" value={cycle.claim_count.toLocaleString()} />
        <Kpi label="Total billed" value={`$${cycle.total_billed}`} />
        <Kpi label="Total pay" value={`$${cycle.total_pay}`} />
        <Kpi label="Closed at" value={cycle.closed_at ? new Date(cycle.closed_at).toLocaleString() : "—"} />
      </section>

      {latestRecon && (
        <section className="mb-6">
          <h2 className="mb-3 text-sm font-semibold">Three-way reconciliation</h2>
          <div className="grid gap-3 md:grid-cols-3">
            <DeltaDisplay label="Tie 1: Claims ↔ Invoice" tie={latestRecon.tie_1} />
            <DeltaDisplay label="Tie 2: Claims ↔ Total AP" tie={latestRecon.tie_2} />
            <DeltaDisplay label="Tie 3: Batch AP ↔ NACHA ↔ 835" tie={latestRecon.tie_3} />
          </div>
          {latestRecon.finalized && (
            <p className="mt-2 text-xs text-muted-foreground">
              Finalized {latestRecon.finalized_at && new Date(latestRecon.finalized_at).toLocaleString()}
              {latestRecon.finalized_by && ` by ${latestRecon.finalized_by}`}
              {latestRecon.accepted_deltas && " (with accepted deltas)"}
            </p>
          )}
        </section>
      )}

      <section className="mb-6">
        <h2 className="mb-3 text-sm font-semibold">Batches ({batches.length})</h2>
        {batches.length === 0
          ? <p className="text-sm text-muted-foreground">None.</p>
          : (
            <div className="rounded-lg border bg-card">
              <table className="w-full text-sm">
                <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 text-left">Batch #</th>
                    <th className="px-3 py-2 text-left">Effective entry</th>
                    <th className="px-3 py-2 text-right">Total</th>
                    <th className="px-3 py-2 text-right">Credits</th>
                    <th className="px-3 py-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {batches.map((b) => (
                    <tr key={b.id}>
                      <td className="px-3 py-1.5 font-mono text-xs">
                        <Link href={`/admin/paysync/batches/${b.id}`} className="text-sky-500 hover:underline">
                          {b.batch_number}
                        </Link>
                      </td>
                      <td className="px-3 py-1.5 font-mono text-xs">{b.effective_entry_date}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">${b.total_credit_amount}</td>
                      <td className="px-3 py-1.5 text-right">{b.credit_entry_count}</td>
                      <td className="px-3 py-1.5"><BatchStatusBadge status={b.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold">Invoices ({invoices.length})</h2>
        {invoices.length === 0
          ? <p className="text-sm text-muted-foreground">None.</p>
          : (
            <div className="rounded-lg border bg-card">
              <table className="w-full text-sm">
                <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2 text-left">Invoice #</th>
                    <th className="px-3 py-2 text-left">Type</th>
                    <th className="px-3 py-2 text-left">Bill to</th>
                    <th className="px-3 py-2 text-right">Total</th>
                    <th className="px-3 py-2 text-left">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {invoices.map((i) => (
                    <tr key={i.id}>
                      <td className="px-3 py-1.5 font-mono text-xs">
                        <Link href={`/admin/paysync/invoices/${i.id}`} className="text-sky-500 hover:underline">
                          {i.invoice_number}
                        </Link>
                      </td>
                      <td className="px-3 py-1.5 text-xs">{i.sequence_type}</td>
                      <td className="px-3 py-1.5 text-xs">{i.bill_to_name}</td>
                      <td className="px-3 py-1.5 text-right tabular-nums">${i.total_amount}</td>
                      <td className="px-3 py-1.5"><InvoiceStatusBadge status={i.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </section>
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
