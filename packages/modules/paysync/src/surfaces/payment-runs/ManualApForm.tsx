// packages/modules/paysync/src/surfaces/payment-runs/ManualApForm.tsx
// Manual AP entry form for payment runs.
// - MoneyInput for amount: validates <=4 decimal places, ROUND_HALF_UP semantics.
// - RbacGate on submit button: Approver-only.
// - Never uses Number() for money — all values remain Decimal-as-string.

import { useState, type ReactElement } from "react";
import { MoneyInput } from "../../components/MoneyInput.js";
import { RbacGate } from "../../components/RbacGate.js";
import type { RbacRole } from "../../inbox/types.js";

export interface ManualApEntry {
  readonly amount: string;
  readonly payee: string;
  readonly memo: string;
}

export interface ManualApFormProps {
  readonly currentRole: RbacRole;
  readonly onSubmit: (entry: ManualApEntry) => void;
}

export function ManualApForm({ currentRole, onSubmit }: ManualApFormProps): ReactElement {
  const [amount, setAmount] = useState<string>("");
  const [payee, setPayee] = useState<string>("");
  const [memo, setMemo] = useState<string>("");

  function handleSubmit(): void {
    if (!amount || !payee) return;
    onSubmit({ amount, payee, memo });
  }

  return (
    <form data-testid="manual-ap-form" onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
      <h2>Manual AP Entry</h2>

      <div>
        <label htmlFor="manual-ap-payee">Payee</label>
        <input
          id="manual-ap-payee"
          data-testid="manual-ap-payee"
          type="text"
          value={payee}
          onChange={(e) => setPayee(e.target.value)}
          required
        />
      </div>

      <div>
        <label htmlFor="manual-ap-amount">Amount</label>
        <MoneyInput
          name="manual-ap-amount"
          initialValue={amount}
          onChange={setAmount}
          maxDecimalPlaces={4}
        />
      </div>

      <div>
        <label htmlFor="manual-ap-memo">Memo</label>
        <input
          id="manual-ap-memo"
          data-testid="manual-ap-memo"
          type="text"
          value={memo}
          onChange={(e) => setMemo(e.target.value)}
        />
      </div>

      <RbacGate role="approver" currentRole={currentRole}>
        <button
          data-testid="manual-ap-submit"
          type="submit"
        >
          Submit AP Entry
        </button>
      </RbacGate>
    </form>
  );
}
