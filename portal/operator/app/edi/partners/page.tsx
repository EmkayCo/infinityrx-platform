"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { Shield, AlertTriangle } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { TradingPartner, PartnerStatus } from "@shared/types/edi";
import { cn, formatDate } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const STATUS_BADGE: Record<PartnerStatus, string> = {
  active: "bg-green-900/40 text-green-300",
  test: "bg-yellow-900/40 text-yellow-300",
  disabled: "bg-slate-700 text-slate-400",
};

const columns: ColDef<TradingPartner>[] = [
  {
    accessorKey: "name",
    header: "Partner",
    cell: (c) => <span className="font-medium text-white">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: (c) => (
      <span className={cn("text-xs px-2 py-0.5 rounded capitalize", STATUS_BADGE[c.getValue() as PartnerStatus])}>
        {c.getValue() as string}
      </span>
    ),
  },
  {
    accessorKey: "protocols",
    header: "Protocols",
    cell: (c) => (
      <div className="flex gap-1">
        {(c.getValue() as string[]).map((p) => (
          <span key={p} className="text-xs px-1.5 py-0.5 rounded bg-navy-700 text-slate-300">{p}</span>
        ))}
      </div>
    ),
  },
  {
    accessorKey: "accepted_transaction_types",
    header: "Transaction Types",
    cell: (c) => (
      <div className="flex gap-1 flex-wrap">
        {(c.getValue() as string[]).slice(0, 5).map((t) => (
          <span key={t} className="text-xs px-1.5 py-0.5 rounded bg-navy-700/60 text-slate-400 font-mono">{t}</span>
        ))}
        {(c.getValue() as string[]).length > 5 && (
          <span className="text-xs text-slate-500">+{(c.getValue() as string[]).length - 5}</span>
        )}
      </div>
    ),
  },
  {
    accessorKey: "cert_expiry",
    header: "Cert Expiry",
    cell: (c) => {
      const row = c.row.original;
      const days = row.days_until_cert_expiry ?? 999;
      return (
        <span className={cn(
          "flex items-center gap-1 text-xs",
          days < 30 ? "text-red-400" : days < 90 ? "text-yellow-400" : "text-slate-400"
        )}>
          {days < 90 && <AlertTriangle className="w-3 h-3" />}
          {c.getValue() ? formatDate(c.getValue() as string) : "—"}
          {days < 90 && ` (${days}d)`}
        </span>
      );
    },
  },
  {
    accessorKey: "test_mode",
    header: "Mode",
    cell: (c) => (
      <span className={cn(
        "text-xs px-2 py-0.5 rounded",
        c.getValue() ? "bg-yellow-900/40 text-yellow-300" : "bg-green-900/40 text-green-300"
      )}>
        {c.getValue() ? "Test" : "Production"}
      </span>
    ),
  },
];

export default function TradingPartnersPage() {
  const router = useRouter();

  const { data: partners = [], isLoading } = useQuery<TradingPartner[]>({
    queryKey: ["trading-partners"],
    queryFn: () =>
      apiGet<TradingPartner[]>(buildUrl(`${API_URLS.edi}/api/v1/trading-partners`)),
    staleTime: 60_000,
  });

  const expiringCount = partners.filter((p) => (p.days_until_cert_expiry ?? 999) < 90).length;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Trading Partners</h1>
          <p className="text-slate-400 text-sm mt-1">{partners.length} partners configured</p>
        </div>
        <div className="flex items-center gap-2">
          {expiringCount > 0 && (
            <button
              onClick={() => router.push("/edi/certs")}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-orange-700/30 bg-orange-900/10 text-orange-300 text-sm hover:bg-orange-900/20 transition-colors"
            >
              <AlertTriangle className="w-4 h-4" />
              {expiringCount} cert{expiringCount > 1 ? "s" : ""} expiring
            </button>
          )}
          <button
            onClick={() => router.push("/edi/monitor")}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors"
          >
            <Shield className="w-4 h-4" />
            Transaction Monitor
          </button>
        </div>
      </div>

      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <DataTable
            columns={columns}
            data={partners}
            isLoading={isLoading}
            emptyTitle="No trading partners configured"
            emptyDescription="Configure trading partners to enable EDI transactions."
            onRowClick={(r: TradingPartner) => router.push(`/edi/partners/${r.id}`)}
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
