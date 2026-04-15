"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { PlusCircle } from "lucide-react";
import Link from "next/link";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiGet } from "@shared/lib/api-client";
import type { ClientRow } from "@shared/lib/mock-data/seed/programs";

interface ClientListResponse {
  clients: ClientRow[];
  total: number;
}

const COLUMNS: Column<ClientRow>[] = [
  {
    id: "company_name",
    header: "Company Name",
    accessor: (r) => r.company_name,
    sortable: true,
    defaultVisible: true,
    pinned: true,
    width: 200,
  },
  {
    id: "bin",
    header: "BIN",
    accessor: (r) => r.bin,
    defaultVisible: true,
    cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span>,
    width: 100,
  },
  {
    id: "federal_id",
    header: "Federal ID",
    accessor: (r) => r.federal_id,
    defaultVisible: true,
    cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span>,
  },
  {
    id: "city",
    header: "City",
    accessor: (r) => r.city,
    sortable: true,
    defaultVisible: true,
  },
  {
    id: "state",
    header: "State",
    accessor: (r) => r.state,
    sortable: true,
    defaultVisible: true,
    width: 80,
  },
  {
    id: "status",
    header: "Status",
    accessor: (r) => r.status,
    defaultVisible: true,
    cell: (v) => (
      <StatusBadge
        status={String(v)}
        variant={v === "enabled" ? "success" : "neutral"}
      />
    ),
  },
  {
    id: "programs_count",
    header: "Programs",
    accessor: (r) => r.programs_count,
    format: "number",
    sortable: true,
    defaultVisible: true,
    align: "right",
  },
  {
    id: "contact_name",
    header: "Contact",
    accessor: (r) => r.contact_name,
    defaultVisible: false,
  },
  {
    id: "phone",
    header: "Phone",
    accessor: (r) => r.phone,
    defaultVisible: false,
  },
  {
    id: "email",
    header: "Email",
    accessor: (r) => r.email,
    defaultVisible: false,
  },
];

export default function CompaniesPage() {
  const router = useRouter();

  const { data, isLoading } = useQuery({
    queryKey: ["clients"],
    queryFn: () => apiGet<ClientListResponse>("/api/v1/clients"),
    staleTime: 60_000,
  });

  const clients = data?.clients ?? [];

  return (
    <DetailPageLayout
      title="Companies"
      subtitle="Manufacturer client companies — details, profile, programs, statement providers, blocked providers."
      actions={
        <Link
          href="/clients/new"
          className="inline-flex items-center gap-2 rounded-md bg-[var(--ifx-navy)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--ifx-navy-dark)] transition-colors"
        >
          <PlusCircle className="h-4 w-4" />
          New Client
        </Link>
      }
    >
      <ConfigurableDataTable
        tableId="companies"
        columns={COLUMNS}
        data={clients}
        loading={isLoading}
        searchable
        exportable
        selectable
        pagination={{ pageSize: 25 }}
        onRowClick={(row) => router.push(`/clients/${row.id}`)}
        emptyMessage="No client companies found."
      />
    </DetailPageLayout>
  );
}
