// packages/modules/paysync/src/surfaces/setup/EmailTemplatesPage.tsx
// Setup page for billing notification email templates.
// Save action is Approver-only per spec §5.4.
// TODO(Plan-F): wire onSave to POST /api/paysync/setup/email-templates.

import type { ReactElement } from "react";
import { RbacGate } from "../../components/RbacGate.js";
import type { RbacRole } from "../../inbox/types.js";

export interface EmailTemplate {
  readonly id: string;
  readonly tenant_id: string;
  readonly trigger_event: string;
  readonly subject: string;
  readonly body_html: string;
  readonly active: boolean;
  readonly created_at: string;
}

export interface EmailTemplatesPageProps {
  readonly templates: ReadonlyArray<EmailTemplate>;
  readonly isLoading: boolean;
  readonly error: string | null;
  readonly currentRole: RbacRole;
  readonly onSave: (data: Omit<EmailTemplate, "id" | "tenant_id" | "created_at">) => void;
}

export function EmailTemplatesPage({
  templates,
  isLoading,
  error,
  currentRole,
  onSave,
}: EmailTemplatesPageProps): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="email-templates-page">
        <div data-testid="email-templates-loading" role="status" aria-label="Loading email templates">
          Loading email templates...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="email-templates-page">
        <div data-testid="email-templates-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="email-templates-page">
      <h1>Email Templates</h1>
      <p>Customize notification email content. Save requires Approver role.</p>

      {templates.length > 0 && (
        <table aria-label="Email templates">
          <thead>
            <tr>
              <th scope="col">Trigger Event</th>
              <th scope="col">Subject</th>
              <th scope="col">Active</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((t) => (
              <tr key={t.id} data-testid="email-template-row">
                <td>{t.trigger_event}</td>
                <td>{t.subject}</td>
                <td>{t.active ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <RbacGate role="approver" currentRole={currentRole}>
        <button
          type="button"
          data-testid="email-templates-save-button"
          onClick={() =>
            onSave({
              trigger_event: "",
              subject: "",
              body_html: "",
              active: true,
            })
          }
        >
          Add Template
        </button>
      </RbacGate>
    </div>
  );
}
