// packages/modules/paysync/src/inbox/cards/UploadPendingReviewCard.tsx
// Rich inbox card for upload_pending_review items.
// Renders filename, error_count from payload, priority indicator, and a
// navigation link to the upload detail page via item.upload_id.

import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";

export default function UploadPendingReviewCard({ item }: { readonly item: InboxItem }): ReactElement {
  const filename = typeof item.payload["filename"] === "string" ? item.payload["filename"] : null;
  const errorCount = typeof item.payload["error_count"] === "number" ? item.payload["error_count"] : null;
  const detailHref = item.upload_id
    ? `/admin/paysync/uploads/${item.upload_id}`
    : "/admin/paysync/uploads";

  return (
    <div data-testid="inbox-card-upload_pending_review">
      {item.priority === "high" && (
        <span data-testid="card-priority-high" aria-label="High priority">
          High Priority
        </span>
      )}

      <strong>{filename ?? "Upload"}</strong>
      <span> — Pending review</span>

      {errorCount !== null && (
        <span data-testid="card-error-count" aria-label={`${errorCount} validation errors`}>
          {" "}({errorCount} error{errorCount !== 1 ? "s" : ""})
        </span>
      )}

      <a data-testid="card-action-link" href={detailHref}>
        Review upload
      </a>
    </div>
  );
}
