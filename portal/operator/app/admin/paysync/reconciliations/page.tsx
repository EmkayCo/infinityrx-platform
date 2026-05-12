"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { CheckCircle2, AlertTriangle, Scale } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import { listCycles, listReconciliations, type CycleReconciliation, type Cycle } from "@shared/lib/paysync-api";

export default function ReconciliationsListPage() {
  const [rows, setRows] = useState<Array<CycleReconciliation & { cycle?: Cycle }>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    // Fetch latest cycles + their reconciliations. Backend exposes the
    // full reconciliation history per cycle; we surface the most-recent
    // run for each cycle here.
    listCycles({ page: 1, page_size: 100, sort_by: "period_start", sort_dir: "desc" })
      .then(async (page) => {
        const recons: Array<CycleReconciliation & { cycle: Cycle }> = [];
        for (const c of page.items) {
          try {
            const cycleRecons = await listReconciliations(c.id);
            if (cycleRecons.length > 0) {
              recons.push({ ...cycleRecons[0], cycle: c });
            }
          } catch {
            // skip cycles with no recon endpoint or 403
          }
        }
        if (!cancelled) setRows(recons);
      })
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        if (!cancelled) {
          setError(msg);
          toast.error(`Failed to load reconciliations — ${msg}`);
        }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-emerald-500/10 p-2">
          <Scale className="h-5 w-5 text-emerald-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Reconciliations</h1>
          <p className="text-sm text-muted-foreground">
            Three-way ties (Claims↔Invoice, Claims↔Total AP, Batch↔NACHA↔835)
            per cycle, $0.01 tolerance.
          </p>
        </div>
      </div>

      {loading
        ? <p className="text-sm text-muted-foreground">Loading…</p>
        : error
        ? <p className="text-sm text-rose-500">{error}</p>
        : rows.length === 0
        ? <p className="text-sm text-muted-foreground">No reconciliation runs yet.</p>
        : (
          <div className="rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Cycle</th>
                  <th className="px-3 py-2 text-left">Run at</th>
                  <th className="px-3 py-2 text-center">Tie 1</th>
                  <th className="px-3 py-2 text-center">Tie 2</th>
                  <th className="px-3 py-2 text-center">Tie 3</th>
                  <th className="px-3 py-2 text-left">Finalized</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="px-3 py-1.5">
                      <Link href={`/admin/paysync/cycles/${r.cycle_id}`}
                            className="font-mono text-sky-500 hover:underline">
                        {r.cycle?.cycle_label ?? r.cycle_id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="px-3 py-1.5 text-xs">
                      {new Date(r.run_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-1.5 text-center"><TieIcon tie={r.tie_1.status} /></td>
                    <td className="px-3 py-1.5 text-center"><TieIcon tie={r.tie_2.status} /></td>
                    <td className="px-3 py-1.5 text-center"><TieIcon tie={r.tie_3.status} /></td>
                    <td className="px-3 py-1.5 text-xs">
                      {r.finalized
                        ? <span className="text-emerald-500">finalized</span>
                        : <span className="text-amber-500">pending</span>}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      <Link href={`/admin/paysync/reconciliations/${r.id}`}
                            className="text-xs text-sky-500 hover:underline">
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}

function TieIcon({ tie }: { tie: "match" | "mismatch" }) {
  return tie === "match"
    ? <CheckCircle2 className="mx-auto h-4 w-4 text-emerald-500" aria-label="match" />
    : <AlertTriangle className="mx-auto h-4 w-4 text-rose-500" aria-label="mismatch" />;
}
