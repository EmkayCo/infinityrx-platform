"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { PlusCircle } from "lucide-react";
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
  {
    id: "name",
    header: "Program Name",
    accessor: (r) => r.name,
    sortable: true,
    defaultVisible: true,
    pinned: true,
    width: 220,
  },
  {
    id: "manufacturer",
    header: "Manufacturer",
    accessor: (r) => r.manufacturer,
    sortable: true,
    defaultVisible: true,
  },
  {
    id: "drugs",
    header: "Drug(s)",
    accessor: (r) => r.drugs.map((d) => d.name).join(", "),
    sortable: false,
    defaultVisible: true,
    width: 200,
  },
  {
    id: "status",
    header: "Status",
    accessor: (r) => r.status,
    defaultVisible: true,
    cell: (v) => (
      <StatusBadge
        status={String(v)}
        variant={
          v === "active" ? "success" : v === "paused" ? "warning" : "neutral"
        }
      />
    ),
  },
  {
    id: "active_enrollments",
    header: "Active Enrollments",
    accessor: (r) => r.active_enrollments,
    format: "number",
    sortable: true,
    defaultVisible: true,
    align: "right",
  },
  {
    id: "total_claims_ytd",
    header: "Total Claims (YTD)",
    accessor: (r) => r.total_claims_ytd,
    format: "number",
    sortable: true,
    defaultVisible: true,
    align: "right",
  },
  {
    id: "total_spend_ytd",
    header: "Total Spend (YTD)",
    accessor: (r) => r.total_spend_ytd,
    format: "currency",
    sortable: true,
    defaultVisible: true,
    align: "right",
  },
  {
    id: "gtn_ratio",
    header: "GTN Ratio",
    accessor: (r) => r.gtn_ratio,
    sortable: true,
    defaultVisible: true,
    align: "right",
    cell: (v) => <span>{String(v)}%</span>,
  },
  {
    id: "budget_remaining",
    header: "Budget Remaining",
    accessor: (r) => r.budget_remaining,
    format: "currency",
    sortable: true,
    defaultVisible: true,
    align: "right",
  },
  {
    id: "effective_date",
    header: "Effective Date",
    accessor: (r) => r.effective_date,
    format: "date",
    sortable: true,
    defaultVisible: false,
  },
  {
    id: "term_date",
    header: "Term Date",
    accessor: (r) => r.term_date ?? "—",
    sortable: true,
    defaultVisible: false,
  },
];

export default function ProgramsOverviewPage() {
  const router = useRouter();

  const { data, isLoading } = useQuery({
    queryKey: ["programs"],
    queryFn: () => apiGet<ProgramListResponse>("/api/v1/programs"),
    staleTime: 60_000,
  });

  const programs = data?.programs ?? [];

  return (
    <DetailPageLayout
      title="Program Overview"
      subtitle="Manufacturer copay assistance programs — enrollments, spend, GTN ratio, active alerts."
      actions={
        <a
          href="/programs/config"
          className="inline-flex items-center gap-2 rounded-md bg-[var(--ifx-navy)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--ifx-navy-dark)] transition-colors"
        >
          <PlusCircle className="h-4 w-4" />
          New Program
        </a>
      }
    >
      <ConfigurableDataTable
        tableId="programs-overview"
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
