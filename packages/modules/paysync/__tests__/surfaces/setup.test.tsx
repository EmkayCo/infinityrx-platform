// packages/modules/paysync/__tests__/surfaces/setup.test.tsx
// RTL tests for the setup surface: SetupHomePage + 6 setup area pages + BFF handlers.
// All mutations are Approver-only (RbacGate role="approver").
// Auditor and Operator see forms read-only (save buttons rendered disabled via RbacGate).
// Backend wire-up for mutations is Plan F+ scope -- forms render but POST is TODO.
// Uses happy-dom. cleanup() in afterEach.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";

afterEach(() => cleanup());

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-17T10:00:00.000+00:00";

// ── SetupHomePage ────────────────────────────────────────────────────────

describe("SetupHomePage", () => {
  let SetupHomePage: typeof import("../../src/surfaces/setup/SetupHomePage.js").SetupHomePage;

  beforeEach(async () => {
    ({ SetupHomePage } = await import("../../src/surfaces/setup/SetupHomePage.js"));
  });

  it("renders the setup home page container", () => {
    render(<SetupHomePage />);
    expect(screen.getByTestId("setup-home-page")).toBeTruthy();
  });

  it("renders a link to email recipients", () => {
    render(<SetupHomePage />);
    expect(screen.getByTestId("setup-link-email-recipients")).toBeTruthy();
  });

  it("renders a link to email templates", () => {
    render(<SetupHomePage />);
    expect(screen.getByTestId("setup-link-email-templates")).toBeTruthy();
  });

  it("renders a link to export templates", () => {
    render(<SetupHomePage />);
    expect(screen.getByTestId("setup-link-export-templates")).toBeTruthy();
  });

  it("renders a link to GL account mappings", () => {
    render(<SetupHomePage />);
    expect(screen.getByTestId("setup-link-gl-account-mappings")).toBeTruthy();
  });

  it("renders a link to invoice sequences", () => {
    render(<SetupHomePage />);
    expect(screen.getByTestId("setup-link-invoice-sequences")).toBeTruthy();
  });

  it("renders a link to cycle schedules", () => {
    render(<SetupHomePage />);
    expect(screen.getByTestId("setup-link-cycle-schedules")).toBeTruthy();
  });

  it("renders a heading", () => {
    render(<SetupHomePage />);
    expect(screen.getByRole("heading", { level: 1 })).toBeTruthy();
  });
});

// ── EmailRecipientsPage ──────────────────────────────────────────────────

