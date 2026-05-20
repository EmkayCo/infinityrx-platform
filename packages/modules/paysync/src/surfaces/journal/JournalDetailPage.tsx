// packages/modules/paysync/src/surfaces/journal/JournalDetailPage.tsx
// Detail view for a single journal entry.
// Shows full entry_hash + prev_hash, hash-chain link visualization,
// and a cross-link to the originating upload when uploadId is provided.

import type { ReactElement } from "react";
import type { JournalEntry } from "@infinityrx/contract";
import { MoneyDisplay } from "../../components/MoneyDisplay.js";

export interface JournalDetailPageProps {
  readonly entry: JournalEntry | null;
  readonly isLoading: boolean;
  readonly error: string | null;
  /** Upload ID to cross-link provenance. Pass when reference_type === "upload". */
  readonly uploadId?: string;
}

export function JournalDetailPage({
  entry,
  isLoading,
  error,
  uploadId,
}: JournalDetailPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="journal-detail-loading" role="status" aria-label="Loading journal entry">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="journal-detail-error" role="alert">
        {error}
      </div>
    );
  }

  if (!entry) {
    return (
      <div data-testid="journal-detail-page">
        <p>Journal entry not found.</p>
      </div>
    );
  }

  return (
    <div data-testid="journal-detail-page">
      <h1>Journal Entry</h1>

      <section aria-label="Entry details">
        <dl>
          <dt>Type</dt>
          <dd>{entry.entry_type}</dd>

          <dt>Account</dt>
          <dd>{entry.gl_account_code ?? "-"}</dd>

          <dt>Amount</dt>
          <dd>
            <MoneyDisplay value={entry.amount} />
          </dd>

          <dt>Category</dt>
          <dd>{entry.category ?? "-"}</dd>

          <dt>Description</dt>
          <dd>{entry.description ?? "-"}</dd>

          <dt>Created At</dt>
          <dd>
            {entry.created_at ? (
              <time dateTime={entry.created_at}>
                {new Date(entry.created_at).toLocaleString()}
              </time>
            ) : (
              "-"
            )}
          </dd>
        </dl>
      </section>

      {/* Hash chain link visualization */}
      <section aria-label="Hash chain" data-testid="hash-chain-links">
        <h2>Hash Chain</h2>
        <dl>
          <dt>Entry Hash</dt>
          <dd>
            <code data-testid="entry-hash-full">{entry.entry_hash ?? "-"}</code>
          </dd>

          <dt>Previous Hash</dt>
          <dd>
            <code data-testid="entry-prev-hash">{entry.prev_hash ?? "-"}</code>
          </dd>
        </dl>
      </section>

      {/* Upload provenance cross-link (per spec: if upload_id non-null) */}
      {uploadId && (
        <section aria-label="Provenance">
          <a
            data-testid="entry-upload-link"
            href={`/admin/paysync/uploads/${uploadId}`}
          >
            Provenance: Upload {uploadId.slice(0, 8)}...
          </a>
        </section>
      )}
    </div>
  );
}
