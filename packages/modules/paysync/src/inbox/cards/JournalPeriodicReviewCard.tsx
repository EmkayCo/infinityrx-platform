// packages/modules/paysync/src/inbox/cards/JournalPeriodicReviewCard.tsx
// Rich inbox card for journal_periodic_review items.
// Renders entry_count and a "Run verify-chain" CTA link to the journal surface.

import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";

export default function JournalPeriodicReviewCard({ item }: { readonly item: InboxItem }): ReactElement {
  const entryCount = typeof item.payload["entry_count"] === "number" ? item.payload["entry_count"] : null;
  const lastVerifiedAt = typeof item.payload["last_verified_at"] === "string" ? item.payload["last_verified_at"] : null;

  return (
    <div data-testid="inbox-card-journal_periodic_review">
      {item.priority === "high" && (
        <span data-testid="card-priority-high" aria-label="High priority">
          High Priority
        </span>
      )}

      <strong>Journal Periodic Review</strong>

      {entryCount !== null && (
        <span data-testid="card-entry-count" aria-label={`${entryCount} journal entries`}>
          {" "}({entryCount} {entryCount !== 1 ? "entries" : "entry"})
        </span>
      )}

      {lastVerifiedAt !== null && (
        <span data-testid="card-last-verified">
          {" "}Last verified:{" "}
          <time dateTime={lastVerifiedAt}>
            {new Date(lastVerifiedAt).toLocaleDateString()}
          </time>
        </span>
      )}

      <a
        data-testid="card-action-link"
        href="/admin/paysync/journal"
      >
        Run verify-chain
      </a>
    </div>
  );
}
