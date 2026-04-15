"use client";

import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";

interface CardholderIdRow {
  id: string;
  prefix: string;
  range_start: string;
  range_end: string;
  client: string;
  program: string;
  bin: string;
  pcn: string;
  group_code: string;
  status: "active" | "depleted" | "reserved";
  issued_count: number;
}

const MOCK_CARDHOLDER_IDS: CardholderIdRow[] = [
  { id: "c001", prefix: "CG", range_start: "CG00000001", range_end: "CG09999999", client: "Helix Biopharma", program: "CardioGuard Copay Program", bin: "610014", pcn: "IFX01", group_code: "CG2026", status: "active", issued_count: 4821 },
  { id: "c002", prefix: "NC", range_start: "NC00000001", range_end: "NC04999999", client: "Vantage Therapeutics", program: "NeuroClear Patient Support", bin: "610014", pcn: "IFX02", group_code: "NC2026", status: "active", issued_count: 2104 },
  { id: "c003", prefix: "OB", range_start: "OB00000001", range_end: "OB02999999", client: "Meridian Oncology", program: "OncoBridge Savings Card", bin: "610014", pcn: "IFX03", group_code: "OB2026", status: "active", issued_count: 892 },
  { id: "c004", prefix: "GA", range_start: "GA00000001", range_end: "GA09999999", client: "Stellar Endocrinology", program: "GlucoAssist Copay Card", bin: "610014", pcn: "IFX04", group_code: "GA2026", status: "active", issued_count: 6304 },
  { id: "c005", prefix: "RF", range_start: "RF00000001", range_end: "RF04999999", client: "Cascade Immunology", program: "RheumaFlex Patient Assistance", bin: "610014", pcn: "IFX05", group_code: "RF2026", status: "reserved", issued_count: 1240 },
];

const COLUMNS: Column<CardholderIdRow>[] = [
  { id: "prefix", header: "Prefix", accessor: (r) => r.prefix, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span>, width: 80 },
  { id: "range_start", header: "Range Start", accessor: (r) => r.range_start, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "range_end", header: "Range End", accessor: (r) => r.range_end, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "client", header: "Client", accessor: (r) => r.client, defaultVisible: true, sortable: true },
  { id: "program", header: "Program", accessor: (r) => r.program, defaultVisible: true, width: 220 },
  { id: "bin", header: "BIN", accessor: (r) => r.bin, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "pcn", header: "PCN", accessor: (r) => r.pcn, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "group_code", header: "Group", accessor: (r) => r.group_code, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "issued_count", header: "Issued", accessor: (r) => r.issued_count, format: "number", align: "right", sortable: true, defaultVisible: true },
  { id: "status", header: "Status", accessor: (r) => r.status, defaultVisible: true, cell: (v) => <StatusBadge status={String(v)} variant={v === "active" ? "success" : v === "depleted" ? "error" : "warning"} /> },
];

export default function CardholderIdsPage() {
  return (
    <DetailPageLayout
      title="Cardholder IDs"
      subtitle="Copay card cardholder ID ranges, BIN/PCN/Group assignments, and activation status."
    >
      <ConfigurableDataTable
        tableId="cardholder-ids"
        columns={COLUMNS}
        data={MOCK_CARDHOLDER_IDS}
        searchable
        exportable
        pagination={{ pageSize: 25 }}
        emptyMessage="No cardholder ID ranges configured."
      />
    </DetailPageLayout>
  );
}
