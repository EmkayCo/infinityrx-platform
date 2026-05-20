// packages/modules/paysync/src/surfaces/journal/HashChainVerifyButton.tsx
// Triggers a synchronous hash-chain verification and renders the result
// via the existing HashChainBadge component.
//
// States:
//   idle       -- "Verify chain integrity" button
//   verifying  -- spinner + "Verifying..."
//   verified   -- green badge (verified=true)
//   broken     -- red badge (verified=false) + broken_at id + escalation message
//   too-large  -- amber badge (verified=null, too_large=true) + link to job runner
//
// Per spec §8: does NOT auto-repair on break. No repair button is ever rendered.
// Per Plan D R1 B2 fix: verify-chain is auditor-only (matches backend RBAC at
// modules/billing/src/api/journal.py). Non-auditor roles see the RbacGate
// denied state and cannot trigger verification.

import { useState, type ReactElement } from "react";
import type { HashChainVerifyResponse } from "@infinityrx/contract";
import { HashChainBadge } from "../../components/HashChainBadge.js";
import { RbacGate } from "../../components/RbacGate.js";
import type { RbacRole } from "../../inbox/types.js";

export interface HashChainVerifyButtonProps {
  readonly currentRole: RbacRole;
  readonly onVerify: () => Promise<HashChainVerifyResponse>;
}

type VerifyState =
  | { status: "idle" }
  | { status: "verifying" }
  | { status: "done"; response: HashChainVerifyResponse }
  | { status: "error"; message: string };

export function HashChainVerifyButton({
  currentRole,
  onVerify,
}: HashChainVerifyButtonProps): ReactElement {
  const [state, setState] = useState<VerifyState>({ status: "idle" });

  async function handleVerify(): Promise<void> {
    setState({ status: "verifying" });
    try {
      const response = await onVerify();
      setState({ status: "done", response });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Verification failed";
      setState({ status: "error", message });
    }
  }

  const button = (
    <button
      data-testid="verify-chain-button"
      type="button"
      onClick={handleVerify}
      disabled={state.status === "verifying"}
      aria-busy={state.status === "verifying"}
    >
      {state.status === "verifying" ? "Verifying..." : "Verify chain integrity"}
    </button>
  );

  return (
    <div data-testid="hash-chain-verify-panel">
      <RbacGate role="auditor" currentRole={currentRole}>
        {button}
      </RbacGate>

      {state.status === "verifying" && (
        <div data-testid="verify-state-verifying" role="status" aria-label="Verifying hash chain">
          Verifying...
        </div>
      )}

      {state.status === "done" && (
        <div data-testid="verify-state-done">
          <HashChainBadge
            verified={state.response.verified}
            tooLarge={state.response.too_large}
          />

          {state.response.verified === false && state.response.broken_at && (
            <div data-testid="verify-broken-at" role="alert">
              <strong>Chain broken at entry:</strong>{" "}
              <span>{state.response.broken_at.slice(0, 8)}...</span>
              <p>
                Do not modify journal -- contact compliance team.
              </p>
            </div>
          )}

          {state.response.too_large && (
            <div data-testid="verify-too-large-hint">
              Chain too large for synchronous verification (&gt;10 000 entries).{" "}
              <a href="/admin/paysync/jobs/verify-chain">
                Run the scheduled verification job
              </a>
            </div>
          )}

          {state.response.verified === true && (
            <div data-testid="verify-entry-count">
              {state.response.total_entries} entries verified.
            </div>
          )}
        </div>
      )}

      {state.status === "error" && (
        <div data-testid="verify-state-error" role="alert">
          {state.message}
        </div>
      )}
    </div>
  );
}
