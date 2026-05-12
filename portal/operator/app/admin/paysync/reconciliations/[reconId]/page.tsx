"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, CheckCircle2, Loader2, Scale } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listReconciliations, listCycles, finalizeReconciliation,
  type CycleReconciliation, type Cycle,
} from "@shared/lib/paysync-api";

import { DeltaDisplay } from "@/components/paysync/delta-display";
import { MismatchFindingCard } from "@/components/paysync/mismatch-finding-card";

interface PageParams { reconId: string; }

export default function ReconciliationDetailPage(
  { params }: { params: Promise<PageParams> },
) {
  const { reconId } = use(params);
  const [recon, setRecon] = useState<CycleReconciliation | null>(null);
  const [cycle, setCycle] = useState<Cycle | null>(null);
  const [loading, setLoading] = useState(true);

  const [acceptedDeltas, setAcceptedDeltas] = useState(false);
  const [operatorNotes, setOperatorNotes] = useState("");
  const [finalizing, setFinalizing] = useState(false);

  useEffect(() => {
    // Reconciliations are fetched per-cycle, so we walk recent cycles
    // until we find the requested recon. In practice the backend would
    // expose a /reconciliations/{id} endpoint; this client falls back
    // gracefully until that ships.
    let cancelled = false;
    (async () => {
      try {
        const cycles = await listCycles({
          page: 1, page_size: 200, sort_by: "period_start", sort_dir: "desc",
        });
        for (const c of cycles.items) {
          const recons = await listReconciliations(c.id);
          const found = recons.find((r) => r.id === reconId);
          if (found) {
            if (!cancelled) {
              setRecon(found);
              setCycle(c);
            }
            return;
          }
        }
        if (!cancelled) toast.error("Reconciliation not found in recent cycles.");
      } catch (e) {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        if (!cancelled) toast.error(`Load failed — ${msg}`);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [reconId]);

  async function handleFinalize() {
    if (!recon) return;
    const anyMismatch =
      recon.tie_1.status === "mismatch" ||
      recon.tie_2.status === "mismatch" ||
      recon.tie_3.status === "mismatch";
    if (anyMismatch && !operatorNotes.trim()) {
      toast.error("Operator notes are required when any tie has a mismatch.");
      return;
    }
    setFinalizing(true);
    try {
      const updated = await finalizeReconciliation(reconId, {
        accepted_deltas: acceptedDeltas,
        operator_notes: operatorNotes || undefined,
      });
      setRecon(updated);
      toast.success("Reconciliation finalized.");
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Finalize failed — ${msg}`);
    } finally {
      setFinalizing(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading reconciliation…
      </div>
    );
  }
  if (!recon) {
    return (
      <div className="p-6">
        <p className="text-rose-500">Reconciliation not found.</p>
        <Link href="/admin/paysync/reconciliations" className="text-sky-500 hover:underline">
          ← Back to reconciliations
        </Link>
      </div>
    );
  }

  const anyMismatch =
    recon.tie_1.status === "mismatch" ||
    recon.tie_2.status === "mismatch" ||
    recon.tie_3.status === "mismatch";

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/admin/paysync/reconciliations" className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-3.5 w-3.5" /> Reconciliations
        </Link>
      </div>

      <header className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-emerald-500/10 p-2">
          <Scale className="h-5 w-5 text-emerald-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">
            Reconciliation — {cycle?.cycle_label ?? recon.cycle_id.slice(0, 8)}
          </h1>
          <p className="text-sm text-muted-foreground">
            Run {new Date(recon.run_at).toLocaleString()}
            {recon.run_by && ` by ${recon.run_by}`}
            {recon.finalized && (
              <span className="ml-2 text-emerald-500">finalized</span>
            )}
          </p>
        </div>
      </header>

      <section className="mb-6">
        <h2 className="mb-3 text-sm font-semibold">Three-way ties</h2>
        <div className="grid gap-3 md:grid-cols-3">
          <DeltaDisplay
            label="Tie 1: Claims ↔ Invoice"
            description="Reimbursement invoice = sum of cycle claim billed."
            tie={recon.tie_1}
          />
          <DeltaDisplay
            label="Tie 2: Claims ↔ Total AP"
            description="Sum of cycle pay = manual AP + batch AP + carryover delta."
            tie={recon.tie_2}
          />
          <DeltaDisplay
            label="Tie 3: Batch AP ↔ NACHA ↔ 835"
            description="Outbound NACHA + 835 totals match batch AP sum."
            tie={recon.tie_3}
          />
        </div>
      </section>

      {recon.findings.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-3 text-sm font-semibold">
            Findings ({recon.findings.length})
          </h2>
          <div className="space-y-2">
            {recon.findings.map((f, i) => (
              <MismatchFindingCard key={i} finding={f} />
            ))}
          </div>
        </section>
      )}

      {!recon.finalized && (
        <section className="rounded-lg border border-amber-500/40 bg-amber-500/5 p-4">
          <h2 className="mb-3 text-sm font-semibold">Finalize this run</h2>
          <p className="mb-3 text-xs text-muted-foreground">
            Finalization promotes the cycle from <span className="font-mono">reconciled</span>{" "}
            to <span className="font-mono">closed_finalized</span>. Once
            finalized, this run is the cycle's authoritative reconciliation
            record.
          </p>
          {anyMismatch && (
            <label className="mb-3 flex items-start gap-2 text-sm">
              <input type="checkbox" checked={acceptedDeltas}
                     onChange={(e) => setAcceptedDeltas(e.target.checked)} />
              <span>
                I have reviewed the deltas and accept them as expected
                (e.g., timing-based or known accounting offset).
              </span>
            </label>
          )}
          <label className="mb-3 block text-xs">
            <span className="font-medium">
              Operator notes {anyMismatch && <span className="text-rose-500">*</span>}
            </span>
            <textarea value={operatorNotes}
                      onChange={(e) => setOperatorNotes(e.target.value)}
                      rows={3}
                      placeholder={anyMismatch
                        ? "Required — describe the deltas and reasoning"
                        : "Optional"}
                      className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
          </label>
          <button onClick={handleFinalize} disabled={finalizing}
                  className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50">
            {finalizing
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <CheckCircle2 className="h-3.5 w-3.5" />}
            Finalize reconciliation
          </button>
        </section>
      )}

      {recon.finalized && (
        <section className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-4">
          <p className="text-sm">
            Finalized {recon.finalized_at && new Date(recon.finalized_at).toLocaleString()}
            {recon.finalized_by && ` by ${recon.finalized_by}`}.
            {recon.accepted_deltas && " Deltas were accepted by operator."}
          </p>
          {recon.operator_notes && (
            <blockquote className="mt-2 border-l-2 pl-3 text-sm text-muted-foreground">
              {recon.operator_notes}
            </blockquote>
          )}
        </section>
      )}
    </div>
  );
}
