"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { ArrowLeft, Banknote, Loader2 } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  getBankSettlement, listSettlementEntries,
  type BankSettlement, type BankSettlementEntry,
} from "@shared/lib/paysync-api";

interface PageParams { settlementId: string; }

export default function SettlementDetailPage(
  { params }: { params: Promise<PageParams> },
) {
  const { settlementId } = use(params);
  const [settlement, setSettlement] = useState<BankSettlement | null>(null);
  const [entries, setEntries] = useState<BankSettlementEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getBankSettlement(settlementId),
      listSettlementEntries(settlementId),
    ]).then(([s, e]) => {
      if (cancelled) return;
      setSettlement(s);
      setEntries(e);
    }).catch((err: unknown) => {
      const msg = err instanceof ApiClientError ? `${err.code}: ${err.message}` : String(err);
      toast.error(`Failed to load settlement — ${msg}`);
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [settlementId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading…
      </div>
    );
  }
  if (!settlement) {
    return (
      <div className="p-6">
        <p className="text-rose-500">Settlement not found.</p>
        <Link href="/admin/paysync/bank-settlements" className="text-sky-500 hover:underline">
          ← Back
        </Link>
      </div>
    );
  }

  const totalEntries = entries.reduce((sum, e) =>
    sum + (e.returned ? 0 : Number(e.settled_amount)), 0);

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/admin/paysync/bank-settlements"
              className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-3.5 w-3.5" /> Settlements
        </Link>
        <span>/</span>
        <span className="font-mono text-foreground">{settlement.bank_reference}</span>
      </div>

      <header className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-emerald-500/10 p-2">
          <Banknote className="h-5 w-5 text-emerald-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Settlement {settlement.settlement_date}</h1>
          <p className="text-sm text-muted-foreground">
            {settlement.bank_reference} · ${settlement.settled_amount} settled
            · {settlement.source.replace("_", " ")} · status {settlement.status}
          </p>
        </div>
      </header>

      <div className="mb-6 grid gap-3 md:grid-cols-4">
        <Kpi label="Entries" value={entries.length.toLocaleString()} />
        <Kpi label="Net settled" value={`$${totalEntries.toFixed(2)}`} />
        <Kpi label="Bounced" value={entries.filter(e => e.returned).length.toString()}
             tone={entries.filter(e => e.returned).length > 0 ? "warn" : undefined} />
        <Kpi label="Matched" value={entries.filter(e => e.matched).length.toString()} />
      </div>

      <section className="rounded-lg border bg-card">
        <header className="border-b px-4 py-3">
          <h2 className="text-sm font-semibold">Entries</h2>
        </header>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-3 py-2 text-left">Trace</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2 text-left">Returned</th>
                <th className="px-3 py-2 text-left">R-code</th>
                <th className="px-3 py-2 text-left">Matched</th>
                <th className="px-3 py-2 text-left">Carryover</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {entries.map((e) => (
                <tr key={e.id} className={e.returned ? "bg-rose-500/5" : undefined}>
                  <td className="px-3 py-1.5 font-mono text-xs">{e.trace_number}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">${e.settled_amount}</td>
                  <td className="px-3 py-1.5 text-xs">
                    {e.returned ? <span className="text-rose-500">returned</span> : "no"}
                  </td>
                  <td className="px-3 py-1.5 font-mono text-xs">{e.return_reason_code ?? "—"}</td>
                  <td className="px-3 py-1.5 text-xs">{e.matched ? "✓" : "—"}</td>
                  <td className="px-3 py-1.5 font-mono text-xs">
                    {e.carryover_id?.slice(0, 8) ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Kpi({
  label, value, tone,
}: { label: string; value: string; tone?: "warn" }) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className={`mt-0.5 text-lg font-semibold tabular-nums ${tone === "warn" ? "text-amber-600" : ""}`}>
        {value}
      </p>
    </div>
  );
}
