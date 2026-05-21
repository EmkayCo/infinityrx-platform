"use client";
/**
 * /admin/paysync/bank-settlements -- Paysync bank settlements list.
 * Fetches via TanStack Query from /api/paysync/bank-settlements (BFF).
 * Renders BankSettlementsListPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { BankSettlementsListPage } from "@infinityrx/module-paysync";
import type { BankSettlement, BankSettlementListResponse } from "@infinityrx/contract";

async function fetchBankSettlements(): Promise<BankSettlementListResponse> {
  const res = await fetch("/api/paysync/bank-settlements", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch bank settlements");
  return res.json() as Promise<BankSettlementListResponse>;
}

export default function BankSettlementsPage() {
  const { data, isLoading, error } = useQuery<BankSettlementListResponse, Error>({
    queryKey: ["paysync", "bank-settlements"],
    queryFn: fetchBankSettlements,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <BankSettlementsListPage
        settlements={(data?.results ?? []) as ReadonlyArray<BankSettlement>}
        isLoading={isLoading}
        error={error?.message ?? null}
      />
    </div>
  );
}
