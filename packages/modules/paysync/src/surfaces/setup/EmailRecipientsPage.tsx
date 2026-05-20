// packages/modules/paysync/src/surfaces/setup/EmailRecipientsPage.tsx
// Setup page for billing email notification recipients.
// Save action is Approver-only per spec §5.4.
// Auditor and Operator see the form read-only (RbacGate renders save disabled).
// TODO(Plan-F): wire onSave to POST /api/paysync/setup/email-recipients.

import type { ReactElement } from "react";
import { RbacGate } from "../../components/RbacGate.js";
import type { RbacRole } from "../../inbox/types.js";

export interface EmailRecipient {
  readonly id: string;
  readonly tenant_id: string;
  readonly email: string;
  readonly name: string;
  readonly notification_kinds: ReadonlyArray<string>;
  readonly active: boolean;
  readonly created_at: string;
}

export interface EmailRecipientsPageProps {
  readonly recipients?: ReadonlyArray<EmailRecipient>;
  readonly isLoading?: boolean;
  readonly error?: string | null;
  readonly currentRole?: RbacRole;
  readonly onSave?: (data: Omit<EmailRecipient, "id" | "tenant_id" | "created_at">) => void;
}

export function EmailRecipientsPage({
  recipients = [],
  isLoading = false,
  error = null,
  currentRole = "auditor",
  onSave = () => undefined,
}: EmailRecipientsPageProps = {}): ReactElement {
  if (isLoading) {
    return (
      <div data-testid="email-recipients-page">
        <div data-testid="email-recipients-loading" role="status" aria-label="Loading email recipients">
          Loading email recipients...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="email-recipients-page">
        <div data-testid="email-recipients-error" role="alert">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div data-testid="email-recipients-page">
      <h1>Email Recipients</h1>
      <p>Manage billing notification recipients. Save requires Approver role.</p>

      {recipients.length > 0 && (
        <table aria-label="Email recipients">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Email</th>
              <th scope="col">Notifications</th>
              <th scope="col">Active</th>
            </tr>
          </thead>
          <tbody>
            {recipients.map((r) => (
              <tr key={r.id} data-testid="email-recipient-row">
                <td>{r.name}</td>
                <td>{r.email}</td>
                <td>{r.notification_kinds.join(", ")}</td>
                <td>{r.active ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <RbacGate role="approver" currentRole={currentRole}>
        <button
          type="button"
          data-testid="email-recipients-save-button"
          onClick={() =>
            onSave({
              email: "",
              name: "",
              notification_kinds: [],
              active: true,
            })
          }
        >
          Add Recipient
        </button>
      </RbacGate>
    </div>
  );
}
