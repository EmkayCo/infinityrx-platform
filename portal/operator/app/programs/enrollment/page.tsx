"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiGet } from "@shared/lib/api-client";
import type { EnrollmentRow } from "@shared/lib/mock-data/seed/programs";

interface EnrollmentAnalyticsResponse {
  enrollments: EnrollmentRow[];
  total: number;
  by_program: {
    program_id: string;
    program_name: string;
    active: number;
    inactive: number;
  }[];
}

const COLUMNS: Column<EnrollmentRow>[] = [
  { id: "member_id", header: "Member ID", accessor: (r) => r.member_id, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span>, pinned: true },
  { id: "program_name", header: "Program", accessor: (r) => r.program_name, defaultVisible: true, sortable: true },
  { id: "enrollment_date", header: "Enrollment Date", accessor: (r) => r.enrollment_date, format: "date", sortable: true, defaultVisible: true },
  { id: "first_fill_date", header: "First Fill Date", accessor: (r) => r.first_fill_date ?? "—", format: "date", sortable: true, defaultVisible: true },
  { id: "fills_to_date", header: "Fills to Date", accessor: (r) => r.fills_to_date, format: "number", align: "right", sortable: true, defaultVisible: true },
  { id: "spend_to_date", header: "Spend to Date", accessor: (r) => r.spend_to_date, format: "currency", align: "right", sortable: true, defaultVisible: true },
  { id: "status", header: "Status", accessor: (r) => r.status, defaultVisible: true, cell: (v) => <StatusBadge status={String(v)} variant={v === "active" ? "success" : "neutral"} /> },
  { id: "source", header: "Source", accessor: (r) => r.source, defaultVisible: false },
];

export default function EnrollmentPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["enrollment-analytics"],
    queryFn: () => apiGet<EnrollmentAnalyticsResponse>("/api/v1/programs/enrollment/analytics"),
    staleTime: 60_000,
  });

  const enrollments = data?.enrollments ?? [];
  const byProgram = data?.by_program ?? [];

  const summaryCards = [
    {
      label: "Total Enrollments",
      value: enrollments.length,
      format: "number" as const,
      href: "/programs",
    },
    {
      label: "Active",
      value: enrollments.filter((e) => e.status === "active").length,
      format: "number" as const,
      href: "/programs",
      accentColor: "var(--ifx-success)",
    },
    {
      label: "Inactive",
      value: enrollments.filter((e) => e.status === "inactive").length,
      format: "number" as const,
      href: "/programs",
      accentColor: "var(--ifx-gray-300)",
    },
    {
      label: "With First Fill",
      value: enrollments.filter((e) => e.first_fill_date).length,
      format: "number" as const,
      href: "/claims",
      accentColor: "var(--ifx-blue)",
    },
  ];

  const chartData = byProgram.map((p) => ({
    name: p.program_name.split(" ").slice(0, 2).join(" "),
    Active: p.active,
    Inactive: p.inactive,
  }));

  return (
    <DetailPageLayout
      title="Enrollment"
      subtitle="Cross-program enrollment analytics — new enrollments, active patients, and source channels."
      summaryCards={summaryCards}
      summaryColumns={4}
    >
      {/* Chart */}
      <div className="rounded-lg bg-white ifx-card-shadow p-4">
        <h3 className="text-sm font-bold text-ifx-gray-900 mb-4">
          Enrollments by Program
        </h3>
        {isLoading ? (
          <div className="h-64 shimmer rounded" />
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartData} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--ifx-gray-100)" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="Active" fill="var(--ifx-navy)" radius={[3, 3, 0, 0]} />
              <Bar dataKey="Inactive" fill="var(--ifx-gray-300)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Enrollment table */}
      <ConfigurableDataTable
        tableId="enrollment-all"
        columns={COLUMNS}
        data={enrollments}
        loading={isLoading}
        searchable
        exportable
        pagination={{ pageSize: 25 }}
        emptyMessage="No enrollment records found."
      />
    </DetailPageLayout>
  );
}
