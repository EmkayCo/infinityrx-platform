// packages/modules/paysync/src/inbox/cards/UploadPendingReviewCard.tsx
// Typed stub card. Real card lands in a later SP-1 plan. Plan A's only job
// is to ship a type-safe, render-able skeleton so ItemRegistry's dynamic
// imports resolve and the InboxQueue can mount cards without error.
import type { ReactElement } from "react";
import type { InboxItem } from "../types.js";

export default function UploadPendingReviewCard({ item }: { readonly item: InboxItem }): ReactElement {
  return (
    <div data-testid="inbox-card-upload_pending_review">
      {item.kind}
    </div>
  );
}
