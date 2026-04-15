"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@shared/lib/api-client";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { KpiCardRow } from "@/components/ui/kpi-card-row";

interface BillingCycle {
  id: string;
  cycle_period: string;
  status: string;
  client_name?: string;
  program_name?: string;
  total_claims: number;
  total_ap_amount: string;
  total_ar_amount: string;
  total_fee_amount: string;
  created_at: string;
  approved_at?: string | null;
  approved_by?: string | null;
}

interface CycleSummary {
  active: number;
  pending_approval: number;
  total_ap: string;
  total_ar: string;
}

const COLUMNS: Column<BillingCycle>[] = [
  {
    id: "cycle_period",
    header: "Period",
    accessor: (r) => r.cycle_period,
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
    id: "client_name",
    header: "Client",
    accessor: (r) => r.client_name,
    defaultVisible: true,
  },
  {
    id: "program_name",
    header: "Program",
    accessor: (r) => r.program_name,
    defaultVisible: true,
  },
  {
    id: "total_claims",
    header: "Claims",
    accessor: (r) => r.total_claims,
    format: "number",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "total_ap_amount",
    header: "AP Total",
    accessor: (r) => r.total_ap_amount,
    format: "currency",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "total_ar_amount",
    header: "AR Total",
    accessor: (r) => r.total_ar_amount,
    format: "currency",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "total_fee_amount",
    header: "Fees",
    accessor: (r) => r.total_fee_amount,
    format: "currency",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "created_at",
    header: "Created",
    accessor: (r) => r.created_at,
    format: "date",
    defaultVisible: true,
  },
  {
    id: "approved_by",
    header: "Approved By",
    accessor: (r) => r.approved_by,
    defaultVisible: false,
  },
  {
    id: "approved_at",
    header: "Approved At",
    accessor: (r) => r.approved_at,
    format: "date",
    defaultVisible: false,
  },
];

export default function BillingCyclesPage() {
  const router = useRouter();

  const { data: summary } = useQuery<CycleSummary>({
    queryKey: ["cycles-summary"],
    queryFn: () => apiGet<CycleSummary>("/api/v1/accounting/cycles/summary"),
  });

  const { data, isLoading } = useQuery<{ items: BillingCycle[]; total: number }>({
    queryKey: ["billing-cycles"],
    queryFn: () => apiGet<{ items: BillingCycle[]; total: number }>("/billing/v1/cycles"),
  });

  const rows = data?.items ?? [];
  const pendingApproval = rows.filter((r) => r.status === "pending_approval");
  const totalAp = rows.reduce((s, r) => s + Number(r.total_ap_amount ?? 0), 0).toFixed(2);
  const totalAr = rows.reduce((s, r) => s + Number(r.total_ar_amount ?? 0), 0).toFixed(2);

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
            Accounting
          </span>
          <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Billing Cycles</h1>
          <p className="mt-1 text-sm text-ifx-gray-400">
            Run billing cycles, review AP/AR, and generate SaaSant, 835, and NACHA outputs.
          </p>
        </div>
      </header>

      <KpiCardRow
        cards={[
          {
            label: "Total Cycles",
            value: data?.total ?? rows.length,
            format: "number",
            accentColor: "var(--ifx-navy)",
          },
          {
            label: "Pending Approval",
            value: summary?.pending_approval ?? pendingApproval.length,
            format: "number",
            accentColor: "var(--ifx-warning)",
            href: "/accounting/cycles",
          },
          {
            label: "Total AP",
            value: summary?.total_ap ?? totalAp,
            format: "currency-compact",
            accentColor: "var(--ifx-error)",
          },
          {
            label: "Total AR",
            value: summary?.total_ar ?? totalAr,
            format: "currency-compact",
            accentColor: "var(--ifx-success)",
          },
        ]}
      />

      <ConfigurableDataTable
        tableId="billing-cycles"
        columns={COLUMNS}
        data={rows}
        getRowId={(r) => r.id}
        onRowClick={(row) => router.push(`/accounting/cycles/${row.id}`)}
        loading={isLoading}
        emptyMessage="No billing cycles found."
        pagination={{ pageSize: 25 }}
      />
    </div>
  );
}
