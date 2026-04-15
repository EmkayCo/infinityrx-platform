"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, MapPin } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { ExportMenu } from "@shared/components/export-menu";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Pharmacy, NetworkStatus, CredentialingStatus } from "@shared/types/directories";
import { cn } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const NETWORK_BADGE: Record<NetworkStatus, string> = {
  in_network: "bg-green-900/40 text-green-300",
  preferred: "bg-blue-900/40 text-blue-300",
  out_of_network: "bg-slate-700 text-slate-400",
  pending: "bg-yellow-900/40 text-yellow-300",
  terminated: "bg-red-900/40 text-red-300",
};

const CRED_BADGE: Record<CredentialingStatus, string> = {
  credentialed: "bg-green-900/40 text-green-300",
  pending: "bg-yellow-900/40 text-yellow-300",
  suspended: "bg-orange-900/40 text-orange-300",
  revoked: "bg-red-900/40 text-red-300",
  expired: "bg-red-900/40 text-red-400",
};

const columns: ColDef<Pharmacy>[] = [
  {
    accessorKey: "npi",
    header: "NPI",
    cell: (c) => <span className="font-mono text-xs text-teal-400">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "name",
    header: "Pharmacy Name",
    cell: (c) => <span className="font-medium text-white">{c.getValue() as string}</span>,
  },
  {
    id: "address",
    header: "Address",
    cell: (c) => {
      const row = c.row.original;
      return (
        <span className="text-xs text-slate-400">
          {row.city}, {row.state} {row.zip}
        </span>
      );
    },
  },
  {
    accessorKey: "pharmacy_type",
    header: "Type",
    cell: (c) => (
      <span className="text-xs text-slate-300 capitalize">
        {(c.getValue() as string).replace(/_/g, " ")}
      </span>
    ),
  },
  {
    accessorKey: "network_status",
    header: "Network",
    cell: (c) => (
      <span
        className={cn(
          "text-xs px-2 py-0.5 rounded capitalize",
          NETWORK_BADGE[c.getValue() as NetworkStatus]
        )}
      >
        {(c.getValue() as string).replace(/_/g, " ")}
      </span>
    ),
  },
  {
    accessorKey: "credentialing_status",
    header: "Credentialing",
    cell: (c) => (
      <span
        className={cn(
          "text-xs px-2 py-0.5 rounded capitalize",
          CRED_BADGE[c.getValue() as CredentialingStatus]
        )}
      >
        {c.getValue() as string}
      </span>
    ),
  },
];

export default function PharmaciesPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");

  const { data: pharmacies = [], isLoading } = useQuery<Pharmacy[]>({
    queryKey: ["pharmacies", search],
    queryFn: () =>
      apiGet<Pharmacy[]>(
        buildUrl(`${API_URLS.pharmacyDirectory}/api/v1/pharmacies`, {
          q: search || undefined,
          limit: 100,
        })
      ),
    staleTime: 60_000,
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Pharmacy Directory</h1>
          <p className="text-slate-400 text-sm mt-1">
            {pharmacies.length} pharmacies
          </p>
        </div>
        <ExportMenu onExportCsv={() => {/* export */}} onExportExcel={() => {/* export */}} />
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="search"
            placeholder="Search NPI, name, city, state..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-sm placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          />
        </div>
        <button className="flex items-center gap-2 px-3 py-2 rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 text-sm transition-colors">
          <MapPin className="w-4 h-4" />
          Map View
        </button>
      </div>

      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <DataTable
            columns={columns}
            data={pharmacies}
            isLoading={isLoading}
            emptyTitle="No pharmacies found"
            emptyDescription="Try adjusting your search terms."
            onRowClick={(r: Pharmacy) => router.push(`/directories/pharmacies/${r.npi}`)}
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
