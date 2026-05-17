// packages/modules/paysync/src/inbox/cards/UploadValidatedCard.tsx
// Rich inbox card for upload_validated_awaiting_batching items.
// Renders filename, claim_count from payload, and a navigation link to the
// upload detail page via item.upload_id.

import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";

export default function UploadValidatedCard({ item }: { readonly item: InboxItem }): ReactElement {
  const filename = typeof item.payload["filename"] === "string" ? item.payload["filename"] : null;
  const claimCount = typeof item.payload["claim_count"] === "number" ? item.payload["claim_count"] : null;
  const detailHref = item.upload_id
    ? `/admin/paysync/uploads/${item.upload_id}`
    : "/admin/paysync/uploads";

  return (
    <div data-testid="inbox-card-upload_validated_awaiting_batching">
      {item.priority === "high" && (
        <span data-testid="card-priority-high" aria-label="High priority">
          High Priority
        </span>
      )}

      <strong>{filename ?? "Upload"}</strong>
      <span> — Validated, awaiting batching</span>

      {claimCount !== null && (
        <span data-testid="card-claim-count" aria-label={`${claimCount} claims`}>
          {" "}({claimCount} claim{claimCount !== 1 ? "s" : ""})
        </span>
      )}

      <a data-testid="card-action-link" href={detailHref}>
        View upload
      </a>
    </div>
  );
}
