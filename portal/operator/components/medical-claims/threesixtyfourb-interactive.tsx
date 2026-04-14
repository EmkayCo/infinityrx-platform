"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import type { ThreeFourtyBSummary, MedicalClaim } from "@shared/types/medical-claims";
import { formatDate } from "@shared/lib/format";

const recentColumns: ColDef<MedicalClaim>[] = [
  { accessorKey: "claim_number", header: "Claim #", cell: (c) => <span className="font-mono text-xs text-teal-400">{c.getValue() as string}</span> },
  { accessorKey: "hcpcs_code", header: "HCPCS", cell: (c) => <span className="font-mono text-xs font-bold">{c.getValue() as string}</span> },
  { accessorKey: "drug_name", header: "Drug" },
  { accessorKey: "provider_name", header: "Provider" },
  { accessorKey: "date_of_service", header: "DOS", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "billed_amount", header: "Billed", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "paid_amount", header: "Paid", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
];

interface Props {
  summary: ThreeFourtyBSummary;
}

export function ThreeFourtyBInteractive({ summary }: Props) {
  const router = useRouter();

  return (
    <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
      <h3 className="text-sm font-semibold text-slate-200 mb-4">Recent 340B Claims</h3>
      <DataTable
        columns={recentColumns}
        data={summary.recent_claims ?? []}
        emptyTitle="No 340B claims found"
        onRowClick={(r: MedicalClaim) => router.push(`/medical-claims/claims/${r.id}`)}
      />
    </div>
  );
}
