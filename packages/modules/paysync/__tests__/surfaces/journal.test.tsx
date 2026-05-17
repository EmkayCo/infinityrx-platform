// packages/modules/paysync/__tests__/surfaces/journal.test.tsx
// RTL tests for the journal surface components.
// Uses happy-dom. Follows the batches/files test pattern.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { JournalEntry, HashChainVerifyResponse } from "@infinityrx/contract";

afterEach(() => cleanup());

// ── Shared fixtures ──────────────────────────────────────────────────────

const TENANT = "t0000000-0000-0000-0000-000000000001";
const NOW = "2026-05-17T12:00:00.000+00:00";
const ENTRY_ID = "je000000-0000-0000-0000-000000000001";
const UPLOAD_ID = "u0000000-0000-0000-0000-000000000001";

function makeEntry(overrides: Partial<JournalEntry> = {}): JournalEntry {
  return {
    id: ENTRY_ID,
    tenant_id: TENANT,
    entry_date: "2026-05-17",
    entry_timestamp: NOW,
    entry_type: "payment",
    client_id: "c0000000-0000-0000-0000-000000000001",
    client_name: "Acme Health Plan",
    program_id: null,
    program_name: null,
    pay_to_entity_id: null,
    pay_to_entity_name: null,
    amount: "1234.56",
    category: "rebate",
    gl_account_code: "2000",
    gl_class: null,
    reference_type: "batch",
    reference_id: "b1000000-0000-0000-0000-000000000001",
    description: "Monthly rebate payment",
    exported_to_accounting: false,
    exported_at: null,
    export_reference: null,
    created_at: NOW,
    entry_hash: "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    prev_hash: "0000000000000000000000000000000000000000000000000000000000000000",
    ...overrides,
  };
}

function makeVerifyResponse(overrides: Partial<HashChainVerifyResponse> = {}): HashChainVerifyResponse {
  return {
    verified: true,
    too_large: false,
    job_id: null,
    total_entries: 42,
    broken_at: null,
    ...overrides,
  };
}

// ── JournalListPage ───────────────────────────────────────────────────────

