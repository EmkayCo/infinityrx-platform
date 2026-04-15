"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Eye, ExternalLink } from "lucide-react";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { apiGet } from "@shared/lib/api-client";
import type { ClientRow } from "@shared/lib/mock-data/seed/programs";

interface ClientListResponse {
  clients: ClientRow[];
  total: number;
}

export default function PortalAccessPage() {
  const [selectedClient, setSelectedClient] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["clients"],
    queryFn: () => apiGet<ClientListResponse>("/api/v1/clients"),
    staleTime: 60_000,
  });

  const clients = (data?.clients ?? []).filter((c) => c.status === "enabled");
  const selected = clients.find((c) => c.id === selectedClient);

  return (
    <DetailPageLayout
      title="Portal Access"
      subtitle="View as manufacturer — select a client to preview what they see on their portal. Read-only. Use this for support calls."
    >
      <div className="rounded-lg bg-white ifx-card-shadow p-6">
        <h3 className="text-sm font-bold text-ifx-gray-900 mb-4">Select Client</h3>
        <div className="max-w-sm">
          {isLoading ? (
            <div className="h-10 shimmer rounded" />
          ) : (
            <select
              value={selectedClient}
              onChange={(e) => setSelectedClient(e.target.value)}
              aria-label="Select client for manufacturer view"
              className="w-full rounded border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
            >
              <option value="">— Select a client —</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.company_name}
                </option>
              ))}
            </select>
          )}
        </div>

        {selected && (
          <div className="mt-6 rounded-lg border border-ifx-gray-100 p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                  Manufacturer View
                </p>
                <h4 className="text-base font-bold text-ifx-gray-900">
                  {selected.company_name}
                </h4>
                <p className="text-sm text-ifx-gray-400">
                  {selected.city}, {selected.state} &middot; BIN {selected.bin}
                </p>
              </div>
              <Eye className="h-8 w-8 text-ifx-gray-400" />
            </div>

            <div className="mb-4 rounded-md bg-amber-50 border border-amber-200 px-4 py-3">
              <p className="text-xs font-medium text-amber-700">
                Read-only mode. You are viewing this portal as the manufacturer.
                No changes can be made from this view.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                { label: "Programs", value: String(selected.programs_count), href: `/clients/${selected.id}?tab=programs` },
                { label: "Contact", value: selected.contact_name, href: "#" },
                { label: "Email", value: selected.email, href: "#" },
                { label: "Phone", value: selected.phone, href: "#" },
              ].map(({ label, value }) => (
                <div key={label}>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400 mb-1">
                    {label}
                  </p>
                  <p className="text-sm text-ifx-gray-900">{value}</p>
                </div>
              ))}
            </div>

            <div className="mt-5 flex gap-3">
              <a
                href={`/clients/${selected.id}`}
                className="inline-flex items-center gap-2 rounded-md bg-[var(--ifx-navy)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--ifx-navy-dark)] transition-colors"
              >
                <ExternalLink className="h-4 w-4" />
                Open Manufacturer Dashboard (Read-only)
              </a>
              <button
                onClick={() => setSelectedClient("")}
                className="rounded-md border border-ifx-gray-100 px-4 py-2 text-sm font-medium text-ifx-gray-700 hover:border-ifx-blue transition-colors"
              >
                Change Client
              </button>
            </div>
          </div>
        )}

        {!selected && !isLoading && (
          <div className="mt-6 rounded-lg border border-dashed border-ifx-gray-100 py-12 text-center">
            <Eye className="h-10 w-10 text-ifx-gray-400 mx-auto mb-3" />
            <p className="text-sm font-medium text-ifx-gray-700">No client selected</p>
            <p className="text-xs text-ifx-gray-400 mt-1">
              Select a manufacturer above to preview their portal view.
            </p>
          </div>
        )}
      </div>
    </DetailPageLayout>
  );
}
