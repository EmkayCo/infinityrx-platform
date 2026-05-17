// packages/modules/paysync/src/surfaces/reports/ReportsListPage.tsx
// Index page for the paysync reports surface.
// All roles can view. Links to cycle reports, journal entries report,
// and period summary report.

import type { ReactElement } from "react";

export function ReportsListPage(): ReactElement {
  return (
    <div data-testid="reports-list-page">
      <h1>Reports</h1>
      <p>Select a report to view. All reports are read-only and available to all roles.</p>

      <ul aria-label="Available reports">
        <li>
          <a
            data-testid="reports-link-cycles"
            href="/admin/paysync/reports/cycles"
          >
            Cycle Reports
          </a>
          <p>Summary of all billing cycles with totals and status.</p>
        </li>
        <li>
          <a
            data-testid="reports-link-journal"
            href="/admin/paysync/reports/journal-entries"
          >
            Journal Entries Report
          </a>
          <p>Filtered view of the billing journal ledger for export and audit review.</p>
        </li>
        <li>
          <a
            data-testid="reports-link-period-summary"
            href="/admin/paysync/reports/period-summary"
          >
            Period Summary
          </a>
          <p>Aggregate totals for a selected billing period.</p>
        </li>
      </ul>
    </div>
  );
}
