"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@shared/lib/api-client";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { KpiCardRow } from "@/components/ui/kpi-card-row";

interface MockClaim {
  id: string;
  fill_date?: string;
  status?: string;
  pharmacy_name?: string;
  pharmacy_npi?: string;
  drug_name?: string;
  drug_ndc?: string;
  member_id?: string;
  client_name?: string;
  program_name?: string;
  ingredient_cost?: string;
  dispensing_fee?: string;
  copay?: string;
  plan_paid?: string;
  quantity?: string | number;
  days_supply?: number;
  rejection_reason?: string | null;
}

interface ClaimsSummary {
  today?: number;
  mtd?: number;
  ytd?: number;
  paid?: number;
  reversals?: number;
  total_billed?: string;
}

const COLUMNS: Column<MockClaim>[] = [
  {
    id: "fill_date",
    header: "Date",
    accessor: (r) => r.fill_date,
    format: "date",
    pinned: true,
    defaultVisible: true,
  },
  {
    id: "status",
    header: "Status",
    accessor: (r) => r.status,
    format: "status",
    defaultVisible: true,
  },
  {
    id: "pharmacy_name",
    header: "Pharmacy",
    accessor: (r) => r.pharmacy_name,
    defaultVisible: true,
  },
  {
    id: "pharmacy_npi",
    header: "NPI",
    accessor: (r) => r.pharmacy_npi,
    format: "npi",
    defaultVisible: true,
  },
  {
    id: "drug_name",
    header: "Drug",
    accessor: (r) => r.drug_name,
    defaultVisible: true,
  },
  {
    id: "drug_ndc",
    header: "NDC",
    accessor: (r) => r.drug_ndc,
    format: "ndc",
    defaultVisible: true,
  },
  {
    id: "member_id",
    header: "Member ID",
    accessor: (r) => r.member_id,
    defaultVisible: true,
  },
  {
    id: "client_name",
    header: "Client",
    accessor: (r) => r.client_name,
    defaultVisible: false,
  },
  {
    id: "program_name",
    header: "Program",
    accessor: (r) => r.program_name,
    defaultVisible: false,
  },
  {
    id: "quantity",
    header: "Qty",
    accessor: (r) => r.quantity,
    format: "number",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "days_supply",
    header: "Days",
    accessor: (r) => r.days_supply,
    format: "number",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "ingredient_cost",
    header: "Ingredient Cost",
    accessor: (r) => r.ingredient_cost,
    format: "currency",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "dispensing_fee",
    header: "Disp. Fee",
    accessor: (r) => r.dispensing_fee,
    format: "currency",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "copay",
    header: "Copay",
    accessor: (r) => r.copay,
    format: "currency",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "plan_paid",
    header: "Paid",
    accessor: (r) => r.plan_paid,
    format: "currency",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "rejection_reason",
    header: "Reject Reason",
    accessor: (r) => r.rejection_reason,
    defaultVisible: false,
  },
];

export default function ClaimsExplorerPage() {
  const router = useRouter();

  const { data: summary } = useQuery<ClaimsSummary>({
    queryKey: ["claims-summary"],
    queryFn: () => apiGet<ClaimsSummary>("/billing/v1/claims/summary"),
  });

  const { data, isLoading } = useQuery<{ items: MockClaim[]; total: number }>({
    queryKey: ["claims-list"],
    queryFn: () => apiGet<{ items: MockClaim[]; total: number }>("/billing/v1/claims"),
  });

  const rows = data?.items ?? [];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
            Claims
          </span>
          <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Claims Explorer</h1>
          <p className="mt-1 text-sm text-ifx-gray-400">
            Browse and investigate every pharmacy claim processed on InfinityRx.
          </p>
        </div>
      </header>

      <KpiCardRow
        cards={[
          {
            label: "Claims (YTD)",
            value: summary?.ytd ?? rows.length,
            format: "number",
            accentColor: "var(--ifx-navy)",
            href: "/claims",
          },
          {
            label: "Paid",
            value: summary?.paid ?? rows.filter((r) => r.status === "paid").length,
            format: "number",
            accentColor: "var(--ifx-success)",
          },
          {
            label: "Reversed",
            value: summary?.reversals ?? rows.filter((r) => r.status === "reversed").length,
            format: "number",
            accentColor: "var(--ifx-error)",
          },
          {
            label: "Total Billed",
            value: summary?.total_billed ?? "0",
            format: "currency-compact",
            accentColor: "var(--ifx-blue)",
          },
        ]}
      />

      <ConfigurableDataTable
        tableId="claims-explorer"
        columns={COLUMNS}
        data={rows}
        getRowId={(r) => r.id}
        onRowClick={(row) => router.push(`/claims/${row.id}`)}
        loading={isLoading}
        emptyMessage="No claims match the current filters."
        pagination={{ pageSize: 25 }}
      />
    </div>
  );
}
