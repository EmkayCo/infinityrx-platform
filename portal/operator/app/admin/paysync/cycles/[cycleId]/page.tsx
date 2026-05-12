"use client";

// Cycle detail — Wave 40 M1.
//
// Tabbed view of one cycle covering overview, claims, holds, manual
// AP, carryovers, batches, invoices, reconciliation, and files.
// Drill-down detail tables are client-side virtualized through the
// existing ConfigurableDataTable; lists hosted under tabs.

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import * as Tabs from "@radix-ui/react-tabs";
import {
  ArrowLeft, Calendar, FileText, Loader2, PlayCircle,
  Receipt, AlertCircle, History,
} from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  getCycle, listCycleClaims, listHeldClaims, listManualAp,
  listCarryovers, listBatches, listInvoices, listReconciliations,
  listCycleFiles, autoHoldCycle, releaseHeldClaim,
  type Cycle, type PaysyncClaim, type HeldClaim,
  type ManualApRecord, type Carryover, type PaymentBatch,
  type Invoice, type CycleReconciliation, type PaysyncFile,
} from "@shared/lib/paysync-api";

import {
  CycleStatusBadge, BatchStatusBadge, InvoiceStatusBadge,
  ManualApStatusBadge,
} from "@/components/paysync/cycle-status-badge";
import { StatusTimeline, type TimelineStep } from "@/components/paysync/status-timeline";
import { DeltaDisplay } from "@/components/paysync/delta-display";
import { FileDownloadButton } from "@/components/paysync/file-download-button";

interface PageParams { cycleId: string; }

