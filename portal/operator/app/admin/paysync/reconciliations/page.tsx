"use client";
/**
 * /admin/paysync/reconciliations -- Paysync reconciliations list.
 * Fetches via TanStack Query from /api/paysync/reconciliations (BFF).
 * Renders ReconciliationsListPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { ReconciliationsListPage } from "@infinityrx/module-paysync";
import type { Reconciliation, ReconciliationListResponse } from "@infinityrx/contract";

async function fetchReconciliations(): Promise<ReconciliationListResponse> {
  const res = await fetch("/api/paysync/reconciliations", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch reconciliations");
  return res.json() as Promise<ReconciliationListResponse>;
}

export default function ReconciliationsPage() {
  const { data, isLoading, error } = useQuery<ReconciliationListResponse, Error>({
    queryKey: ["paysync", "reconciliations"],
    queryFn: fetchReconciliations,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <ReconciliationsListPage
        reconciliations={(data?.results ?? []) as ReadonlyArray<Reconciliation>}
        isLoading={isLoading}
        error={error?.message ?? null}
      />
    </div>
  );
}