describe("EmailRecipientsPage", () => {
  let EmailRecipientsPage: typeof import("../../src/surfaces/setup/EmailRecipientsPage.js").EmailRecipientsPage;

  const makeRecipient = (overrides = {}) => ({
    id: "r1000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    email: "billing@example.com",
    name: "Billing Team",
    notification_kinds: ["cycle", "invoice"],
    active: true,
    created_at: NOW,
    ...overrides,
  });

  beforeEach(async () => {
    ({ EmailRecipientsPage } = await import("../../src/surfaces/setup/EmailRecipientsPage.js"));
  });

  it("renders the email recipients page container", () => {
    render(<EmailRecipientsPage recipients={[]} isLoading={false} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("email-recipients-page")).toBeTruthy();
  });

  it("renders a row for each recipient", () => {
    render(
      <EmailRecipientsPage
        recipients={[makeRecipient(), makeRecipient({ id: "r2", email: "ops@example.com" })]}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getAllByTestId("email-recipient-row")).toHaveLength(2);
  });

  it("renders recipient email in row", () => {
    render(
      <EmailRecipientsPage
        recipients={[makeRecipient()]}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText("billing@example.com")).toBeTruthy();
  });

  it("save button is denied (RbacGate) for Operator role", () => {
    render(
      <EmailRecipientsPage
        recipients={[]}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("save button is allowed (RbacGate) for Approver role", () => {
    render(
      <EmailRecipientsPage
        recipients={[]}
        isLoading={false}
        error={null}
        currentRole="approver"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("save button is denied (RbacGate) for Auditor role", () => {
    render(
      <EmailRecipientsPage
        recipients={[]}
        isLoading={false}
        error={null}
        currentRole="auditor"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders loading state", () => {
    render(<EmailRecipientsPage recipients={[]} isLoading={true} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("email-recipients-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(<EmailRecipientsPage recipients={[]} isLoading={false} error="Failed" currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("email-recipients-error")).toBeTruthy();
  });
});

// ── EmailTemplatesPage ───────────────────────────────────────────────────

describe("EmailTemplatesPage", () => {
  let EmailTemplatesPage: typeof import("../../src/surfaces/setup/EmailTemplatesPage.js").EmailTemplatesPage;

  const makeTemplate = (overrides = {}) => ({
    id: "t1000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    trigger_event: "cycle.closed",
    subject: "Billing Cycle Closed",
    body_html: "<p>Your billing cycle has closed.</p>",
    active: true,
    created_at: NOW,
    ...overrides,
  });

  beforeEach(async () => {
    ({ EmailTemplatesPage } = await import("../../src/surfaces/setup/EmailTemplatesPage.js"));
  });

  it("renders the email templates page container", () => {
    render(<EmailTemplatesPage templates={[]} isLoading={false} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("email-templates-page")).toBeTruthy();
  });

  it("renders a row for each template", () => {
    render(
      <EmailTemplatesPage
        templates={[makeTemplate(), makeTemplate({ id: "t2", trigger_event: "invoice.sent" })]}
        isLoading={false}
        error={null}
        currentRole="approver"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getAllByTestId("email-template-row")).toHaveLength(2);
  });

  it("renders trigger_event for each template", () => {
    render(
      <EmailTemplatesPage
        templates={[makeTemplate()]}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText("cycle.closed")).toBeTruthy();
  });

  it("Approver save button is allowed", () => {
    render(
      <EmailTemplatesPage
        templates={[]}
        isLoading={false}
        error={null}
        currentRole="approver"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("Auditor sees save button denied", () => {
    render(
      <EmailTemplatesPage
        templates={[]}
        isLoading={false}
        error={null}
        currentRole="auditor"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders loading state", () => {
    render(<EmailTemplatesPage templates={[]} isLoading={true} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("email-templates-loading")).toBeTruthy();
  });
});

// ── ExportTemplatesPage ──────────────────────────────────────────────────

describe("ExportTemplatesPage", () => {
  let ExportTemplatesPage: typeof import("../../src/surfaces/setup/ExportTemplatesPage.js").ExportTemplatesPage;

  const makeExportTemplate = (overrides = {}) => ({
    id: "e1000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    name: "Standard CSV Export",
    format: "csv" as const,
    columns: ["date", "amount", "gl_account"],
    active: true,
    created_at: NOW,
    ...overrides,
  });

  beforeEach(async () => {
    ({ ExportTemplatesPage } = await import("../../src/surfaces/setup/ExportTemplatesPage.js"));
  });

  it("renders the export templates page container", () => {
    render(<ExportTemplatesPage templates={[]} isLoading={false} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("export-templates-page")).toBeTruthy();
  });

  it("renders a row for each template", () => {
    render(
      <ExportTemplatesPage
        templates={[makeExportTemplate(), makeExportTemplate({ id: "e2", name: "XLSX Export" })]}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getAllByTestId("export-template-row")).toHaveLength(2);
  });

  it("renders template name", () => {
    render(
      <ExportTemplatesPage
        templates={[makeExportTemplate()]}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText("Standard CSV Export")).toBeTruthy();
  });

  it("Approver save is allowed", () => {
    render(
      <ExportTemplatesPage templates={[]} isLoading={false} error={null} currentRole="approver" onSave={vi.fn()} />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("Operator save is denied", () => {
    render(
      <ExportTemplatesPage templates={[]} isLoading={false} error={null} currentRole="operator" onSave={vi.fn()} />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders loading state", () => {
    render(<ExportTemplatesPage templates={[]} isLoading={true} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("export-templates-loading")).toBeTruthy();
  });
});

// ── GlAccountMappingsPage ────────────────────────────────────────────────

describe("GlAccountMappingsPage", () => {
  let GlAccountMappingsPage: typeof import("../../src/surfaces/setup/GlAccountMappingsPage.js").GlAccountMappingsPage;

  const makeMapping = (overrides = {}) => ({
    id: "g1000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    entry_category: "rebate",
    gl_account_code: "4000",
    gl_class: null,
    active: true,
    created_at: NOW,
    ...overrides,
  });

  beforeEach(async () => {
    ({ GlAccountMappingsPage } = await import("../../src/surfaces/setup/GlAccountMappingsPage.js"));
  });

  it("renders the GL account mappings page container", () => {
    render(<GlAccountMappingsPage mappings={[]} isLoading={false} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("gl-account-mappings-page")).toBeTruthy();
  });

  it("renders a row for each mapping", () => {
    render(
      <GlAccountMappingsPage
        mappings={[makeMapping(), makeMapping({ id: "g2", entry_category: "admin_fee", gl_account_code: "5000" })]}
        isLoading={false}
        error={null}
        currentRole="approver"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getAllByTestId("gl-mapping-row")).toHaveLength(2);
  });

  it("renders entry_category and gl_account_code", () => {
    render(
      <GlAccountMappingsPage
        mappings={[makeMapping()]}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText("rebate")).toBeTruthy();
    expect(screen.getByText("4000")).toBeTruthy();
  });

  it("Approver-only save button allowed for Approver", () => {
    render(
      <GlAccountMappingsPage mappings={[]} isLoading={false} error={null} currentRole="approver" onSave={vi.fn()} />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("Approver-only save button denied for Operator", () => {
    render(
      <GlAccountMappingsPage mappings={[]} isLoading={false} error={null} currentRole="operator" onSave={vi.fn()} />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders loading state", () => {
    render(<GlAccountMappingsPage mappings={[]} isLoading={true} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("gl-account-mappings-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(<GlAccountMappingsPage mappings={[]} isLoading={false} error="Load failed" currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("gl-account-mappings-error")).toBeTruthy();
  });
});

// ── InvoiceSequencesPage ─────────────────────────────────────────────────

describe("InvoiceSequencesPage", () => {
  let InvoiceSequencesPage: typeof import("../../src/surfaces/setup/InvoiceSequencesPage.js").InvoiceSequencesPage;

  const makeSequence = (overrides = {}) => ({
    id: "s1000000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    prefix: "INV-",
    next_value: 1001,
    padding: 6,
    active: true,
    created_at: NOW,
    ...overrides,
  });

  beforeEach(async () => {
    ({ InvoiceSequencesPage } = await import("../../src/surfaces/setup/InvoiceSequencesPage.js"));
  });

  it("renders the invoice sequences page container", () => {
    render(<InvoiceSequencesPage sequences={[]} isLoading={false} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("invoice-sequences-page")).toBeTruthy();
  });

  it("renders a row for each sequence", () => {
    render(
      <InvoiceSequencesPage
        sequences={[makeSequence(), makeSequence({ id: "s2", prefix: "CRED-" })]}
        isLoading={false}
        error={null}
        currentRole="approver"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getAllByTestId("invoice-sequence-row")).toHaveLength(2);
  });

  it("renders prefix and next_value", () => {
    render(
      <InvoiceSequencesPage
        sequences={[makeSequence()]}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText("INV-")).toBeTruthy();
    expect(screen.getByText("1001")).toBeTruthy();
  });

  it("Approver save allowed", () => {
    render(
      <InvoiceSequencesPage sequences={[]} isLoading={false} error={null} currentRole="approver" onSave={vi.fn()} />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("Operator save denied", () => {
    render(
      <InvoiceSequencesPage sequences={[]} isLoading={false} error={null} currentRole="operator" onSave={vi.fn()} />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders loading state", () => {
    render(<InvoiceSequencesPage sequences={[]} isLoading={true} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("invoice-sequences-loading")).toBeTruthy();
  });
});

// ── CycleSchedulesPage ───────────────────────────────────────────────────

describe("CycleSchedulesPage", () => {
  let CycleSchedulesPage: typeof import("../../src/surfaces/setup/CycleSchedulesPage.js").CycleSchedulesPage;

  const makeSchedule = (overrides = {}) => ({
    id: "cs100000-0000-0000-0000-000000000001",
    tenant_id: TENANT,
    name: "Monthly Standard",
    frequency: "monthly" as const,
    close_day: 25,
    open_day: 1,
    active: true,
    created_at: NOW,
    ...overrides,
  });

  beforeEach(async () => {
    ({ CycleSchedulesPage } = await import("../../src/surfaces/setup/CycleSchedulesPage.js"));
  });

  it("renders the cycle schedules page container", () => {
    render(<CycleSchedulesPage schedules={[]} isLoading={false} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("cycle-schedules-page")).toBeTruthy();
  });

  it("renders a row for each schedule", () => {
    render(
      <CycleSchedulesPage
        schedules={[makeSchedule(), makeSchedule({ id: "cs2", name: "Quarterly", frequency: "quarterly" })]}
        isLoading={false}
        error={null}
        currentRole="approver"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getAllByTestId("cycle-schedule-row")).toHaveLength(2);
  });

  it("renders schedule name and frequency", () => {
    render(
      <CycleSchedulesPage
        schedules={[makeSchedule()]}
        isLoading={false}
        error={null}
        currentRole="operator"
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText("Monthly Standard")).toBeTruthy();
    expect(screen.getByText("monthly")).toBeTruthy();
  });

  it("Approver save allowed", () => {
    render(
      <CycleSchedulesPage schedules={[]} isLoading={false} error={null} currentRole="approver" onSave={vi.fn()} />,
    );
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("Operator save denied", () => {
    render(
      <CycleSchedulesPage schedules={[]} isLoading={false} error={null} currentRole="operator" onSave={vi.fn()} />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("Auditor save denied", () => {
    render(
      <CycleSchedulesPage schedules={[]} isLoading={false} error={null} currentRole="auditor" onSave={vi.fn()} />,
    );
    expect(screen.getByTestId("rbac-gate-denied")).toBeTruthy();
  });

  it("renders loading state", () => {
    render(<CycleSchedulesPage schedules={[]} isLoading={true} error={null} currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("cycle-schedules-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(<CycleSchedulesPage schedules={[]} isLoading={false} error="Load failed" currentRole="operator" onSave={vi.fn()} />);
    expect(screen.getByTestId("cycle-schedules-error")).toBeTruthy();
  });
});

// ── BFF setup handlers ────────────────────────────────────────────────────

describe("BFF setup handlers", () => {
  let handleListEmailRecipients: typeof import("../../src/surfaces/setup/bff/setup.js").handleListEmailRecipients;
  let handleListEmailTemplates: typeof import("../../src/surfaces/setup/bff/setup.js").handleListEmailTemplates;
  let handleListExportTemplates: typeof import("../../src/surfaces/setup/bff/setup.js").handleListExportTemplates;
  let handleListGlAccountMappings: typeof import("../../src/surfaces/setup/bff/setup.js").handleListGlAccountMappings;
  let handleListInvoiceSequences: typeof import("../../src/surfaces/setup/bff/setup.js").handleListInvoiceSequences;
  let handleListCycleSchedules: typeof import("../../src/surfaces/setup/bff/setup.js").handleListCycleSchedules;

  beforeEach(async () => {
    ({
      handleListEmailRecipients,
      handleListEmailTemplates,
      handleListExportTemplates,
      handleListGlAccountMappings,
      handleListInvoiceSequences,
      handleListCycleSchedules,
    } = await import("../../src/surfaces/setup/bff/setup.js"));
  });

  it("handleListEmailRecipients returns 200 with data", async () => {
    const mockClient = { listEmailRecipients: vi.fn().mockResolvedValue({ results: [], total: 0 }) };
    const result = await handleListEmailRecipients({ headers: {} }, mockClient as never);
    expect(result.status).toBe(200);
  });

  it("handleListEmailTemplates returns 200 with data", async () => {
    const mockClient = { listEmailTemplates: vi.fn().mockResolvedValue({ results: [], total: 0 }) };
    const result = await handleListEmailTemplates({ headers: {} }, mockClient as never);
    expect(result.status).toBe(200);
  });

  it("handleListExportTemplates returns 200 with data", async () => {
    const mockClient = { listExportTemplates: vi.fn().mockResolvedValue({ results: [], total: 0 }) };
    const result = await handleListExportTemplates({ headers: {} }, mockClient as never);
    expect(result.status).toBe(200);
  });

  it("handleListGlAccountMappings returns 200 with data", async () => {
    const mockClient = { listGlAccountMappings: vi.fn().mockResolvedValue({ results: [], total: 0 }) };
    const result = await handleListGlAccountMappings({ headers: {} }, mockClient as never);
    expect(result.status).toBe(200);
  });

  it("handleListInvoiceSequences returns 200 with data", async () => {
    const mockClient = { listInvoiceSequences: vi.fn().mockResolvedValue({ results: [], total: 0 }) };
    const result = await handleListInvoiceSequences({ headers: {} }, mockClient as never);
    expect(result.status).toBe(200);
  });

  it("handleListCycleSchedules returns 200 with data", async () => {
    const mockClient = { listCycleSchedules: vi.fn().mockResolvedValue({ results: [], total: 0 }) };
    const result = await handleListCycleSchedules({ headers: {} }, mockClient as never);
    expect(result.status).toBe(200);
  });
});
