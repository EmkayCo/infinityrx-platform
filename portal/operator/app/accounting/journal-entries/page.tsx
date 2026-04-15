"use client";

import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@shared/lib/api-client";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { KpiCardRow } from "@/components/ui/kpi-card-row";

interface JournalEntry {
  id: string;
  date: string;
  type: "AP" | "AR" | "Transfer" | "Fee" | "Adjustment";
  description?: string;
  debit_account?: string;
  credit_account?: string;
  amount: string;
  qb_class?: string;
  cycle_id?: string;
  cycle_period?: string;
  status?: string;
  reference?: string;
  created_by?: string;
  created_at?: string;
}

interface JournalSummary {
  total_entries: number;
  total_ap: string;
  total_ar: string;
  total_fees: string;
}

const COLUMNS: Column<JournalEntry>[] = [
  {
    id: "date",
    header: "Date",
    accessor: (r) => r.date,
    format: "date",
    pinned: true,
    defaultVisible: true,
  },
  {
    id: "type",
    header: "Type",
    accessor: (r) => r.type,
    defaultVisible: true,
  },
  {
    id: "description",
    header: "Description",
    accessor: (r) => r.description,
    defaultVisible: true,
  },
  {
    id: "debit_account",
    header: "Debit Account",
    accessor: (r) => r.debit_account,
    defaultVisible: true,
  },
  {
    id: "credit_account",
    header: "Credit Account",
    accessor: (r) => r.credit_account,
    defaultVisible: true,
  },
  {
    id: "amount",
    header: "Amount",
    accessor: (r) => r.amount,
    format: "currency",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "qb_class",
    header: "QB Class",
    accessor: (r) => r.qb_class,
    defaultVisible: true,
  },
  {
    id: "cycle_period",
    header: "Cycle Period",
    accessor: (r) => r.cycle_period,
    defaultVisible: false,
  },
  {
    id: "reference",
    header: "Reference",
    accessor: (r) => r.reference,
    defaultVisible: false,
  },
  {
    id: "status",
    header: "Status",
    accessor: (r) => r.status ?? "posted",
    format: "status",
    defaultVisible: false,
  },
  {
    id: "created_by",
    header: "Created By",
    accessor: (r) => r.created_by,
    defaultVisible: false,
  },
  {
    id: "created_at",
    header: "Created At",
    accessor: (r) => r.created_at,
    format: "date",
    defaultVisible: false,
  },
];

export default function JournalEntriesPage() {
  const { data: summary } = useQuery<JournalSummary>({
    queryKey: ["journal-summary"],
    queryFn: () => apiGet<JournalSummary>("/api/v1/accounting/journal-entries/summary"),
  });

  const { data, isLoading } = useQuery<{ items: JournalEntry[]; total: number }>({
    queryKey: ["journal-entries"],
    queryFn: () => apiGet<{ items: JournalEntry[]; total: number }>("/api/v1/accounting/journal-entries"),
  });

  const rows = data?.items ?? [];
  const totalAp = rows.filter((r) => r.type === "AP").reduce((s, r) => s + Number(r.amount), 0).toFixed(2);
  const totalAr = rows.filter((r) => r.type === "AR").reduce((s, r) => s + Number(r.amount), 0).toFixed(2);
  const totalFees = rows.filter((r) => r.type === "Fee").reduce((s, r) => s + Number(r.amount), 0).toFixed(2);

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
          Accounting
        </span>
        <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Journal Entries</h1>
        <p className="mt-1 text-sm text-ifx-gray-400">
          Virtual transfer journal entries with AP/AR accounts and QuickBooks class assignments.
        </p>
      </header>

      <KpiCardRow
        cards={[
          {
            label: "Total Entries",
            value: summary?.total_entries ?? data?.total ?? rows.length,
            format: "number",
            accentColor: "var(--ifx-navy)",
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
          {
            label: "Total Fees",
            value: summary?.total_fees ?? totalFees,
            format: "currency-compact",
            accentColor: "var(--ifx-blue)",
          },
        ]}
      />

      <ConfigurableDataTable
        tableId="journal-entries"
        columns={COLUMNS}
        data={rows}
        getRowId={(r) => r.id}
        loading={isLoading}
        emptyMessage="No journal entries found."
        pagination={{ pageSize: 50, pageSizeOptions: [25, 50, 100] }}
        exportable
      />
    </div>
  );
}
