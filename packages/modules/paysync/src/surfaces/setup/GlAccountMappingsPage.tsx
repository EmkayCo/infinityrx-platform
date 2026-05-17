// packages/modules/paysync/src/surfaces/setup/GlAccountMappingsPage.tsx
// Setup page for GL account code mappings.
// Maps paysync entry categories to general ledger account codes.
// Save action is Approver-only per spec §5.4.
// TODO(Plan-F): wire onSave to POST /api/paysync/setup/gl-account-mappings.

import type { ReactElement } from "react";
import { RbacGate } from "../../components/RbacGate.js";
import type { RbacRole } from "../../inbox/types.js";

export interface GlAccountMapping {
  readonly id: string;
  readonly tenant_id: string;
  readonly entry_category: string;
  readonly gl_account_code: string;
  readonly gl_class: string | null;
  readonly active: boolean;
  readonly created_at: string;
}

export interface GlAccountMappingsPageProps {
  readonly mappings: ReadonlyArray<GlAccountMapping>;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly currentRole: RbacRole;
  readonly onSave: (data: Omit<GlAccountMapping, "id" | "tenant_id" | "created_at">) => void;
}

export function GlAccountMappingsPage({
  mappings,
  isLoading,
  error,
  currentRole,
  onSave,
}: GlAccountMappingsPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="gl-account-mappings-page">
        <div data-testid="gl-account-mappings-loading" role="status" aria-label="Loading GL account mappings">
          Loading GL account mappings...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="gl-account-mappings-page">
        <div data-testid="gl-account-mappings-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="gl-account-mappings-page">
      <h1>GL Account Mappings</h1>
      <p>Map paysync entry categories to general ledger account codes. Save requires Approver role.</p>

      {mappings.length > 0 && (
        <table aria-label="GL account mappings">
          <thead>
            <tr>
              <th scope="col">Entry Category</th>
              <th scope="col">GL Account Code</th>
              <th scope="col">GL Class</th>
              <th scope="col">Active</th>
            </tr>
          </thead>
          <tbody>
            {mappings.map((m) => (
              <tr key={m.id} data-testid="gl-mapping-row">
                <td>{m.entry_category}</td>
                <td>{m.gl_account_code}</td>
                <td>{m.gl_class ?? "-"}</td>
                <td>{m.active ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <RbacGate role="approver" currentRole={currentRole}>
        <button
          type="button"
          data-testid="gl-account-mappings-save-button"
          onClick={() =>
            onSave({
              entry_category: "",
              gl_account_code: "",
              gl_class: null,
              active: true,
            })
          }
        >
          Add Mapping
        </button>
      </RbacGate>
    </div>
  );
}
