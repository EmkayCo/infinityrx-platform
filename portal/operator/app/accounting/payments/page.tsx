"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@shared/lib/api-client";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { KpiCardRow } from "@/components/ui/kpi-card-row";

interface PaymentBatch {
  id: string;
  vendor?: string;
  vendor_name?: string;
  status: string;
  total_amount: string;
  payment_count?: number;
  claim_count?: number;
  created_at: string;
  approved_at?: string | null;
  settled_at?: string | null;
  nrid?: string;
}

interface PaymentSummary {
  pending_batches: number;
  total_pending_amount: string;
  settled_today: string;
  returned_today: number;
  total_pharmacy_paid: string;
}

const COLUMNS: Column<PaymentBatch>[] = [
  {
    id: "id",
    header: "Batch ID",
    accessor: (r) => r.id.slice(0, 8) + "…",
    pinned: true,
    defaultVisible: true,
  },
  {
    id: "vendor_name",
    header: "Type / Vendor",
    accessor: (r) => r.vendor_name ?? r.vendor ?? "—",
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
    id: "total_amount",
    header: "Total Amount",
    accessor: (r) => r.total_amount,
    format: "currency",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "payment_count",
    header: "Payments",
    accessor: (r) => r.payment_count ?? r.claim_count,
    format: "number",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "created_at",
    header: "Created",
    accessor: (r) => r.created_at,
    format: "date",
    defaultVisible: true,
  },
  {
    id: "approved_at",
    header: "Approved",
    accessor: (r) => r.approved_at,
    format: "date",
    defaultVisible: false,
  },
  {
    id: "settled_at",
    header: "Settled",
    accessor: (r) => r.settled_at,
    format: "date",
    defaultVisible: false,
  },
  {
    id: "nrid",
    header: "NRID",
    accessor: (r) => r.nrid,
    defaultVisible: false,
  },
];

export default function PaymentsBatchesPage() {
  const router = useRouter();

  const { data: summary } = useQuery<PaymentSummary>({
    queryKey: ["payments-summary"],
    queryFn: () => apiGet<PaymentSummary>("/api/v1/payments/dashboard"),
  });

  const { data, isLoading } = useQuery<{ items: PaymentBatch[]; total: number }>({
    queryKey: ["payment-batches"],
    queryFn: () => apiGet<{ items: PaymentBatch[]; total: number }>("/batches"),
  });

  const rows = data?.items ?? [];

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
          Accounting
        </span>
        <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Payments &amp; Batches</h1>
        <p className="mt-1 text-sm text-ifx-gray-400">
          Payment batches — ACH, check, and individual payments with claim assignments.
        </p>
      </header>

      <KpiCardRow
        cards={[
          {
            label: "Pending Batches",
            value: summary?.pending_batches ?? rows.filter((r) => r.status === "pending_approval").length,
            format: "number",
            accentColor: "var(--ifx-warning)",
          },
          {
            label: "Pending Amount",
            value: summary?.total_pending_amount ?? "0",
            format: "currency-compact",
            accentColor: "var(--ifx-navy)",
          },
          {
            label: "Settled Today",
            value: summary?.settled_today ?? "0",
            format: "currency-compact",
            accentColor: "var(--ifx-success)",
          },
          {
            label: "Returned Today",
            value: summary?.returned_today ?? 0,
            format: "number",
            accentColor: "var(--ifx-error)",
          },
        ]}
      />

      <ConfigurableDataTable
        tableId="payment-batches"
        columns={COLUMNS}
        data={rows}
        getRowId={(r) => r.id}
        onRowClick={(row) => router.push(`/accounting/payments/${row.id}`)}
        loading={isLoading}
        emptyMessage="No payment batches found."
        pagination={{ pageSize: 25 }}
      />
    </div>
  );
}
