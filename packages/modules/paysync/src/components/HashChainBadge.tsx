// packages/modules/paysync/src/components/HashChainBadge.tsx
// Renders the journal hash-chain verification state per §10.4 spec.
// States:
//   verified === true            → green ✓
//   verified === false           → red ✗
//   verified === null && tooLarge → amber ⚠ (deferred to async job, see PAYSYNC_HASH_CHAIN_SYNC_LIMIT)
//   verified === null            → spinner (in-flight verification)

import type { ReactElement } from "react";

export interface HashChainBadgeProps {
  readonly verified: boolean | null;
  readonly tooLarge?: boolean;
}

export function HashChainBadge({ verified, tooLarge = false }: HashChainBadgeProps): ReactElement {
  if (verified === true) {
    return (
      <span data-testid="hash-chain-verified" role="status" aria-label="Hash chain verified">
        ✓ Verified
      </span>
    );
  }
  if (verified === false) {
    return (
      <span data-testid="hash-chain-failed" role="alert" aria-label="Hash chain verification failed">
        ✗ Failed
      </span>
    );
  }
  if (tooLarge) {
    return (
      <span
        data-testid="hash-chain-too-large"
        role="status"
        aria-label="Hash chain verification deferred to background job"
      >
        ⚠ Deferred
      </span>
    );
  }
  return (
    <span data-testid="hash-chain-loading" role="status" aria-label="Verifying hash chain">
      …
    </span>
  );
}