export default function CycleDetailPage(
  { params }: { params: Promise<PageParams> },
) {
  const { cycleId } = use(params);
  const [cycle, setCycle] = useState<Cycle | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getCycle(cycleId).then((c) => {
      if (!cancelled) setCycle(c);
    }).catch((e: unknown) => {
      const msg = e instanceof ApiClientError
        ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Failed to load cycle — ${msg}`);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [cycleId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading cycle…
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

  const canClose = cycle.status === "open";
  const canResume = cycle.status === "closing";

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/admin/paysync/cycles" className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-3.5 w-3.5" /> Cycles
        </Link>
        <span>/</span>
        <span className="font-mono text-foreground">{cycle.cycle_label}</span>
      </div>

      <header className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-teal-500/10 p-2">
            <Calendar className="h-5 w-5 text-teal-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">{cycle.cycle_label}</h1>
            <p className="text-sm text-muted-foreground">
              {cycle.cycle_type === "payment_cycle" ? "Payment cycle" : "Invoice cycle"}
              {" · "}
              {cycle.period_start} → {cycle.period_end}
              {cycle.schedule_name && ` · ${cycle.schedule_name}`}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <CycleStatusBadge status={cycle.status} />
          {canClose && (
            <Link
              href={`/admin/paysync/cycles/${cycle.id}/close`}
              className="inline-flex items-center gap-1.5 rounded-md bg-amber-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-600"
            >
              <PlayCircle className="h-4 w-4" /> Run cycle close
            </Link>
          )}
          {canResume && (
            <Link
              href={`/admin/paysync/cycles/${cycle.id}/close`}
              className="inline-flex items-center gap-1.5 rounded-md bg-amber-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-600"
            >
              <PlayCircle className="h-4 w-4" /> Resume close
            </Link>
          )}
          {!canClose && !canResume && (
            <Link
              href={`/admin/paysync/cycles/${cycle.id}/close-report`}
              className="inline-flex items-center gap-1.5 rounded-md border bg-background px-3 py-1.5 text-sm hover:bg-muted"
            >
              <FileText className="h-4 w-4" /> View close report
            </Link>
          )}
        </div>
      </header>

      <KpiRow cycle={cycle} />

      <Tabs.Root defaultValue="overview" className="mt-6">
        <Tabs.List className="flex flex-wrap gap-1 border-b">
          {[
            ["overview", "Overview"], ["claims", "Claims"],
            ["holds", "Holds"], ["manual-ap", "Manual AP"],
            ["carryovers", "Carryovers"], ["batches", "Batches"],
            ["invoices", "Invoices"], ["reconciliation", "Reconciliation"],
            ["files", "Files"],
          ].map(([value, label]) => (
            <Tabs.Trigger
              key={value} value={value}
              className="px-3 py-2 text-sm text-muted-foreground hover:text-foreground data-[state=active]:border-b-2 data-[state=active]:border-teal-500 data-[state=active]:text-foreground"
            >
              {label}
            </Tabs.Trigger>
          ))}
        </Tabs.List>

        <Tabs.Content value="overview" className="pt-6">
          <OverviewTab cycle={cycle} />
        </Tabs.Content>
        <Tabs.Content value="claims" className="pt-6">
          <ClaimsTab cycleId={cycle.id} />
        </Tabs.Content>
        <Tabs.Content value="holds" className="pt-6">
          <HoldsTab cycleId={cycle.id} />
        </Tabs.Content>
        <Tabs.Content value="manual-ap" className="pt-6">
          <ManualApTab cycleId={cycle.id} />
        </Tabs.Content>
        <Tabs.Content value="carryovers" className="pt-6">
          <CarryoversTab cycleId={cycle.id} />
        </Tabs.Content>
        <Tabs.Content value="batches" className="pt-6">
          <BatchesTab cycleId={cycle.id} cycleStatus={cycle.status} />
        </Tabs.Content>
        <Tabs.Content value="invoices" className="pt-6">
          <InvoicesTab cycleId={cycle.id} />
        </Tabs.Content>
        <Tabs.Content value="reconciliation" className="pt-6">
          <ReconciliationTab cycleId={cycle.id} />
        </Tabs.Content>
        <Tabs.Content value="files" className="pt-6">
          <FilesTab cycleId={cycle.id} />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  );
}

function KpiRow({ cycle }: { cycle: Cycle }) {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Kpi label="Claims" value={cycle.claim_count.toLocaleString()} />
      <Kpi label="Total billed" value={`$${Number(cycle.total_billed).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
      <Kpi label="Total pay" value={`$${Number(cycle.total_pay).toLocaleString(undefined, { minimumFractionDigits: 2 })}`} />
      <Kpi label="Reconciliation" value={cycle.reconciliation_status ?? "—"} />
    </div>
  );
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

// ─── Overview tab ──────────────────────────────────────────────

function OverviewTab({ cycle }: { cycle: Cycle }) {
  const lifecycleSteps: TimelineStep[] = [
    { id: "open", label: "Open", state: "completed", occurredAt: cycle.created_at },
    { id: "closing", label: "Closing", state:
      cycle.status === "closing" ? "current"
      : ["closed", "invoiced", "paid", "reconciled", "closed_finalized"].includes(cycle.status) ? "completed"
      : "pending" },
    { id: "closed", label: "Closed", state:
      cycle.status === "closed" ? "current"
      : ["invoiced", "paid", "reconciled", "closed_finalized"].includes(cycle.status) ? "completed"
      : "pending", occurredAt: cycle.closed_at },
    { id: "invoiced", label: "Invoiced", state:
      cycle.status === "invoiced" ? "current"
      : ["paid", "reconciled", "closed_finalized"].includes(cycle.status) ? "completed"
      : "pending" },
    { id: "paid", label: "Paid", state:
      cycle.status === "paid" ? "current"
      : ["reconciled", "closed_finalized"].includes(cycle.status) ? "completed"
      : "pending" },
    { id: "reconciled", label: "Reconciled", state:
      cycle.status === "reconciled" ? "current"
      : cycle.status === "closed_finalized" ? "completed"
      : "pending" },
  ];

  return (
    <div className="grid gap-6 md:grid-cols-2">
      <section className="rounded-lg border bg-card p-4">
        <h2 className="mb-4 text-sm font-semibold">Lifecycle</h2>
        <StatusTimeline steps={lifecycleSteps} />
      </section>
      <section className="rounded-lg border bg-card p-4">
        <h2 className="mb-4 text-sm font-semibold">Cycle metadata</h2>
        <dl className="space-y-2 text-sm">
          <Row label="Cycle ID" value={<span className="font-mono text-xs">{cycle.id}</span>} />
          <Row label="Tenant ID" value={<span className="font-mono text-xs">{cycle.tenant_id}</span>} />
          <Row label="Schedule" value={cycle.schedule_name ?? "—"} />
          <Row label="Created" value={new Date(cycle.created_at).toLocaleString()} />
          <Row label="Closed" value={cycle.closed_at ? new Date(cycle.closed_at).toLocaleString() : "—"} />
        </dl>
      </section>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

// ─── Claims tab ────────────────────────────────────────────────

function ClaimsTab({ cycleId }: { cycleId: string }) {
  const [rows, setRows] = useState<PaysyncClaim[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listCycleClaims(cycleId, { page: 1, page_size: 500 })
      .then((p) => setRows(p.items))
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load claims — ${msg}`);
      })
      .finally(() => setLoading(false));
  }, [cycleId]);

  if (loading) return <Loader />;
  if (rows.length === 0) return <Empty title="No claims in this cycle" />;

  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left">Auth</th>
            <th className="px-3 py-2 text-left">DOS</th>
            <th className="px-3 py-2 text-left">Pharmacy</th>
            <th className="px-3 py-2 text-left">NDC</th>
            <th className="px-3 py-2 text-right">Billed</th>
            <th className="px-3 py-2 text-right">Pay</th>
            <th className="px-3 py-2 text-left">Channel</th>
            <th className="px-3 py-2 text-left">Status</th>
            <th className="px-3 py-2 text-left">Flags</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="px-3 py-1.5 font-mono text-xs">{r.auth_num}</td>
              <td className="px-3 py-1.5 font-mono text-xs">{r.date_of_service}</td>
              <td className="px-3 py-1.5">
                <span className="font-mono text-xs">{r.pharmacy_npi}</span>
                {r.pharmacy_name && (
                  <span className="ml-1 text-xs text-muted-foreground">
                    {r.pharmacy_name}
                  </span>
                )}
              </td>
              <td className="px-3 py-1.5 font-mono text-xs">{r.ndc}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">${r.client_billed}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">${r.total_pay}</td>
              <td className="px-3 py-1.5 text-xs">
                {r.channel ?? "—"}
                {r.sub_channel && <span className="ml-1 text-muted-foreground">({r.sub_channel})</span>}
              </td>
              <td className="px-3 py-1.5 text-xs">{r.status}</td>
              <td className="px-3 py-1.5 text-xs">
                {[r.has_hold && "hold", r.has_manual_ap && "manualAP", r.has_carryover && "carryover", r.reversed_auth_num && "reversal"]
                  .filter(Boolean).join(" · ") || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Holds tab ─────────────────────────────────────────────────

function HoldsTab({ cycleId }: { cycleId: string }) {
  const [rows, setRows] = useState<HeldClaim[]>([]);
  const [loading, setLoading] = useState(true);

  function refresh() {
    setLoading(true);
    listHeldClaims(cycleId)
      .then(setRows)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load holds — ${msg}`);
      })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, [cycleId]);

  async function handleAutoHold() {
    try {
      const res = await autoHoldCycle(cycleId);
      toast.success(`${res.held_count} claim(s) auto-held.`);
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Auto-hold failed — ${msg}`);
    }
  }

  async function handleRelease(heldId: string) {
    const reason = prompt("Reason for release (logged):");
    if (!reason || !reason.trim()) return;
    try {
      await releaseHeldClaim(heldId, reason);
      toast.success("Claim released.");
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Release failed — ${msg}`);
    }
  }

  if (loading) return <Loader />;

  return (
    <>
      <div className="mb-3 flex justify-end">
        <button onClick={handleAutoHold}
                className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
          Run auto-hold
        </button>
      </div>
      {rows.length === 0
        ? <Empty title="No held claims" hint="Auto-hold runs detect claims with missing banking or pending discrepancies." />
        : (
          <div className="overflow-x-auto rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Claim</th>
                  <th className="px-3 py-2 text-left">Pharmacy</th>
                  <th className="px-3 py-2 text-left">Reason</th>
                  <th className="px-3 py-2 text-left">Held at</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.auth_num}</td>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.pharmacy_npi}</td>
                    <td className="px-3 py-1.5 text-xs">{r.reason}</td>
                    <td className="px-3 py-1.5 text-xs">{new Date(r.held_at).toLocaleString()}</td>
                    <td className="px-3 py-1.5 text-xs">
                      {r.released_at
                        ? <span className="text-emerald-500">released {new Date(r.released_at).toLocaleString()}</span>
                        : <span className="text-amber-500">held</span>}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      {!r.released_at && (
                        <button onClick={() => handleRelease(r.id)}
                                className="rounded-md border px-2 py-1 text-xs hover:bg-muted">
                          Release
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </>
  );
}

// ─── Manual AP tab ─────────────────────────────────────────────

function ManualApTab({ cycleId }: { cycleId: string }) {
  const [rows, setRows] = useState<ManualApRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listManualAp({ cycle_id: cycleId, page: 1, page_size: 200 })
      .then((p) => setRows(p.items))
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load manual AP — ${msg}`);
      })
      .finally(() => setLoading(false));
  }, [cycleId]);

  if (loading) return <Loader />;
  if (rows.length === 0) return <Empty title="No manual AP records linked to this cycle" />;

  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left">Channel</th>
            <th className="px-3 py-2 text-left">Payee</th>
            <th className="px-3 py-2 text-right">Amount</th>
            <th className="px-3 py-2 text-left">Reference</th>
            <th className="px-3 py-2 text-left">Status</th>
            <th className="px-3 py-2 text-left">Processed</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="px-3 py-1.5 text-xs">{r.channel}</td>
              <td className="px-3 py-1.5 text-xs">{r.payee_name}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">${r.payment_amount}</td>
              <td className="px-3 py-1.5 font-mono text-xs">{r.external_reference ?? "—"}</td>
              <td className="px-3 py-1.5"><ManualApStatusBadge status={r.status} /></td>
              <td className="px-3 py-1.5 text-xs">{r.processed_at ? new Date(r.processed_at).toLocaleString() : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Carryovers tab ────────────────────────────────────────────

function CarryoversTab({ cycleId }: { cycleId: string }) {
  const [rows, setRows] = useState<Carryover[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      listCarryovers({ origin_cycle_id: cycleId, page: 1, page_size: 200 }),
      listCarryovers({ resolution_cycle_id: cycleId, page: 1, page_size: 200 }),
    ])
      .then(([origin, resolution]) => {
        const seen = new Set<string>();
        const merged: Carryover[] = [];
        for (const c of [...origin.items, ...resolution.items]) {
          if (!seen.has(c.id)) { seen.add(c.id); merged.push(c); }
        }
        setRows(merged);
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load carryovers — ${msg}`);
      })
      .finally(() => setLoading(false));
  }, [cycleId]);

  if (loading) return <Loader />;
  if (rows.length === 0) return <Empty title="No carryovers affecting this cycle" />;

  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left">Type</th>
            <th className="px-3 py-2 text-left">Direction</th>
            <th className="px-3 py-2 text-right">Amount</th>
            <th className="px-3 py-2 text-left">Pay-to</th>
            <th className="px-3 py-2 text-left">Origin</th>
            <th className="px-3 py-2 text-left">Resolution</th>
            <th className="px-3 py-2 text-left">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="px-3 py-1.5 text-xs">{r.carryover_type}</td>
              <td className="px-3 py-1.5 text-xs">
                {r.direction === "we_owe_pharmacy" ? "We owe" : "Pharmacy owes"}
              </td>
              <td className="px-3 py-1.5 text-right tabular-nums">${r.amount}</td>
              <td className="px-3 py-1.5 font-mono text-xs">{r.pay_to_external_id ?? "—"}</td>
              <td className="px-3 py-1.5 text-xs">
                {r.origin_cycle_id === cycleId ? "this" : (r.origin_cycle_id?.slice(0, 8) ?? "—")}
              </td>
              <td className="px-3 py-1.5 text-xs">
                {r.resolution_cycle_id === cycleId ? "this" : (r.resolution_cycle_id?.slice(0, 8) ?? "—")}
              </td>
              <td className="px-3 py-1.5 text-xs">{r.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Batches tab ───────────────────────────────────────────────

function BatchesTab({ cycleId, cycleStatus }: { cycleId: string; cycleStatus: string }) {
  const [rows, setRows] = useState<PaymentBatch[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listBatches({ cycle_id: cycleId, page: 1, page_size: 100 })
      .then((p) => setRows(p.items))
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load batches — ${msg}`);
      })
      .finally(() => setLoading(false));
  }, [cycleId]);

  if (loading) return <Loader />;
  if (rows.length === 0) return <Empty title="No batches yet for this cycle" hint={
    cycleStatus === "open"
      ? "Cycle close generates batches automatically."
      : "Batches will appear once batch generation has run."
  } />;

  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left">Batch #</th>
            <th className="px-3 py-2 text-left">Effective entry</th>
            <th className="px-3 py-2 text-right">Total credit</th>
            <th className="px-3 py-2 text-right">Credits</th>
            <th className="px-3 py-2 text-right">Claims</th>
            <th className="px-3 py-2 text-left">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((b) => (
            <tr key={b.id} className="hover:bg-muted/30">
              <td className="px-3 py-1.5">
                <Link href={`/admin/paysync/batches/${b.id}`}
                      className="font-mono text-sky-500 hover:underline">
                  {b.batch_number}
                </Link>
              </td>
              <td className="px-3 py-1.5 font-mono text-xs">{b.effective_entry_date}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">${b.total_credit_amount}</td>
              <td className="px-3 py-1.5 text-right">{b.credit_entry_count}</td>
              <td className="px-3 py-1.5 text-right">{b.claim_count}</td>
              <td className="px-3 py-1.5"><BatchStatusBadge status={b.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Invoices tab ──────────────────────────────────────────────

function InvoicesTab({ cycleId }: { cycleId: string }) {
  const [rows, setRows] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listInvoices({ cycle_id: cycleId, page: 1, page_size: 100 })
      .then((p) => setRows(p.items))
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load invoices — ${msg}`);
      })
      .finally(() => setLoading(false));
  }, [cycleId]);

  if (loading) return <Loader />;
  if (rows.length === 0) return <Empty title="No invoices yet for this cycle" />;

  return (
    <div className="overflow-x-auto rounded-lg border bg-card">
      <table className="w-full text-sm">
        <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
          <tr>
            <th className="px-3 py-2 text-left">Invoice #</th>
            <th className="px-3 py-2 text-left">Type</th>
            <th className="px-3 py-2 text-left">Bill to</th>
            <th className="px-3 py-2 text-left">Date</th>
            <th className="px-3 py-2 text-right">Total</th>
            <th className="px-3 py-2 text-right">Paid</th>
            <th className="px-3 py-2 text-left">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.map((i) => (
            <tr key={i.id}>
              <td className="px-3 py-1.5 font-mono text-xs">
                <Link href={`/admin/paysync/invoices/${i.id}`}
                      className="text-sky-500 hover:underline">
                  {i.invoice_number}
                </Link>
              </td>
              <td className="px-3 py-1.5 text-xs">{i.sequence_type === "reimbursement" ? "Reimbursement" : "Client fees"}</td>
              <td className="px-3 py-1.5 text-xs">{i.bill_to_name}</td>
              <td className="px-3 py-1.5 font-mono text-xs">{i.invoice_date}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">${i.total_amount}</td>
              <td className="px-3 py-1.5 text-right tabular-nums">${i.paid_amount}</td>
              <td className="px-3 py-1.5"><InvoiceStatusBadge status={i.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Reconciliation tab ────────────────────────────────────────

function ReconciliationTab({ cycleId }: { cycleId: string }) {
  const [runs, setRuns] = useState<CycleReconciliation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listReconciliations(cycleId)
      .then(setRuns)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load reconciliations — ${msg}`);
      })
      .finally(() => setLoading(false));
  }, [cycleId]);

  if (loading) return <Loader />;
  if (runs.length === 0) {
    return <Empty title="No reconciliation runs yet" hint="Reconciliation runs automatically during cycle close." />;
  }

  const latest = runs[0];

  return (
    <div className="space-y-6">
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Latest run</h2>
          <Link href={`/admin/paysync/reconciliations/${latest.id}`}
                className="text-xs text-sky-500 hover:underline">
            Open detail
          </Link>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <DeltaDisplay label="Tie 1: Claims ↔ Invoice"
                        description="Reimbursement invoice = sum of cycle claim billed."
                        tie={latest.tie_1} />
          <DeltaDisplay label="Tie 2: Claims ↔ Total AP"
                        description="Sum of cycle pay = manual AP + batch AP + carryover delta."
                        tie={latest.tie_2} />
          <DeltaDisplay label="Tie 3: Batch AP ↔ NACHA ↔ 835"
                        description="Outbound NACHA + 835 totals match batch AP sum."
                        tie={latest.tie_3} />
        </div>
      </section>

      {runs.length > 1 && (
        <section>
          <h2 className="mb-2 text-sm font-semibold">Run history</h2>
          <div className="rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Run at</th>
                  <th className="px-3 py-2 text-left">Run by</th>
                  <th className="px-3 py-2 text-left">Tie 1</th>
                  <th className="px-3 py-2 text-left">Tie 2</th>
                  <th className="px-3 py-2 text-left">Tie 3</th>
                  <th className="px-3 py-2 text-left">Finalized</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {runs.map((r) => (
                  <tr key={r.id}>
                    <td className="px-3 py-1.5 text-xs">{new Date(r.run_at).toLocaleString()}</td>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.run_by ?? "—"}</td>
                    <td className="px-3 py-1.5 text-xs">{r.tie_1.status}</td>
                    <td className="px-3 py-1.5 text-xs">{r.tie_2.status}</td>
                    <td className="px-3 py-1.5 text-xs">{r.tie_3.status}</td>
                    <td className="px-3 py-1.5 text-xs">{r.finalized ? "yes" : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

// ─── Files tab ─────────────────────────────────────────────────

function FilesTab({ cycleId }: { cycleId: string }) {
  const [files, setFiles] = useState<PaysyncFile[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listCycleFiles(cycleId)
      .then(setFiles)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load files — ${msg}`);
      })
      .finally(() => setLoading(false));
  }, [cycleId]);

  if (loading) return <Loader />;
  if (files.length === 0) return <Empty title="No files generated yet" />;

  const groups = files.reduce<Record<string, PaysyncFile[]>>((acc, f) => {
    (acc[f.file_type] ??= []).push(f); return acc;
  }, {});

  return (
    <div className="space-y-4">
      {Object.entries(groups).map(([type, group]) => (
        <section key={type} className="rounded-lg border bg-card p-4">
          <h2 className="mb-3 text-sm font-semibold">{type.replace(/_/g, " ")}</h2>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {group.map((f) => (
              <FileDownloadButton
                key={f.id} fileId={f.id}
                fileLabel={f.file_path.split("/").pop() ?? f.file_path}
                sha256={f.sha256} sizeBytes={f.size_bytes}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

// ─── Common helpers ────────────────────────────────────────────

function Loader() {
  return (
    <div className="flex items-center justify-center p-12 text-muted-foreground">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading…
    </div>
  );
}

function Empty({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-dashed bg-card/40 p-8 text-center">
      <AlertCircle className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
      <p className="text-sm font-medium">{title}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
