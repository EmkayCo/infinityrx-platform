"use client";

import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";

interface StateRuleRow {
  id: string;
  state_code: string;
  state_name: string;
  client: string;
  rule_type: string;
  description: string;
  status: "active" | "inactive";
  effective_date: string;
}

const MOCK_STATE_RULES: StateRuleRow[] = [
  { id: "sr001", state_code: "CA", state_name: "California", client: "Helix Biopharma", rule_type: "Eligibility Restriction", description: "CA patient assistance rules — state-funded programs must be offered first", status: "active", effective_date: "2026-01-01" },
  { id: "sr002", state_code: "NY", state_name: "New York", client: "Meridian Oncology", rule_type: "Maximum Copay", description: "NY State caps patient copay at $0 for certain oncology drugs — copay card supplement", status: "active", effective_date: "2026-01-01" },
  { id: "sr003", state_code: "TX", state_name: "Texas", client: "Stellar Endocrinology", rule_type: "Prior Authorization Override", description: "TX-specific PA override process for diabetes medications", status: "active", effective_date: "2026-03-01" },
  { id: "sr004", state_code: "MA", state_name: "Massachusetts", client: "Vantage Therapeutics", rule_type: "Formulary Exception", description: "MA step therapy exception rules per MA regulations", status: "active", effective_date: "2026-01-01" },
  { id: "sr005", state_code: "FL", state_name: "Florida", client: "Helix Biopharma", rule_type: "Eligibility Restriction", description: "FL Medicaid exclusion — patients with Medicaid are ineligible", status: "inactive", effective_date: "2025-01-01" },
];

const COLUMNS: Column<StateRuleRow>[] = [
  { id: "state_code", header: "State", accessor: (r) => r.state_code, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span>, width: 80, sortable: true, pinned: true },
  { id: "state_name", header: "State Name", accessor: (r) => r.state_name, defaultVisible: true, sortable: true },
  { id: "client", header: "Client", accessor: (r) => r.client, defaultVisible: true, sortable: true },
  { id: "rule_type", header: "Rule Type", accessor: (r) => r.rule_type, defaultVisible: true, sortable: true },
  { id: "description", header: "Description", accessor: (r) => r.description, defaultVisible: true, width: 300 },
  { id: "status", header: "Status", accessor: (r) => r.status, defaultVisible: true, cell: (v) => <StatusBadge status={String(v)} variant={v === "active" ? "success" : "neutral"} /> },
  { id: "effective_date", header: "Effective Date", accessor: (r) => r.effective_date, format: "date", sortable: true, defaultVisible: true },
];

export default function StateRulesPage() {
  return (
    <DetailPageLayout
      title="State Rules"
      subtitle="State-specific regulatory rules and client eligibility requirements by jurisdiction."
    >
      <ConfigurableDataTable
        tableId="state-rules"
        columns={COLUMNS}
        data={MOCK_STATE_RULES}
        searchable
        exportable
        pagination={{ pageSize: 25 }}
        emptyMessage="No state rules configured."
      />
    </DetailPageLayout>
  );
}
