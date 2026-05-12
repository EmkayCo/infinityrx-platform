"use client";

// PaySync dashboard — Wave 40 M5.

import { useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  Calendar, Wallet, Receipt, Scale, ArrowLeftRight,
  AlertTriangle, History,
} from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import { getPaysyncDashboard, type PaysyncDashboard } from "@shared/lib/paysync-api";
import { GlobalSearch } from "@/components/paysync/global-search";

export default function PaysyncDashboardPage() {
  const [data, setData] = useState<PaysyncDashboard | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPaysyncDashboard()
      .then(setData)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load dashboard — ${msg}`);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">PaySync dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Overview of open cycles, pending operator actions, and recent
            activity.
          </p>
        </div>
        <GlobalSearch />
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Loading…</p>
        : !data
        ? <p className="text-sm text-rose-500">Dashboard data unavailable.</p>
        : (
          <>
            <section className="mb-6 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
              <KpiCard icon={Calendar} tone="teal"
                       label="Open cycles" value={data.open_cycles_count.toLocaleString()}
                       sub={`${data.open_cycles_claim_count.toLocaleString()} claims`}
                       href="/admin/paysync/cycles?status=open" />
              <KpiCard icon={Wallet} tone="amber"
                       label="Pending close" value={data.pending_close_count.toLocaleString()}
                       sub="cycles ready to close"
                       href="/admin/paysync/cycles?status=closing" />
              <KpiCard icon={Scale} tone="emerald"
                       label="Pending reconciliation" value={data.pending_reconciliation_count.toLocaleString()}
                       sub="awaiting operator finalize"
                       href="/admin/paysync/reconciliations" />
              <KpiCard icon={AlertTriangle} tone="rose"
                       label="Banking discrepancies" value={data.banking_discrepancies_pending.toLocaleString()}
                       sub="pending review"
                       href="/admin/network/banking-discrepancies" />
              <KpiCard icon={ArrowLeftRight} tone="amber"
                       label="Open carryovers" value={data.open_carryovers_count.toLocaleString()}
                       sub={`$${data.open_carryovers_we_owe} we owe · $${data.open_carryovers_pharmacy_owes} owed`}
                       href="/admin/paysync/carryovers?status=open" />
              <QuickActionCard
                icon={Calendar} tone="teal"
                title="View open cycles"
                description="Drill into in-flight cycles and run cycle close."
                href="/admin/paysync/cycles?status=open"
              />
              <QuickActionCard
                icon={Scale} tone="emerald"
                title="Pending reconciliations"
                description="Finalize the latest reconciliation runs."
                href="/admin/paysync/reconciliations"
              />
              <QuickActionCard
                icon={Receipt} tone="sky"
                title="Invoices"
                description="Reimbursement + client-fee invoices."
                href="/admin/paysync/invoices"
              />
            </section>

            <section className="rounded-lg border bg-card">
              <header className="flex items-center gap-2 border-b px-4 py-3">
                <History className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold">Recent activity</h2>
              </header>
              {data.recent_activity.length === 0
                ? <p className="p-4 text-sm text-muted-foreground">No recent activity.</p>
                : (
                  <ul className="divide-y">
                    {data.recent_activity.map((a) => (
                      <li key={a.id} className="px-4 py-2 text-sm">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-medium">{a.event_type}</p>
                            <p className="text-xs text-muted-foreground">{a.description}</p>
                            <p className="text-[11px] text-muted-foreground">
                              {new Date(a.occurred_at).toLocaleString()}
                              {a.actor && ` · ${a.actor}`}
                            </p>
                          </div>
                          {a.related_entity_url && (
                            <Link href={a.related_entity_url}
                                  className="text-xs text-sky-500 hover:underline">
                              Open →
                            </Link>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
            </section>
          </>
        )}
    </div>
  );
}

function KpiCard({
  icon: Icon, tone, label, value, sub, href,
}: {
  icon: typeof Calendar;
  tone: "teal" | "amber" | "emerald" | "rose" | "sky" | "violet";
  label: string;
  value: string;
  sub: string;
  href: string;
}) {
  const toneCls: Record<typeof tone, string> = {
    teal: "bg-teal-500/10 text-teal-500",
    amber: "bg-amber-500/10 text-amber-500",
    emerald: "bg-emerald-500/10 text-emerald-500",
    rose: "bg-rose-500/10 text-rose-500",
    sky: "bg-sky-500/10 text-sky-500",
    violet: "bg-violet-500/10 text-violet-500",
  };
  return (
    <Link href={href}
          className="rounded-lg border bg-card p-4 transition-colors hover:bg-muted/30">
      <div className="mb-2 flex items-center gap-2">
        <div className={`rounded-md p-1.5 ${toneCls[tone]}`}>
          <Icon className="h-4 w-4" />
        </div>
        <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</p>
      </div>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>
    </Link>
  );
}

function QuickActionCard({
  icon: Icon, tone, title, description, href,
}: {
  icon: typeof Calendar;
  tone: "teal" | "emerald" | "sky";
  title: string;
  description: string;
  href: string;
}) {
  const toneCls: Record<typeof tone, string> = {
    teal: "bg-teal-500/10 text-teal-500",
    emerald: "bg-emerald-500/10 text-emerald-500",
    sky: "bg-sky-500/10 text-sky-500",
  };
  return (
    <Link href={href}
          className="rounded-lg border bg-card p-4 transition-colors hover:bg-muted/30">
      <div className={`mb-2 inline-flex rounded-md p-2 ${toneCls[tone]}`}>
        <Icon className="h-4 w-4" />
      </div>
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
    </Link>
  );
}
