"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ShieldAlert } from "lucide-react";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { PharmacyRiskScore } from "@shared/types/reclaimrx";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { cn } from "@shared/lib/format";

const TIER_CLASSES: Record<PharmacyRiskScore["risk_tier"], string> = {
  critical: "bg-red-100 text-red-700 font-bold",
  high: "bg-orange-100 text-orange-700 font-bold",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-green-100 text-green-700",
};

function RiskScoreBadge({ score, tier }: { score: number; tier: PharmacyRiskScore["risk_tier"] }) {
  return (
    <div className="flex items-center gap-2">
      <div className="relative w-16 h-2 rounded-full bg-gray-200 overflow-hidden">
        <div
          className={cn(
            "absolute inset-y-0 left-0 rounded-full transition-all",
            tier === "critical"
              ? "bg-red-500"
              : tier === "high"
                ? "bg-orange-400"
                : tier === "medium"
                  ? "bg-yellow-400"
                  : "bg-green-400"
          )}
          style={{ width: `${score}%` }}
        />
      </div>
      <span
        className={cn(
          "text-xs px-1.5 py-0.5 rounded",
          TIER_CLASSES[tier]
        )}
      >
        {score}
      </span>
    </div>
  );
}

const COLUMNS: Column<PharmacyRiskScore>[] = [
  {
    id: "pharmacy_name",
    header: "Pharmacy",
    accessor: (r) => r.pharmacy_name,
    pinned: true,
    sortable: true,
  },
  {
    id: "npi",
    header: "NPI",
    accessor: (r) => r.npi,
    cell: (v) => <span className="font-mono text-xs text-ifx-gray-700">{v as string}</span>,
  },
  {
    id: "risk_score",
    header: "Risk Score",
    accessor: (r) => r.risk_score,
    cell: (v, row) => <RiskScoreBadge score={row.risk_score} tier={row.risk_tier} />,
    sortable: true,
    align: "left",
  },
  {
    id: "risk_tier",
    header: "Tier",
    accessor: (r) => r.risk_tier,
    cell: (v) => {
      const tier = v as PharmacyRiskScore["risk_tier"];
      return (
        <span className={cn("text-xs px-2 py-0.5 rounded-full capitalize", TIER_CLASSES[tier])}>
          {tier}
        </span>
      );
    },
    sortable: true,
  },
  {
    id: "chain_code",
    header: "Chain",
    accessor: (r) => r.chain_code,
    sortable: true,
  },
  {
    id: "state",
    header: "State",
    accessor: (r) => r.state,
    sortable: true,
  },
  {
    id: "total_claims",
    header: "Total Claims",
    accessor: (r) => r.total_claims,
    format: "number",
    sortable: true,
    align: "right",
  },
  {
    id: "total_copay_paid",
    header: "Total Copay Paid",
    accessor: (r) => r.total_copay_paid,
    format: "currency",
    sortable: true,
    align: "right",
  },
  {
    id: "reversal_rate",
    header: "Reversal Rate",
    accessor: (r) => `${(parseFloat(r.reversal_rate) * 100).toFixed(1)}%`,
    sortable: true,
    align: "right",
  },
  {
    id: "active_investigations",
    header: "Active Inv.",
    accessor: (r) => r.active_investigations,
    cell: (v) => {
      const n = v as number;
      return (
        <span className={cn("text-sm font-medium", n > 0 ? "text-red-600" : "text-ifx-gray-400")}>
          {n > 0 ? n : "—"}
        </span>
      );
    },
    sortable: true,
    align: "right",
  },
  {
    id: "top_factor",
    header: "Top Risk Factor",
    accessor: (r) => r.factors[0]?.description ?? "—",
    cell: (v) => (
      <span className="text-xs text-ifx-gray-400 truncate max-w-[200px] block">{v as string}</span>
    ),
    defaultVisible: false,
  },
];

export default function PharmacyRiskScoresPage() {
  const router = useRouter();

  const { data: pharmacies = [], isLoading } = useQuery<PharmacyRiskScore[]>({
    queryKey: ["pharmacy-risk-scores"],
    queryFn: () =>
      apiGet<PharmacyRiskScore[]>(
        buildUrl(`${API_URLS.reclaimrx}/api/v1/reclaimrx/risk-scores`)
      ),
    staleTime: 120_000,
  });

  const criticalCount = pharmacies.filter((p) => p.risk_tier === "critical").length;
  const highCount = pharmacies.filter((p) => p.risk_tier === "high").length;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-orange-500" />
            <h1 className="text-xl font-bold text-ifx-gray-900">Pharmacy Risk Scores</h1>
          </div>
          <p className="text-sm text-ifx-gray-400 mt-0.5">
            {pharmacies.length} pharmacies scored ·{" "}
            <span className="text-red-600 font-medium">{criticalCount} critical</span>
            {" · "}
            <span className="text-orange-600 font-medium">{highCount} high risk</span>
          </p>
        </div>
      </div>

      {/* Factor key */}
      <div className="flex items-center gap-4 text-xs text-ifx-gray-400">
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-red-500 inline-block" /> Critical (75–100)
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-orange-400 inline-block" /> High (50–74)
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-yellow-400 inline-block" /> Medium (25–49)
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-3 rounded bg-green-400 inline-block" /> Low (0–24)
        </span>
      </div>

      <div className="bg-white rounded-lg ifx-card-shadow">
        <ConfigurableDataTable
          tableId="pharmacy-risk-scores"
          columns={COLUMNS}
          data={pharmacies}
          loading={isLoading}
          searchable
          exportable
          pagination={{ pageSize: 25, pageSizeOptions: [25, 50, 100] }}
          emptyMessage="No pharmacy risk scores available."
          onRowClick={(row) =>
            router.push(`/directories/pharmacies/${row.npi}?tab=risk`)
          }
        />
      </div>
    </div>
  );
}
