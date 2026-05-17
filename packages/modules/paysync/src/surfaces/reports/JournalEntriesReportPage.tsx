// packages/modules/paysync/src/surfaces/reports/JournalEntriesReportPage.tsx
// Read-only report view for journal entries.
// Re-uses JournalEntry type from @infinityrx/contract.
// All roles can view. Monetary amounts via MoneyDisplay.

import type { ReactElement } from "react";
import type { JournalEntry } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface JournalEntriesReportPageProps {
  readonly entries: ReadonlyArray<JournalEntry>;
  readonly isLoading: boolean;
  readonly error: string | null;
}

export function JournalEntriesReportPage({
  entries,
  isLoading,
  error,
}: JournalEntriesReportPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="journal-entries-report-page">
        <div
          data-testid="journal-entries-report-loading"
          role="status"
          aria-label="Loading journal entries report"
        >
          Loading journal entries...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="journal-entries-report-page">
        <div data-testid="journal-entries-report-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="journal-entries-report-page">
      <h1>Journal Entries Report</h1>
      <p>Read-only view of the billing journal ledger. All roles can view.</p>

      <div data-testid="export-disabled-notice">
        <button
          type="button"
          disabled
          aria-disabled="true"
          title="PDF/Excel export coming in a future release"
        >
          Export
        </button>
      </div>

      {entries.length === 0 ? (
        <div data-testid="journal-entries-report-empty" role="status">
          No journal entries found for the selected filters.
        </div>
      ) : (
        <table aria-label="Journal entries report">
          <thead>
            <tr>
              <th scope="col">Date</th>
              <th scope="col">Type</th>
              <th scope="col">Account</th>
              <th scope="col">Amount</th>
              <th scope="col">Description</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id} data-testid="journal-report-entry-row">
                <td>
                  {entry.entry_date ? (
                    <time dateTime={entry.entry_date}>{entry.entry_date}</time>
                  ) : (
                    <span>-</span>
                  )}
                </td>
                <td>{entry.entry_type}</td>
                <td>{entry.gl_account_code ?? "-"}</td>
                <td>
                  <MoneyDisplay value={entry.amount} />
                </td>
                <td>{entry.description ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
