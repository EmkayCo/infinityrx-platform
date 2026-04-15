"use client";

import { useQuery } from "@tanstack/react-query";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiGet } from "@shared/lib/api-client";
import type { MasterFeeRow } from "@shared/lib/mock-data/seed/programs";

interface MasterFeeResponse {
  fees: MasterFeeRow[];
  total: number;
}

const UNIT_LABELS: Record<string, string> = {
  per_claim: "Per Claim",
  per_transaction: "Per Transaction",
  monthly: "Monthly",
  one_time: "One-Time",
};

const COLUMNS: Column<MasterFeeRow>[] = [
  {
    id: "description",
    header: "Fee Description",
    accessor: (r) => r.description,
    defaultVisible: true,
    pinned: true,
    sortable: true,
    width: 280,
  },
  {
    id: "fee_type",
    header: "Fee Type",
    accessor: (r) => r.fee_type,
    defaultVisible: true,
    cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span>,
  },
  {
    id: "default_rate",
    header: "Default Rate",
    accessor: (r) => r.default_rate,
    format: "currency",
    align: "right",
    sortable: true,
    defaultVisible: true,
  },
  {
    id: "unit",
    header: "Unit",
    accessor: (r) => UNIT_LABELS[r.unit] ?? r.unit,
    defaultVisible: true,
  },
  {
    id: "effective_date",
    header: "Effective Date",
    accessor: (r) => r.effective_date,
    format: "date",
    sortable: true,
    defaultVisible: true,
  },
  {
    id: "active",
    header: "Status",
    accessor: (r) => r.active,
    defaultVisible: true,
    cell: (v) => (
      <StatusBadge
        status={v ? "active" : "inactive"}
        variant={v ? "success" : "neutral"}
      />
    ),
  },
];

export default function FeeConfigPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["master-fee-schedule"],
    queryFn: () => apiGet<MasterFeeResponse>("/api/v1/clients/fees/master"),
    staleTime: 300_000,
  });

  const fees = data?.fees ?? [];

  return (
    <DetailPageLayout
      title="Fee Configuration"
      subtitle="Master fee schedule — setup fees, transaction fees, dispensing fees, and service fees for all clients."
    >
      <ConfigurableDataTable
        tableId="fee-config-master"
        columns={COLUMNS}
        data={fees}
        loading={isLoading}
        searchable
        exportable
        pagination={{ pageSize: 25 }}
        emptyMessage="No fee schedule entries found."
      />
    </DetailPageLayout>
  );
}
