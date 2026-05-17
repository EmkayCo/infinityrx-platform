// packages/modules/paysync/src/surfaces/setup/ExportTemplatesPage.tsx
// Setup page for billing data export templates.
// Save action is Approver-only per spec §5.4.
// TODO(Plan-F): wire onSave to POST /api/paysync/setup/export-templates.

import type { ReactElement } from "react";
import { RbacGate } from "../../components/RbacGate.js";
import type { RbacRole } from "../../inbox/types.js";

export type ExportFormat = "csv" | "xlsx" | "json" | "fixed-width";

export interface ExportTemplate {
  readonly id: string;
  readonly tenant_id: string;
  readonly name: string;
  readonly format: ExportFormat;
  readonly columns: ReadonlyArray<string>;
  readonly active: boolean;
  readonly created_at: string;
}

export interface ExportTemplatesPageProps {
  readonly templates?: ReadonlyArray<ExportTemplate>;
  readonly isLoading?: boolean;
  readonly error?: string | null;
  readonly currentRole?: RbacRole;
  readonly onSave?: (data: Omit<ExportTemplate, "id" | "tenant_id" | "created_at">) => void;
}

export function ExportTemplatesPage({
  templates = [],
  isLoading = false,
  error = null,
  currentRole = "auditor",
  onSave = () => undefined,
}: ExportTemplatesPageProps = {}): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="export-templates-page">
        <div data-testid="export-templates-loading" role="status" aria-label="Loading export templates">
          Loading export templates...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="export-templates-page">
        <div data-testid="export-templates-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="export-templates-page">
      <h1>Export Templates</h1>
      <p>Define column layouts and formats for billing data exports. Save requires Approver role.</p>

      {templates.length > 0 && (
        <table aria-label="Export templates">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Format</th>
              <th scope="col">Columns</th>
              <th scope="col">Active</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((t) => (
              <tr key={t.id} data-testid="export-template-row">
                <td>{t.name}</td>
                <td>{t.format}</td>
                <td>{t.columns.join(", ")}</td>
                <td>{t.active ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <RbacGate role="approver" currentRole={currentRole}>
        <button
          type="button"
          data-testid="export-templates-save-button"
          onClick={() =>
            onSave({
              name: "",
              format: "csv",
              columns: [],
              active: true,
            })
          }
        >
          Add Export Template
        </button>
      </RbacGate>
    </div>
  );
}
