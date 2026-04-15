"use client";

import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";

interface ExceptionRow {
  id: string;
  rule_type: string;
  entity_type: "pharmacy" | "member" | "ndc";
  entity_value: string;
  client: string;
  reason: string;
  status: "active" | "expired";
  effective_date: string;
  expiry_date: string | null;
}

const MOCK_EXCEPTIONS: ExceptionRow[] = [
  { id: "ex001", rule_type: "Pharmacy Override", entity_type: "pharmacy", entity_value: "1234567890", client: "Helix Biopharma", reason: "Manual approval from medical director", status: "active", effective_date: "2026-01-15", expiry_date: "2026-06-30" },
  { id: "ex002", rule_type: "NDC Exclusion", entity_type: "ndc", entity_value: "12345678901", client: "Stellar Endocrinology", reason: "Formulary exclusion — covered under separate program", status: "active", effective_date: "2026-02-01", expiry_date: null },
  { id: "ex003", rule_type: "Member Override", entity_type: "member", entity_value: "MBR-2026-0041", client: "Meridian Oncology", reason: "Compassionate use — exceeds annual benefit cap", status: "active", effective_date: "2026-03-10", expiry_date: "2026-12-31" },
  { id: "ex004", rule_type: "Pharmacy Override", entity_type: "pharmacy", entity_value: "9876543210", client: "Vantage Therapeutics", reason: "340B exception — manually approved", status: "expired", effective_date: "2025-06-01", expiry_date: "2026-01-01" },
];

const COLUMNS: Column<ExceptionRow>[] = [
  { id: "rule_type", header: "Rule Type", accessor: (r) => r.rule_type, defaultVisible: true, pinned: true, sortable: true },
  { id: "entity_type", header: "Entity Type", accessor: (r) => r.entity_type, defaultVisible: true },
  { id: "entity_value", header: "Entity ID / Value", accessor: (r) => r.entity_value, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "client", header: "Client", accessor: (r) => r.client, defaultVisible: true, sortable: true },
  { id: "reason", header: "Reason", accessor: (r) => r.reason, defaultVisible: true, width: 260 },
  { id: "status", header: "Status", accessor: (r) => r.status, defaultVisible: true, cell: (v) => <StatusBadge status={String(v)} variant={v === "active" ? "success" : "neutral"} /> },
  { id: "effective_date", header: "Effective", accessor: (r) => r.effective_date, format: "date", sortable: true, defaultVisible: true },
  { id: "expiry_date", header: "Expiry", accessor: (r) => r.expiry_date ?? "—", sortable: true, defaultVisible: true },
];

export default function ExceptionsPage() {
  return (
    <DetailPageLayout
      title="Exceptions"
      subtitle="Client-specific exception rules — blocked pharmacies, member overrides, NDC exclusions."
    >
      <ConfigurableDataTable
        tableId="exceptions"
        columns={COLUMNS}
        data={MOCK_EXCEPTIONS}
        searchable
        exportable
        pagination={{ pageSize: 25 }}
        emptyMessage="No exceptions configured."
      />
    </DetailPageLayout>
  );
}
