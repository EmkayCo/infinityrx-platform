"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@shared/lib/api-client";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { KpiCardRow } from "@/components/ui/kpi-card-row";

interface Invoice {
  id: string;
  invoice_number: string;
  client_name?: string;
  cycle_id?: string;
  status: string;
  total_amount: string;
  due_date?: string;
  issued_at?: string;
  paid_at?: string | null;
  pdf_url?: string | null;
}

interface InvoiceSummary {
  total: number;
  outstanding: string;
  overdue_count: number;
  paid_this_month: string;
}

const COLUMNS: Column<Invoice>[] = [
  {
    id: "invoice_number",
    header: "Invoice #",
    accessor: (r) => r.invoice_number,
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
    id: "total_amount",
    header: "Total Amount",
    accessor: (r) => r.total_amount,
    format: "currency",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "issued_at",
    header: "Period / Issued",
    accessor: (r) => r.issued_at,
    format: "date",
    defaultVisible: true,
  },
  {
    id: "due_date",
    header: "Due Date",
    accessor: (r) => r.due_date,
    format: "date",
    defaultVisible: true,
  },
  {
    id: "paid_at",
    header: "Paid Date",
    accessor: (r) => r.paid_at,
    format: "date",
    defaultVisible: true,
  },
  {
    id: "pdf_url",
    header: "PDF",
    accessor: (r) => r.pdf_url ? "Available" : "—",
    defaultVisible: false,
  },
];

export default function InvoicesPage() {
  const router = useRouter();

  const { data: summary } = useQuery<InvoiceSummary>({
    queryKey: ["invoices-summary"],
    queryFn: () => apiGet<InvoiceSummary>("/api/v1/accounting/invoices/summary"),
  });

  const { data, isLoading } = useQuery<{ items: Invoice[]; total: number }>({
    queryKey: ["invoices"],
    queryFn: () => apiGet<{ items: Invoice[]; total: number }>("/billing/v1/invoices"),
  });

  const rows = data?.items ?? [];
  const overdueCount = rows.filter((r) => r.status === "overdue").length;
  const outstandingTotal = rows
    .filter((r) => ["sent", "overdue"].includes(r.status))
    .reduce((s, r) => s + Number(r.total_amount), 0)
    .toFixed(2);

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
          Accounting
        </span>
        <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Invoices</h1>
        <p className="mt-1 text-sm text-ifx-gray-400">
          Manufacturer invoices — draft, send, mark paid, and download PDFs.
        </p>
      </header>

      <KpiCardRow
        cards={[
          {
            label: "Total Invoices",
            value: data?.total ?? rows.length,
            format: "number",
            accentColor: "var(--ifx-navy)",
          },
          {
            label: "Outstanding",
            value: summary?.outstanding ?? outstandingTotal,
            format: "currency-compact",
            accentColor: "var(--ifx-warning)",
          },
          {
            label: "Overdue",
            value: summary?.overdue_count ?? overdueCount,
            format: "number",
            accentColor: "var(--ifx-error)",
          },
          {
            label: "Paid This Month",
            value: summary?.paid_this_month ?? "0",
            format: "currency-compact",
            accentColor: "var(--ifx-success)",
          },
        ]}
      />

      <ConfigurableDataTable
        tableId="invoices"
        columns={COLUMNS}
        data={rows}
        getRowId={(r) => r.id}
        onRowClick={(row) => router.push(`/accounting/invoices/${row.id}`)}
        loading={isLoading}
        emptyMessage="No invoices found."
        pagination={{ pageSize: 25 }}
      />
    </div>
  );
}
