// packages/modules/paysync/src/surfaces/setup/InvoiceSequencesPage.tsx
// Setup page for invoice number sequences.
// Save action is Approver-only per spec §5.4.
// TODO(Plan-F): wire onSave to POST /api/paysync/setup/invoice-sequences.

import type { ReactElement } from "react";
import { RbacGate } from "../../components/RbacGate.js";
import type { RbacRole } from "../../inbox/types.js";

export interface InvoiceSequence {
  readonly id: string;
  readonly tenant_id: string;
  readonly prefix: string;
  readonly next_value: number;
  readonly padding: number;
  readonly active: boolean;
  readonly created_at: string;
}

export interface InvoiceSequencesPageProps {
  readonly sequences: ReadonlyArray<InvoiceSequence>;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly currentRole: RbacRole;
  readonly onSave: (data: Omit<InvoiceSequence, "id" | "tenant_id" | "created_at">) => void;
}

export function InvoiceSequencesPage({
  sequences,
  isLoading,
  error,
  currentRole,
  onSave,
}: InvoiceSequencesPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="invoice-sequences-page">
        <div data-testid="invoice-sequences-loading" role="status" aria-label="Loading invoice sequences">
          Loading invoice sequences...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="invoice-sequences-page">
        <div data-testid="invoice-sequences-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="invoice-sequences-page">
      <h1>Invoice Sequences</h1>
      <p>Configure invoice number prefixes and counters. Save requires Approver role.</p>

      {sequences.length > 0 && (
        <table aria-label="Invoice sequences">
          <thead>
            <tr>
              <th scope="col">Prefix</th>
              <th scope="col">Next Value</th>
              <th scope="col">Padding</th>
              <th scope="col">Active</th>
            </tr>
          </thead>
          <tbody>
            {sequences.map((s) => (
              <tr key={s.id} data-testid="invoice-sequence-row">
                <td>{s.prefix}</td>
                <td>{s.next_value}</td>
                <td>{s.padding}</td>
                <td>{s.active ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <RbacGate role="approver" currentRole={currentRole}>
        <button
          type="button"
          data-testid="invoice-sequences-save-button"
          onClick={() =>
            onSave({
              prefix: "",
              next_value: 1,
              padding: 6,
              active: true,
            })
          }
        >
          Add Sequence
        </button>
      </RbacGate>
    </div>
  );
}
