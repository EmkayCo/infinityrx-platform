"use client";
/**
 * /admin/paysync/bank-settlements/[id] -- Single bank settlement detail.
 * Fetches via TanStack Query from /api/paysync/bank-settlements/[id] (BFF).
 * Renders BankSettlementDetailPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { BankSettlementDetailPage } from "@infinityrx/module-paysync";
import type { BankSettlement } from "@infinityrx/contract";

async function fetchBankSettlement(id: string): Promise<BankSettlement | null> {
  const res = await fetch(`/api/paysync/bank-settlements/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch bank settlement");
  return res.json() as Promise<BankSettlement>;
}

export default function BankSettlementDetailRoute() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  const { data, isLoading, error } = useQuery<BankSettlement | null, Error>({
    queryKey: ["paysync", "bank-settlements", id],
    queryFn: () => fetchBankSettlement(id),
    enabled: !!id,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <BankSettlementDetailPage
        settlement={data ?? null}
        isLoading={isLoading}
        error={error?.message ?? null}
        currentRole="operator"
        onResolveDiscrepancy={() => undefined}
      />
    </div>
  );
}
