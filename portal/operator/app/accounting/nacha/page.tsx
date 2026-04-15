"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Send } from "lucide-react";
import { apiGet, apiPost } from "@shared/lib/api-client";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { KpiCardRow } from "@/components/ui/kpi-card-row";

interface NachaFile {
  id: string;
  filename: string;
  status: string;
  batch_count?: number;
  entry_count?: number;
  total_amount: string;
  generated_at: string;
  transmitted_at?: string | null;
  ack_status?: string;
  download_url?: string;
  effective_date?: string;
  company_name?: string;
  bank_name?: string;
}

const COLUMNS: Column<NachaFile>[] = [
  {
    id: "filename",
    header: "Filename",
    accessor: (r) => r.filename,
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
    id: "ack_status",
    header: "ACK Status",
    accessor: (r) => r.ack_status ?? "pending",
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
    id: "entry_count",
    header: "Entries",
    accessor: (r) => r.entry_count,
    format: "number",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "generated_at",
    header: "Generated",
    accessor: (r) => r.generated_at,
    format: "date",
    defaultVisible: true,
  },
  {
    id: "transmitted_at",
    header: "Transmitted",
    accessor: (r) => r.transmitted_at,
    format: "date",
    defaultVisible: true,
  },
  {
    id: "effective_date",
    header: "Effective Date",
    accessor: (r) => r.effective_date,
    format: "date",
    defaultVisible: false,
  },
  {
    id: "company_name",
    header: "Company",
    accessor: (r) => r.company_name,
    defaultVisible: false,
  },
  {
    id: "bank_name",
    header: "Bank",
    accessor: (r) => r.bank_name,
    defaultVisible: false,
  },
  {
    id: "batch_count",
    header: "Batches",
    accessor: (r) => r.batch_count,
    format: "number",
    align: "right",
    defaultVisible: false,
  },
];

export default function NachaPage() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<{ items: NachaFile[]; total: number }>({
    queryKey: ["nacha-files"],
    queryFn: () => apiGet<{ items: NachaFile[]; total: number }>("/nacha"),
  });

  const transmitMutation = useMutation({
    mutationFn: (fileId: string) => apiPost(`/nacha/${fileId}/transmit`, {}),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["nacha-files"] }),
  });

  const rows = data?.items ?? [];
  const pendingTransmit = rows.filter((r) => !r.transmitted_at);
  const totalAmount = rows.reduce((s, r) => s + Number(r.total_amount ?? 0), 0).toFixed(2);
  const acknowledged = rows.filter((r) => r.ack_status === "acknowledged").length;

  const COLUMNS_WITH_ACTIONS: Column<NachaFile>[] = [
    ...COLUMNS,
    {
      id: "actions",
      header: "Actions",
      accessor: (r) => r.id,
      defaultVisible: true,
      cell: (_value, row) => (
        <div className="flex items-center gap-2">
          {row.download_url && (
            <a
              href={row.download_url}
              className="inline-flex items-center gap-1 text-xs font-medium text-ifx-blue hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              <Download className="h-3.5 w-3.5" />
              Download
            </a>
          )}
          {!row.transmitted_at && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); transmitMutation.mutate(row.id); }}
              className="inline-flex items-center gap-1 text-xs font-medium text-ifx-navy hover:underline"
            >
              <Send className="h-3.5 w-3.5" />
              Transmit
            </button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <header>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
          Accounting
        </span>
        <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">NACHA Files</h1>
        <p className="mt-1 text-sm text-ifx-gray-400">
          NACHA ACH file generation history, transmission status, and download management.
        </p>
      </header>

      <KpiCardRow
        cards={[
          {
            label: "Total Files",
            value: data?.total ?? rows.length,
            format: "number",
            accentColor: "var(--ifx-navy)",
          },
          {
            label: "Pending Transmit",
            value: pendingTransmit.length,
            format: "number",
            accentColor: "var(--ifx-warning)",
          },
          {
            label: "Acknowledged",
            value: acknowledged,
            format: "number",
            accentColor: "var(--ifx-success)",
          },
          {
            label: "Total Amount",
            value: totalAmount,
            format: "currency-compact",
            accentColor: "var(--ifx-blue)",
          },
        ]}
      />

      <ConfigurableDataTable
        tableId="nacha-files"
        columns={COLUMNS_WITH_ACTIONS}
        data={rows}
        getRowId={(r) => r.id}
        loading={isLoading}
        emptyMessage="No NACHA files found."
        pagination={{ pageSize: 25 }}
      />
    </div>
  );
}
