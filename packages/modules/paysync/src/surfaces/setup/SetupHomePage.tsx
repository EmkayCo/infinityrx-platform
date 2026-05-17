// packages/modules/paysync/src/surfaces/setup/SetupHomePage.tsx
// Index page for the paysync setup surface.
// All setup mutations are Approver-only per spec §5.4.
// This page is navigational only -- no mutations here.

import type { ReactElement } from "react";

export function SetupHomePage(): ReactElement {
  return (
    <div data-testid="setup-home-page">
      <h1>PaySync Setup</h1>
      <p>Configure billing notifications, GL mappings, invoice sequences, and cycle schedules. Save actions require Approver role.</p>

      <ul aria-label="Setup areas">
        <li>
          <a data-testid="setup-link-email-recipients" href="/admin/paysync/setup/email-recipients">
            Email Recipients
          </a>
          <p>Manage who receives billing notification emails.</p>
        </li>
        <li>
          <a data-testid="setup-link-email-templates" href="/admin/paysync/setup/email-templates">
            Email Templates
          </a>
          <p>Customize notification email subjects and body content.</p>
        </li>
        <li>
          <a data-testid="setup-link-export-templates" href="/admin/paysync/setup/export-templates">
            Export Templates
          </a>
          <p>Define column layouts and formats for billing data exports.</p>
        </li>
        <li>
          <a data-testid="setup-link-gl-account-mappings" href="/admin/paysync/setup/gl-account-mappings">
            GL Account Mappings
          </a>
          <p>Map paysync entry categories to general ledger account codes.</p>
        </li>
        <li>
          <a data-testid="setup-link-invoice-sequences" href="/admin/paysync/setup/invoice-sequences">
            Invoice Sequences
          </a>
          <p>Configure invoice number prefixes and counters.</p>
        </li>
        <li>
          <a data-testid="setup-link-cycle-schedules" href="/admin/paysync/setup/cycle-schedules">
            Cycle Schedules
          </a>
          <p>Set automated billing cycle open and close schedules.</p>
        </li>
      </ul>
    </div>
  );
}