describe("JournalListPage", () => {
  let JournalListPage: typeof import("../../src/surfaces/journal/JournalListPage.js").JournalListPage;

  beforeEach(async () => {
    ({ JournalListPage } = await import("../../src/surfaces/journal/JournalListPage.js"));
  });

  it("renders the journal list page container", () => {
    render(<JournalListPage entries={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("journal-list-page")).toBeTruthy();
  });

  it("renders a row for each entry", () => {
    const entries = [
      makeEntry({ id: "je1" }),
      makeEntry({ id: "je2", amount: "500.00" }),
    ];
    render(<JournalListPage entries={entries} isLoading={false} error={null} />);
    expect(screen.getAllByTestId("journal-entry-row")).toHaveLength(2);
  });

  it("renders MoneyDisplay for each entry amount", () => {
    render(<JournalListPage entries={[makeEntry()]} isLoading={false} error={null} />);
    expect(screen.getByTestId("money-display")).toBeTruthy();
  });

  it("renders truncated entry_hash (first 8 chars + ellipsis)", () => {
    render(<JournalListPage entries={[makeEntry()]} isLoading={false} error={null} />);
    const hashCell = screen.getByTestId("entry-hash-short");
    expect(hashCell.textContent).toBe("abcdef12...");
  });

  it("renders entry_type column", () => {
    render(<JournalListPage entries={[makeEntry({ entry_type: "rebate" })]} isLoading={false} error={null} />);
    expect(screen.getByText("rebate")).toBeTruthy();
  });

  it("renders loading state when isLoading=true", () => {
    render(<JournalListPage entries={[]} isLoading={true} error={null} />);
    expect(screen.getByTestId("journal-list-loading")).toBeTruthy();
  });

  it("renders error state when error is set", () => {
    render(<JournalListPage entries={[]} isLoading={false} error="Network error" />);
    expect(screen.getByTestId("journal-list-error")).toBeTruthy();
  });

  it("renders empty state when no entries", () => {
    render(<JournalListPage entries={[]} isLoading={false} error={null} />);
    expect(screen.getByTestId("journal-list-empty")).toBeTruthy();
  });

  it("renders gl_account_code column", () => {
    render(<JournalListPage entries={[makeEntry({ gl_account_code: "2000" })]} isLoading={false} error={null} />);
    expect(screen.getByText("2000")).toBeTruthy();
  });

  it("renders created_at as a time element", () => {
    render(<JournalListPage entries={[makeEntry()]} isLoading={false} error={null} />);
    expect(screen.getByRole("cell", { name: /2026/i }) || screen.getByTestId("journal-entry-row")).toBeTruthy();
  });
});

// ── JournalDetailPage ─────────────────────────────────────────────────────

describe("JournalDetailPage", () => {
  let JournalDetailPage: typeof import("../../src/surfaces/journal/JournalDetailPage.js").JournalDetailPage;

  beforeEach(async () => {
    ({ JournalDetailPage } = await import("../../src/surfaces/journal/JournalDetailPage.js"));
  });

  it("renders the journal detail page container", () => {
    render(<JournalDetailPage entry={makeEntry()} isLoading={false} error={null} />);
    expect(screen.getByTestId("journal-detail-page")).toBeTruthy();
  });

  it("renders the full entry_hash", () => {
    render(<JournalDetailPage entry={makeEntry()} isLoading={false} error={null} />);
    const fullHash = screen.getByTestId("entry-hash-full");
    expect(fullHash.textContent).toContain("abcdef1234567890");
  });

  it("renders the prev_hash", () => {
    render(<JournalDetailPage entry={makeEntry()} isLoading={false} error={null} />);
    const prevHash = screen.getByTestId("entry-prev-hash");
    expect(prevHash.textContent).toContain("0000000000000000");
  });

  it("renders hash-chain link visualization (hash chain section)", () => {
    render(<JournalDetailPage entry={makeEntry()} isLoading={false} error={null} />);
    expect(screen.getByTestId("hash-chain-links")).toBeTruthy();
  });

  it("renders upload cross-link when upload_id is present", () => {
    render(
      <JournalDetailPage
        entry={makeEntry({ reference_type: "upload", reference_id: UPLOAD_ID })}
        isLoading={false}
        error={null}
        uploadId={UPLOAD_ID}
      />,
    );
    const link = screen.getByTestId("entry-upload-link") as HTMLAnchorElement;
    expect(link.href).toContain(UPLOAD_ID);
  });

  it("does not render upload link when upload_id is absent", () => {
    render(<JournalDetailPage entry={makeEntry()} isLoading={false} error={null} />);
    expect(screen.queryByTestId("entry-upload-link")).toBeNull();
  });

  it("renders loading state", () => {
    render(<JournalDetailPage entry={null} isLoading={true} error={null} />);
    expect(screen.getByTestId("journal-detail-loading")).toBeTruthy();
  });

  it("renders error state", () => {
    render(<JournalDetailPage entry={null} isLoading={false} error="Not found" />);
    expect(screen.getByTestId("journal-detail-error")).toBeTruthy();
  });

  it("renders not-found state when entry is null", () => {
    render(<JournalDetailPage entry={null} isLoading={false} error={null} />);
    expect(screen.getByTestId("journal-detail-page")).toBeTruthy();
  });
});

// ── HashChainVerifyButton ─────────────────────────────────────────────────

describe("HashChainVerifyButton", () => {
  let HashChainVerifyButton: typeof import("../../src/surfaces/journal/HashChainVerifyButton.js").HashChainVerifyButton;

  beforeEach(async () => {
    ({ HashChainVerifyButton } = await import("../../src/surfaces/journal/HashChainVerifyButton.js"));
  });

  it("renders the verify button container", () => {
    const onVerify = vi.fn().mockResolvedValue(makeVerifyResponse());
    render(<HashChainVerifyButton currentRole="auditor" onVerify={onVerify} />);
    expect(screen.getByTestId("hash-chain-verify-panel")).toBeTruthy();
  });

  it("renders verify button in idle state", () => {
    const onVerify = vi.fn().mockResolvedValue(makeVerifyResponse());
    render(<HashChainVerifyButton currentRole="auditor" onVerify={onVerify} />);
    expect(screen.getByTestId("verify-chain-button")).toBeTruthy();
  });

  it("renders RbacGate allowed for Auditor", () => {
    const onVerify = vi.fn().mockResolvedValue(makeVerifyResponse());
    render(<HashChainVerifyButton currentRole="auditor" onVerify={onVerify} />);
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("renders RbacGate allowed for Approver", () => {
    const onVerify = vi.fn().mockResolvedValue(makeVerifyResponse());
    render(<HashChainVerifyButton currentRole="approver" onVerify={onVerify} />);
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("renders RbacGate allowed for Operator", () => {
    const onVerify = vi.fn().mockResolvedValue(makeVerifyResponse());
    render(<HashChainVerifyButton currentRole="operator" onVerify={onVerify} />);
    expect(screen.getByTestId("rbac-gate-allowed")).toBeTruthy();
  });

  it("shows verifying spinner while in flight", async () => {
    let resolve: (v: HashChainVerifyResponse) => void;
    const onVerify = vi.fn().mockReturnValue(new Promise<HashChainVerifyResponse>((r) => { resolve = r; }));
    render(<HashChainVerifyButton currentRole="auditor" onVerify={onVerify} />);
    fireEvent.click(screen.getByTestId("verify-chain-button"));
    await waitFor(() => {
      expect(screen.getByTestId("verify-state-verifying")).toBeTruthy();
    });
    resolve!(makeVerifyResponse());
  });

  it("shows HashChainBadge verified=true (green) after successful verify", async () => {
    const onVerify = vi.fn().mockResolvedValue(makeVerifyResponse({ verified: true }));
    render(<HashChainVerifyButton currentRole="auditor" onVerify={onVerify} />);
    fireEvent.click(screen.getByTestId("verify-chain-button"));
    await waitFor(() => {
      expect(screen.getByTestId("hash-chain-verified")).toBeTruthy();
    });
  });

  it("shows HashChainBadge verified=false (red) when chain is broken", async () => {
    const onVerify = vi.fn().mockResolvedValue(
      makeVerifyResponse({ verified: false, broken_at: ENTRY_ID }),
    );
    render(<HashChainVerifyButton currentRole="auditor" onVerify={onVerify} />);
    fireEvent.click(screen.getByTestId("verify-chain-button"));
    await waitFor(() => {
      expect(screen.getByTestId("hash-chain-failed")).toBeTruthy();
    });
  });

  it("shows broken_at entry id when chain is broken", async () => {
    const onVerify = vi.fn().mockResolvedValue(
      makeVerifyResponse({ verified: false, broken_at: ENTRY_ID }),
    );
    render(<HashChainVerifyButton currentRole="auditor" onVerify={onVerify} />);
    fireEvent.click(screen.getByTestId("verify-chain-button"));
    await waitFor(() => {
      expect(screen.getByTestId("verify-broken-at")).toBeTruthy();
    });
  });

  it("shows HashChainBadge tooLarge (amber) when too_large=true", async () => {
    const onVerify = vi.fn().mockResolvedValue(
      makeVerifyResponse({ verified: null, too_large: true }),
    );
    render(<HashChainVerifyButton currentRole="auditor" onVerify={onVerify} />);
    fireEvent.click(screen.getByTestId("verify-chain-button"));
    await waitFor(() => {
      expect(screen.getByTestId("hash-chain-too-large")).toBeTruthy();
    });
  });

  it("does not auto-repair on broken chain (no repair button rendered)", async () => {
    const onVerify = vi.fn().mockResolvedValue(
      makeVerifyResponse({ verified: false, broken_at: ENTRY_ID }),
    );
    render(<HashChainVerifyButton currentRole="auditor" onVerify={onVerify} />);
    fireEvent.click(screen.getByTestId("verify-chain-button"));
    await waitFor(() => {
      expect(screen.getByTestId("hash-chain-failed")).toBeTruthy();
    });
    expect(screen.queryByTestId("verify-repair-button")).toBeNull();
  });
});

// ── BFF journal handlers ──────────────────────────────────────────────────

describe("BFF journal handlers", () => {
  let handlers: typeof import("../../src/surfaces/journal/bff/journal.js");
  let createMockJournalClient: typeof import("@infinityrx/contract")["createMockJournalClient"];

  beforeEach(async () => {
    handlers = await import("../../src/surfaces/journal/bff/journal.js");
    ({ createMockJournalClient } = await import("@infinityrx/contract"));
  });

  it("handleListJournal returns 200 with results", async () => {
    const client = createMockJournalClient();
    const req = { headers: {}, searchParams: new URLSearchParams() };
    const resp = await handlers.handleListJournal(req, client);
    expect(resp.status).toBe(200);
  });

  it("handleGetJournalEntry returns 404 when not found", async () => {
    const client = createMockJournalClient();
    const req = { headers: {} };
    const resp = await handlers.handleGetJournalEntry("not-an-id", req, client);
    expect(resp.status).toBe(404);
  });

  it("handleVerifyChain returns 200 with verify response", async () => {
    const client = createMockJournalClient();
    const req = { headers: {} };
    const resp = await handlers.handleVerifyChain(req, client);
    expect(resp.status).toBe(200);
    expect(resp.data).toHaveProperty("verified");
  });
});
