"use client";

import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";

interface NetworkRow {
  id: string;
  network_name: string;
  network_id: string;
  client: string;
  pharmacy_count: number;
  status: "active" | "inactive";
  effective_date: string;
}

const MOCK_NETWORKS: NetworkRow[] = [
  { id: "n001", network_name: "National Retail Network", network_id: "NRN-001", client: "Helix Biopharma", pharmacy_count: 62400, status: "active", effective_date: "2026-01-01" },
  { id: "n002", network_name: "Specialty Pharmacy Network", network_id: "SPN-002", client: "Meridian Oncology", pharmacy_count: 1200, status: "active", effective_date: "2026-01-01" },
  { id: "n003", network_name: "Mail Order Only", network_id: "MON-003", client: "Vantage Therapeutics", pharmacy_count: 45, status: "active", effective_date: "2026-01-01" },
  { id: "n004", network_name: "Preferred Retail", network_id: "PRN-004", client: "Stellar Endocrinology", pharmacy_count: 28000, status: "active", effective_date: "2026-02-01" },
  { id: "n005", network_name: "Legacy Network", network_id: "LGN-005", client: "Cascade Immunology", pharmacy_count: 400, status: "inactive", effective_date: "2025-01-01" },
];

const COLUMNS: Column<NetworkRow>[] = [
  { id: "network_name", header: "Network Name", accessor: (r) => r.network_name, defaultVisible: true, pinned: true, sortable: true },
  { id: "network_id", header: "Network ID", accessor: (r) => r.network_id, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "client", header: "Client", accessor: (r) => r.client, defaultVisible: true, sortable: true },
  { id: "pharmacy_count", header: "Pharmacies", accessor: (r) => r.pharmacy_count, format: "number", align: "right", sortable: true, defaultVisible: true },
  { id: "status", header: "Status", accessor: (r) => r.status, defaultVisible: true, cell: (v) => <StatusBadge status={String(v)} variant={v === "active" ? "success" : "neutral"} /> },
  { id: "effective_date", header: "Effective Date", accessor: (r) => r.effective_date, format: "date", sortable: true, defaultVisible: true },
];

export default function PreferredNetworksPage() {
  return (
    <DetailPageLayout
      title="Preferred Networks"
      subtitle="Preferred network configuration and pharmacy inclusion rules per client."
    >
      <ConfigurableDataTable
        tableId="preferred-networks"
        columns={COLUMNS}
        data={MOCK_NETWORKS}
        searchable
        exportable
        pagination={{ pageSize: 25 }}
        emptyMessage="No networks configured."
      />
    </DetailPageLayout>
  );
}
