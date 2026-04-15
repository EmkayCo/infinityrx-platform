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
  LineChart,
  Line,
} from "recharts";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { apiGet } from "@shared/lib/api-client";

interface BudgetProgram {
  program_id: string;
  program_name: string;
  manufacturer: string;
  annual_budget: string;
  spent: string;
  remaining: string;
  projected_annual: string;
  variance: string;
}

interface BudgetMonthlyRow {
  month: string;
  budget: string;
  actual: string;
  program_id: string;
}

interface BudgetSummaryResponse {
  programs: BudgetProgram[];
  monthly: BudgetMonthlyRow[];
}

const COLUMNS: Column<BudgetProgram>[] = [
  { id: "program_name", header: "Program", accessor: (r) => r.program_name, defaultVisible: true, sortable: true, pinned: true, width: 220 },
  { id: "manufacturer", header: "Manufacturer", accessor: (r) => r.manufacturer, defaultVisible: true, sortable: true },
  { id: "annual_budget", header: "Annual Budget", accessor: (r) => r.annual_budget, format: "currency", align: "right", sortable: true, defaultVisible: true },
  { id: "spent", header: "Spent to Date", accessor: (r) => r.spent, format: "currency", align: "right", sortable: true, defaultVisible: true },
  { id: "remaining", header: "Remaining", accessor: (r) => r.remaining, format: "currency", align: "right", sortable: true, defaultVisible: true },
  { id: "projected_annual", header: "Projected Year-End", accessor: (r) => r.projected_annual, format: "currency", align: "right", sortable: true, defaultVisible: true },
  { id: "variance", header: "Variance", accessor: (r) => r.variance, format: "currency", align: "right", sortable: true, defaultVisible: true },
];

export default function BudgetPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["budget-summary"],
    queryFn: () => apiGet<BudgetSummaryResponse>("/api/v1/programs/budget/summary"),
    staleTime: 60_000,
  });

  const programs = data?.programs ?? [];
  const monthly = data?.monthly ?? [];

  const totalBudget = programs.reduce((s, p) => s + parseFloat(p.annual_budget), 0);
  const totalSpent = programs.reduce((s, p) => s + parseFloat(p.spent), 0);
  const totalRemaining = programs.reduce((s, p) => s + parseFloat(p.remaining), 0);
  const totalProjected = programs.reduce((s, p) => s + parseFloat(p.projected_annual), 0);

  const summaryCards = [
    { label: "Total Annual Budget", value: totalBudget.toFixed(2), format: "currency-compact" as const, href: "/programs", accentColor: "var(--ifx-navy)" },
    { label: "Spent to Date", value: totalSpent.toFixed(2), format: "currency-compact" as const, href: "/accounting/cycles", accentColor: "var(--ifx-pink)" },
    { label: "Remaining", value: totalRemaining.toFixed(2), format: "currency-compact" as const, href: "/programs", accentColor: "var(--ifx-success)" },
    { label: "Projected Year-End", value: totalProjected.toFixed(2), format: "currency-compact" as const, href: "/programs", accentColor: "var(--ifx-blue)" },
  ];

  const monthMap: Record<string, { Budget: number; Actual: number }> = {};
  for (const row of monthly) {
    if (!monthMap[row.month]) monthMap[row.month] = { Budget: 0, Actual: 0 };
    monthMap[row.month].Budget += parseFloat(row.budget);
    monthMap[row.month].Actual += parseFloat(row.actual);
  }
  const aggregatedMonthly = Object.entries(monthMap).map(([month, vals]) => ({
    month,
    Budget: vals.Budget,
    Actual: vals.Actual,
  }));

  return (
    <DetailPageLayout
      title="Budget &amp; Forecast"
      subtitle="Cross-program budget overview — budget vs. actual, burn rate, and projected year-end spend."
      summaryCards={summaryCards}
      summaryColumns={4}
    >
      <div className="rounded-lg bg-white ifx-card-shadow p-4">
        <h3 className="text-sm font-bold text-ifx-gray-900 mb-4">
          Budget vs. Actual — All Programs (Monthly)
        </h3>
        {isLoading ? (
          <div className="h-64 shimmer rounded" />
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={aggregatedMonthly} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--ifx-gray-100)" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => `$${(v / 1000000).toFixed(1)}M`} />
              <Tooltip formatter={(v) => typeof v === "number" ? `$${(v / 1000000).toFixed(2)}M` : String(v)} />
              <Legend />
              <Bar dataKey="Budget" fill="var(--ifx-navy)" radius={[3, 3, 0, 0]} />
              <Bar dataKey="Actual" fill="var(--ifx-pink)" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="rounded-lg bg-white ifx-card-shadow p-4">
        <h3 className="text-sm font-bold text-ifx-gray-900 mb-4">Cumulative Spend Trend</h3>
        {isLoading ? (
          <div className="h-48 shimmer rounded" />
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={aggregatedMonthly} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--ifx-gray-100)" />
              <XAxis dataKey="month" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v: number) => `$${(v / 1000000).toFixed(1)}M`} />
              <Tooltip formatter={(v) => typeof v === "number" ? `$${(v / 1000000).toFixed(2)}M` : String(v)} />
              <Legend />
              <Line type="monotone" dataKey="Actual" stroke="var(--ifx-pink)" strokeWidth={2} dot />
              <Line type="monotone" dataKey="Budget" stroke="var(--ifx-navy)" strokeWidth={2} strokeDasharray="5 5" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <ConfigurableDataTable
        tableId="budget-by-program"
        columns={COLUMNS}
        data={programs}
        loading={isLoading}
        searchable
        exportable
        pagination={{ pageSize: 25 }}
        emptyMessage="No budget data available."
      />
    </DetailPageLayout>
  );
}
