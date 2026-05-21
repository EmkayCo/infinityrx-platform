"use client";
/**
 * /admin/paysync/reconciliations/[id] -- Single reconciliation detail.
 * Fetches via TanStack Query from /api/paysync/reconciliations/[id] (BFF).
 * Renders ReconciliationDetailPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { ReconciliationDetailPage } from "@infinityrx/module-paysync";
import type { Reconciliation } from "@infinityrx/contract";

async function fetchReconciliation(id: string): Promise<Reconciliation | null> {
  const res = await fetch(`/api/paysync/reconciliations/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch reconciliation");
  return res.json() as Promise<Reconciliation>;
}

export default function ReconciliationDetailRoute() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  const { data, isLoading, error } = useQuery<Reconciliation | null, Error>({
    queryKey: ["paysync", "reconciliations", id],
    queryFn: () => fetchReconciliation(id),
    enabled: !!id,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <ReconciliationDetailPage
        reconciliation={data ?? null}
        isLoading={isLoading}
        error={error?.message ?? null}
        currentRole="operator"
        onFinalize={() => undefined}
      />
    </div>
  );
}
