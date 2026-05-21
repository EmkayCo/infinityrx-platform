"use client";
/**
 * /admin/paysync/invoices/[id] -- Single invoice detail.
 * Fetches via TanStack Query from /api/paysync/invoices/[id] (BFF).
 * Renders InvoiceDetailPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { InvoiceDetailPage } from "@infinityrx/module-paysync";
import type { Invoice } from "@infinityrx/contract";

async function fetchInvoice(id: string): Promise<Invoice | null> {
  const res = await fetch(`/api/paysync/invoices/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch invoice");
  return res.json() as Promise<Invoice>;
}

export default function InvoiceDetailRoute() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  const { data, isLoading, error } = useQuery<Invoice | null, Error>({
    queryKey: ["paysync", "invoices", id],
    queryFn: () => fetchInvoice(id),
    enabled: !!id,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <InvoiceDetailPage
        invoice={data ?? null}
        isLoading={isLoading}
        error={error?.message ?? null}
        currentRole="operator"
        onSend={() => undefined}
      />
    </div>
  );
}
