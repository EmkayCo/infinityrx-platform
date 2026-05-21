"use client";
/**
 * /admin/paysync/invoices -- Paysync invoices list.
 * Fetches via TanStack Query from /api/paysync/invoices (BFF).
 * Renders InvoicesListPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { InvoicesListPage } from "@infinityrx/module-paysync";
import type { Invoice, InvoiceListResponse } from "@infinityrx/contract";

async function fetchInvoices(): Promise<InvoiceListResponse> {
  const res = await fetch("/api/paysync/invoices", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch invoices");
  return res.json() as Promise<InvoiceListResponse>;
}

export default function InvoicesPage() {
  const { data, isLoading, error } = useQuery<InvoiceListResponse, Error>({
    queryKey: ["paysync", "invoices"],
    queryFn: fetchInvoices,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <InvoicesListPage
        invoices={(data?.results ?? []) as ReadonlyArray<Invoice>}
        isLoading={isLoading}
        error={error?.message ?? null}
      />
    </div>
  );
}
