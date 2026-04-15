"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiGet } from "@shared/lib/api-client";
import type { ProgramRow } from "@shared/lib/mock-data/seed/programs";

interface ProgramListResponse {
  programs: ProgramRow[];
  total: number;
}

const COLUMNS: Column<ProgramRow>[] = [
  { id: "manufacturer", header: "Manufacturer", accessor: (r) => r.manufacturer, sortable: true, defaultVisible: true, pinned: true },
  { id: "name", header: "Program Name", accessor: (r) => r.name, sortable: true, defaultVisible: true, width: 220 },
  { id: "status", header: "Status", accessor: (r) => r.status, defaultVisible: true, cell: (v) => <StatusBadge status={String(v)} variant={v === "active" ? "success" : v === "paused" ? "warning" : "neutral"} /> },
  { id: "active_enrollments", header: "Active Enrollments", accessor: (r) => r.active_enrollments, format: "number", align: "right", sortable: true, defaultVisible: true },
  { id: "total_claims_ytd", header: "Claims (YTD)", accessor: (r) => r.total_claims_ytd, format: "number", align: "right", sortable: true, defaultVisible: true },
  { id: "total_spend_ytd", header: "Spend (YTD)", accessor: (r) => r.total_spend_ytd, format: "currency", align: "right", sortable: true, defaultVisible: true },
  { id: "gtn_ratio", header: "GTN Ratio", accessor: (r) => r.gtn_ratio, defaultVisible: true, align: "right", cell: (v) => <span>{String(v)}%</span> },
  { id: "budget_remaining", header: "Budget Remaining", accessor: (r) => r.budget_remaining, format: "currency", align: "right", sortable: true, defaultVisible: true },
];

export default function ClientProgramsPage() {
  const router = useRouter();

  const { data, isLoading } = useQuery({
    queryKey: ["programs"],
    queryFn: () => apiGet<ProgramListResponse>("/api/v1/programs"),
    staleTime: 60_000,
  });

  const programs = data?.programs ?? [];

  return (
    <DetailPageLayout
      title="Client Programs"
      subtitle="Cross-client view of all manufacturer copay programs grouped by company."
    >
      <ConfigurableDataTable
        tableId="client-programs-all"
        columns={COLUMNS}
        data={programs}
        loading={isLoading}
        searchable
        exportable
        pagination={{ pageSize: 25 }}
        onRowClick={(row) => router.push(`/programs/${row.id}`)}
        emptyMessage="No programs found."
      />
    </DetailPageLayout>
  );
}
