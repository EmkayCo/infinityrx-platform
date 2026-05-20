// packages/modules/paysync/src/surfaces/journal/JournalListPage.tsx
// List view for billing journal entries (hash-chained ledger).
// Columns: gl_account_code, amount (MoneyDisplay), entry_type, entry_hash (first 8 chars), created_at.
// Data received via props (BFF/TanStack Query owns the fetch).

import type { ReactElement } from "react";
import type { JournalEntry } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface JournalListPageProps {
  readonly entries: ReadonlyArray<JournalEntry>;
  readonly isLoading: boolean;
  readonly error: string | null;
}

function truncateHash(hash: string | null): string {
  if (!hash) return "-";
  return `${hash.slice(0, 8)}...`;
}

export function JournalListPage({
  entries,
  isLoading,
  error,
}: JournalListPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="journal-list-page">
        <div data-testid="journal-list-loading" role="status" aria-label="Loading journal entries">
          Loading journal entries...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="journal-list-page">
        <div data-testid="journal-list-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="journal-list-page">
      <h1>Journal Ledger</h1>

      {entries.length === 0 ? (
        <div data-testid="journal-list-empty" role="status">
          No journal entries found.
        </div>
      ) : (
        <table aria-label="Journal entries">
          <thead>
            <tr>
              <th scope="col">Account</th>
              <th scope="col">Amount</th>
              <th scope="col">Type</th>
              <th scope="col">Hash</th>
              <th scope="col">Created At</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id} data-testid="journal-entry-row">
                <td>
                  <a href={`/admin/paysync/journal/${entry.id}`}>
                    {entry.gl_account_code ?? "-"}
                  </a>
                </td>
                <td>
                  <MoneyDisplay value={entry.amount} />
                </td>
                <td>{entry.entry_type}</td>
                <td>
                  <span
                    data-testid="entry-hash-short"
                    title={entry.entry_hash ?? undefined}
                    aria-label={`Entry hash: ${entry.entry_hash ?? "none"}`}
                  >
                    {truncateHash(entry.entry_hash)}
                  </span>
                </td>
                <td>
                  {entry.created_at ? (
                    <time dateTime={entry.created_at}>
                      {new Date(entry.created_at).toLocaleString()}
                    </time>
                  ) : (
                    <span>-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
