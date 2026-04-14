"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Shield, RefreshCw } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { CertAlert } from "@shared/types/edi";
import { cn, formatDate } from "@shared/lib/format";

const columns: ColDef<CertAlert>[] = [
  {
    accessorKey: "partner_name",
    header: "Partner",
    cell: (c) => <span className="font-medium text-white">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "cert_name",
    header: "Certificate",
    cell: (c) => <span className="font-mono text-xs text-slate-300">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "expires_at",
    header: "Expires",
    cell: (c) => <span className="text-sm text-slate-300">{formatDate(c.getValue() as string)}</span>,
  },
  {
    accessorKey: "days_until_expiry",
    header: "Days Until Expiry",
    cell: (c) => {
      const days = c.getValue() as number;
      return (
        <span className={cn(
          "flex items-center gap-1.5 text-sm font-medium",
          days < 0 ? "text-red-500" : days < 30 ? "text-red-400" : days < 60 ? "text-orange-400" : days < 90 ? "text-yellow-400" : "text-slate-300"
        )}>
          {days < 90 && <AlertTriangle className="w-3.5 h-3.5" />}
          {days < 0 ? "EXPIRED" : `${days} days`}
        </span>
      );
    },
  },
  {
    id: "action",
    header: "Action",
    cell: () => (
      <button className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-teal-600 hover:bg-teal-500 text-white transition-colors">
        <RefreshCw className="w-3 h-3" />
        Renew
      </button>
    ),
  },
];

export default function CertsPage() {
  const { data: certs = [], isLoading } = useQuery<CertAlert[]>({
    queryKey: ["cert-alerts"],
    queryFn: () =>
      apiGet<CertAlert[]>(buildUrl(`${API_URLS.edi}/api/v1/certificates/alerts`)),
    staleTime: 60_000,
  });

  const critical = certs.filter((c) => c.days_until_expiry < 30);
  const warning = certs.filter((c) => c.days_until_expiry >= 30 && c.days_until_expiry < 90);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Certificate Expiry Alerts</h1>
          <p className="text-slate-400 text-sm mt-1">
            {certs.length} certificates monitored
          </p>
        </div>
        <Shield className="w-6 h-6 text-teal-400" />
      </div>

      {critical.length > 0 && (
        <div className="rounded-lg border border-red-700/30 bg-red-900/10 p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0" />
          <p className="text-sm text-red-300">
            <span className="font-semibold">{critical.length} certificate{critical.length > 1 ? "s" : ""}</span> expire within 30 days. Renew immediately.
          </p>
        </div>
      )}

      {warning.length > 0 && (
        <div className="rounded-lg border border-yellow-700/20 bg-yellow-900/5 p-4 flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
          <p className="text-sm text-yellow-300">
            <span className="font-semibold">{warning.length} certificate{warning.length > 1 ? "s" : ""}</span> expire within 90 days.
          </p>
        </div>
      )}

      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <DataTable
            columns={columns}
            data={certs}
            isLoading={isLoading}
            emptyTitle="No certificate alerts"
            emptyDescription="All certificates are valid and not expiring soon."
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
